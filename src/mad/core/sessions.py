from __future__ import annotations

import asyncio

from mad.core import log


class SessionStore:
    """Holds all per-process session state. Injected into create_app() so
    tests (and other embeddings) get a fresh instance with no global leakage.
    """

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.idempotency: dict[str, str] = {}
        self.sse_queues: dict[str, asyncio.Queue] = {}

    def get_or_create_queue(self, session_id: str) -> asyncio.Queue:
        if session_id not in self.sse_queues:
            self.sse_queues[session_id] = asyncio.Queue()
        return self.sse_queues[session_id]

    def push_event(self, session_id: str, event: dict) -> None:
        q = self.sse_queues.get(session_id)
        if q is not None:
            q.put_nowait(event)

    def emit_and_push(self, session_id: str, event_type: str, data: dict | None = None) -> dict:
        event = log.emit(session_id, event_type, data)
        self.push_event(session_id, event)
        return event
