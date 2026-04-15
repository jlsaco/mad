from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from mad.agent.loop import run_agent_loop
from mad.core import log
from mad.core.resources import provision_file, provision_github_repo
from mad.core.security import validate_mount_path
from mad.core.sessions import SessionStore
from mad.core.workspace import workspace_path

router = APIRouter()


def _store(request: Request) -> SessionStore:
    return request.app.state.store


@router.post("/v1/sessions")
async def create_session(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    log.ensure_sessions_dir()
    store = _store(request)

    if idempotency_key and idempotency_key in store.idempotency:
        existing_id = store.idempotency[idempotency_key]
        return store.sessions[existing_id]["response"]

    body = await request.json()
    agent = body["agent"]
    resources = body.get("resources", [])

    for res in resources:
        validate_mount_path(res["mount_path"])

    session_id = "sesn_" + uuid.uuid4().hex[:12]
    workspace = workspace_path(session_id)
    workspace.mkdir(parents=True, exist_ok=True)

    log.emit(session_id, "session.created", {"agent": agent["name"]})

    resources_mounted = []
    for res in resources:
        if res["type"] == "github_repository":
            mounted = provision_github_repo(session_id, res)
        elif res["type"] == "file":
            mounted = provision_file(session_id, res)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown resource type: {res['type']!r}")
        resources_mounted.append(mounted)

    response = {
        "session_id": session_id,
        "status": "created",
        "workspace": str(workspace),
        "resources_mounted": resources_mounted,
    }

    store.sessions[session_id] = {
        "session_id": session_id,
        "agent": agent,
        "workspace": str(workspace),
        "status": "created",
        "response": response,
    }
    store.get_or_create_queue(session_id)

    if idempotency_key:
        store.idempotency[idempotency_key] = session_id

    return response


@router.post("/v1/sessions/{session_id}/events")
async def send_events(session_id: str, request: Request) -> dict:
    store = _store(request)
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    body = await request.json()
    events = body.get("events", [])
    session = store.sessions[session_id]

    for event in events:
        event_type = event.get("type")
        if event_type == "user.message":
            content = event.get("content", "")
            log.emit(session_id, "user.message", {"content": content})
            asyncio.create_task(run_agent_loop(store, session_id, session, content))

    return {"status": "accepted"}


@router.get("/v1/sessions/{session_id}/stream")
async def stream_session(session_id: str, request: Request) -> StreamingResponse:
    store = _store(request)
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    queue = store.get_or_create_queue(session_id)

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/v1/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> dict:
    store = _store(request)
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = store.sessions[session_id]
    events = log.get_events(session_id)
    return {
        "session_id": session_id,
        "status": session["status"],
        "workspace": session["workspace"],
        "events": events,
    }


@router.get("/v1/sessions")
async def list_sessions(request: Request) -> list:
    store = _store(request)
    return [
        {"session_id": sid, "status": s["status"]}
        for sid, s in store.sessions.items()
    ]


@router.delete("/v1/sessions/{session_id}")
async def delete_session(session_id: str, request: Request) -> dict:
    store = _store(request)
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = store.sessions[session_id]
    workspace = Path(session["workspace"])

    if workspace.exists():
        shutil.rmtree(workspace)

    session["status"] = "deleted"
    store.sse_queues.pop(session_id, None)

    return {"status": "deleted", "session_id": session_id}
