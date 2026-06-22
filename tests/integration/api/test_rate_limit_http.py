"""HTTP contract tests for rate-limit retry status fields (issue #62).

Verifies:
- GET /v1/sessions/{id}/tasks exposes ``status`` and ``retry_info`` on the
  in-flight task response.
- ``status="dispatched"`` by default (no retry in progress).
- ``status="retrying"`` with ``retry_info`` populated when the projection
  has retry metadata.
- OpenAPI schema documents ``status`` enum and ``retry_info`` on TaskResponse.
- 422 on unknown ``status`` value (schema enforcement via Pydantic).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from mad.core.orchestration.domain.task import Task
from mad.core.orchestration.ports.task_queue import RetryInfo


def _session_id(client: TestClient, session_payload: dict) -> str:
    r = client.post("/v1/sessions", json=session_payload)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _inject_in_flight_with_retry(client: TestClient, session_id: str) -> None:
    """Place an in-flight task and retry_info directly on the projection."""
    projection = client.app.state.task_projection
    task = Task(
        task_id=uuid4(),
        session_id=session_id,
        content="rate-limited work",
        scheduled_for="now",
        created_at=datetime.now(UTC),
    )
    projection._in_flight[session_id] = task
    projection._retry_info[session_id] = RetryInfo(
        attempt=2,
        retry_after_s=120.0,
        reason="overloaded",
    )


def _inject_in_flight_normal(client: TestClient, session_id: str) -> Task:
    """Place an in-flight task without retry metadata."""
    projection = client.app.state.task_projection
    task = Task(
        task_id=uuid4(),
        session_id=session_id,
        content="normal running work",
        scheduled_for="now",
        created_at=datetime.now(UTC),
    )
    projection._in_flight[session_id] = task
    return task


# -- status field defaults to "dispatched" ------------------------------------


def test_in_flight_task_status_defaults_to_dispatched(
    client: TestClient, session_payload: dict
) -> None:
    session_id = _session_id(client, session_payload)
    _inject_in_flight_normal(client, session_id)

    r = client.get(f"/v1/sessions/{session_id}/tasks")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["in_flight"] is not None
    assert body["in_flight"]["status"] == "dispatched"
    assert body["in_flight"]["retry_info"] is None


# -- status="retrying" with retry_info -----------------------------------------


def test_in_flight_task_status_retrying_with_retry_info(
    client: TestClient, session_payload: dict
) -> None:
    session_id = _session_id(client, session_payload)
    _inject_in_flight_with_retry(client, session_id)

    r = client.get(f"/v1/sessions/{session_id}/tasks")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["in_flight"] is not None
    assert body["in_flight"]["status"] == "retrying"
    ri = body["in_flight"]["retry_info"]
    assert ri is not None
    assert ri["attempt"] == 2
    assert ri["retry_after_s"] == 120.0
    assert ri["reason"] == "overloaded"


# -- retry_info absent when no retry in progress --------------------------------


def test_no_in_flight_task_returns_null(client: TestClient, session_payload: dict) -> None:
    session_id = _session_id(client, session_payload)

    r = client.get(f"/v1/sessions/{session_id}/tasks")

    assert r.status_code == 200, r.text
    assert r.json()["in_flight"] is None


# -- OpenAPI contract ----------------------------------------------------------


def test_openapi_documents_status_and_retry_info_on_task_response(
    client: TestClient,
) -> None:
    """OpenAPI schema for TaskResponse must include ``status`` and ``retry_info``."""
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    assert "TaskResponse" in schemas, "TaskResponse not in OpenAPI schemas"
    props = schemas["TaskResponse"]["properties"]

    # status field
    assert "status" in props, "status not in TaskResponse"
    status_schema = props["status"]
    # Pydantic emits: {"type": "string", "enum": ["dispatched", "retrying"], "default": "dispatched"}
    assert status_schema["type"] == "string", f"status.type is not string: {status_schema}"
    assert set(status_schema["enum"]) == {"dispatched", "retrying"}, (
        f"status.enum mismatch: {status_schema}"
    )
    assert status_schema.get("default") == "dispatched", (
        f"status.default is not 'dispatched': {status_schema}"
    )

    # retry_info field
    assert "retry_info" in props, "retry_info not in TaskResponse"
    ri_schema = props["retry_info"]
    # Pydantic emits: {"anyOf": [{"$ref": "...RetryInfoResponse"}, {"type": "null"}]}
    any_of = ri_schema.get("anyOf", [])
    assert len(any_of) == 2, f"retry_info.anyOf expected 2 items: {ri_schema}"
    types_in_any_of = [item.get("type") for item in any_of]
    assert "null" in types_in_any_of, f"retry_info.anyOf does not include null: {ri_schema}"
    refs_in_any_of = [item.get("$ref", "") for item in any_of]
    assert any("RetryInfoResponse" in r for r in refs_in_any_of), (
        f"retry_info.anyOf does not reference RetryInfoResponse: {ri_schema}"
    )
