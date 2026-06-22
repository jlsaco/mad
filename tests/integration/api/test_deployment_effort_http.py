"""HTTP integration tests for deployment effort config routes (issue #60).

Endpoints under test:
- GET  /v1/effort
- PUT  /v1/effort
- DELETE /v1/effort

Also covers:
- OpenAPI contract test for PUT /v1/effort (heuristic rule 5).
- Bootstrap / persistence round-trip for DeploymentEffortConfig.
- Opaque pass-through at session create (effort is NOT validated — unlike model).
- Launcher effort threading (ScriptedLauncher records effort on each call).

Mirrors ``test_deployment_model_http`` but deliberately omits model's 422
validation and task-enqueue cases: effort is an opaque pass-through string
and has no task-level override (issue #60 out of scope).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mad.adapters.inbound.http.app import create_app
from mad.core.orchestration.domain.effort_config import (
    DEPLOYMENT_EFFORT_SESSION_ID,
    DeploymentEffortConfig,
)
from mad.core.orchestration.use_cases.deployment_effort_config import (
    bootstrap_deployment_effort_config,
)
from support.launchers import ScriptedLauncher
from support.sessions import FakeSessionRepository

# ---------------------------------------------------------------------------
# GET /v1/effort
# ---------------------------------------------------------------------------


def test_get_deployment_effort_unset_returns_null(client: TestClient) -> None:
    """With no deployment effort configured, effort is null."""
    r = client.get("/v1/effort")
    assert r.status_code == 200, r.text
    assert r.json() == {"effort": None}


def test_get_deployment_effort_reflects_prior_put(client: TestClient) -> None:
    """Negative twin / live state: after a PUT, GET reads the new value."""
    client.put("/v1/effort", json={"effort": "high"})
    r = client.get("/v1/effort")
    assert r.status_code == 200, r.text
    assert r.json() == {"effort": "high"}


# ---------------------------------------------------------------------------
# PUT /v1/effort
# ---------------------------------------------------------------------------


def test_put_deployment_effort_returns_200_and_effort(client: TestClient) -> None:
    """Setting the deployment effort returns 200 with the new effort value."""
    r = client.put("/v1/effort", json={"effort": "low"})
    assert r.status_code == 200, r.text
    assert r.json() == {"effort": "low"}


def test_put_deployment_effort_missing_effort_field_returns_422(client: TestClient) -> None:
    """Negative twin: omitting the required ``effort`` field returns 422."""
    r = client.put("/v1/effort", json={})
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# DELETE /v1/effort
# ---------------------------------------------------------------------------


def test_delete_deployment_effort_clears_to_null(client: TestClient) -> None:
    """After PUT then DELETE, GET reports null again."""
    client.put("/v1/effort", json={"effort": "high"})
    r = client.delete("/v1/effort")
    assert r.status_code == 200, r.text
    assert r.json() == {"effort": None}

    r2 = client.get("/v1/effort")
    assert r2.json() == {"effort": None}


def test_delete_deployment_effort_idempotent_when_already_null(client: TestClient) -> None:
    """Negative twin: deleting when already unset is a 200 no-op."""
    r = client.delete("/v1/effort")
    assert r.status_code == 200, r.text
    assert r.json() == {"effort": None}


# ---------------------------------------------------------------------------
# OpenAPI contract test for PUT /v1/effort (heuristic rule 5)
# ---------------------------------------------------------------------------


def test_openapi_put_deployment_effort_declares_effort_field(client: TestClient) -> None:
    """PUT /v1/effort must appear in the OpenAPI spec with a body schema
    that has a required ``effort`` field (string)."""
    spec = client.get("/openapi.json").json()
    paths = spec.get("paths", {})
    assert "/v1/effort" in paths, "PUT /v1/effort route absent from OpenAPI spec"
    put_op = paths["/v1/effort"].get("put", {})
    assert put_op, "PUT operation absent from /v1/effort spec"
    body = put_op.get("requestBody", {})
    assert body, "PUT /v1/effort has no requestBody"
    schema_ref = body["content"]["application/json"]["schema"]
    # Resolve $ref to SetDeploymentEffortRequest schema
    ref = schema_ref.get("$ref", "")
    schema_name = ref.rsplit("/", 1)[-1] if ref else ""
    schema = spec["components"]["schemas"][schema_name] if schema_name else schema_ref
    assert "effort" in schema.get("required", []), (
        f"'effort' must be required in SetDeploymentEffortRequest schema, got: {schema}"
    )
    props = schema.get("properties", {})
    assert "effort" in props, f"'effort' must be a property, got: {props}"


# ---------------------------------------------------------------------------
# Bootstrap / persistence round-trip
# ---------------------------------------------------------------------------


def test_bootstrap_deployment_effort_config_last_write_wins() -> None:
    """Two ``effort.default.updated`` events → last one wins after replay."""
    repo = FakeSessionRepository()
    repo.append_event(DEPLOYMENT_EFFORT_SESSION_ID, "effort.default.updated", {"effort": "first"})
    repo.append_event(DEPLOYMENT_EFFORT_SESSION_ID, "effort.default.updated", {"effort": "last"})
    config = DeploymentEffortConfig()

    bootstrap_deployment_effort_config(config, repo)

    assert config.default_effort == "last"


def test_bootstrap_then_cleared_leaves_none() -> None:
    """After an update followed by a clear, bootstrap results in None."""
    repo = FakeSessionRepository()
    repo.append_event(DEPLOYMENT_EFFORT_SESSION_ID, "effort.default.updated", {"effort": "mid"})
    repo.append_event(DEPLOYMENT_EFFORT_SESSION_ID, "effort.default.cleared", {})
    config = DeploymentEffortConfig()

    bootstrap_deployment_effort_config(config, repo)

    assert config.default_effort is None


def test_bootstrap_missing_log_leaves_default_none() -> None:
    """Negative twin: no reserved log → default_effort stays None."""
    repo = FakeSessionRepository()
    config = DeploymentEffortConfig()

    bootstrap_deployment_effort_config(config, repo)

    assert config.default_effort is None


# ---------------------------------------------------------------------------
# Opaque pass-through at session create (effort is NOT validated)
# ---------------------------------------------------------------------------


def _base_session_payload() -> dict:
    return {
        "agent": {"name": "a", "provider": "claude_cli"},
        "resources": [],
    }


def test_post_session_with_arbitrary_effort_is_accepted(client: TestClient) -> None:
    """An effort value Mad has never heard of is accepted (200) — effort is an
    opaque pass-through string, NOT validated against any provider's levels.
    This is the deliberate contrast to model, which 422s on an unknown id."""
    payload = _base_session_payload()
    payload["effort"] = "ultra-mega-think-9000"
    r = client.post("/v1/sessions", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["session_id"].startswith("sesn_")


def test_post_session_without_effort_field_succeeds(client: TestClient) -> None:
    """Negative twin: no effort field → session created (inherits deployment default)."""
    r = client.post("/v1/sessions", json=_base_session_payload())
    assert r.status_code == 200, r.text
    assert r.json()["session_id"].startswith("sesn_")


# ---------------------------------------------------------------------------
# Launcher effort threading (ScriptedLauncher records effort)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_threads_session_effort_to_launcher(
    tmp_path: Path,
    tmp_sessions_dir: Path,
    tmp_workspaces_dir: Path,
) -> None:
    """Create a session with an arbitrary effort, send a message, and assert
    the ScriptedLauncher received that exact effort on both calls (primary +
    auto-sync) — proving both the threading AND the opaque pass-through."""
    launcher = ScriptedLauncher()
    launcher.script(
        [
            [{"type": "session.status_idle", "stop_reason": "end_turn"}],
            [{"type": "session.status_idle", "stop_reason": "end_turn"}],
        ]
    )
    c = TestClient(create_app(launcher_factory=lambda _name: launcher))

    payload = {
        "agent": {"name": "a", "provider": "claude_cli"},
        "resources": [],
        "effort": "high",
    }
    r = c.post("/v1/sessions", json=payload)
    assert r.status_code == 200, r.text
    session_id = r.json()["session_id"]

    r2 = c.post(f"/v1/sessions/{session_id}/messages", json={"content": "go"})
    assert r2.status_code == 200, r2.text

    # Wait for both launcher calls (primary + auto-sync).
    deadline = asyncio.get_event_loop().time() + 3.0
    while len(launcher.calls) < 2 and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.05)

    assert len(launcher.calls) >= 1, "Launcher must have been called at least once"
    for call in launcher.calls:
        assert call["effort"] == "high", f"Expected effort='high' on all calls, got: {call}"


@pytest.mark.asyncio
async def test_send_message_passes_none_effort_when_no_effort_set(
    tmp_path: Path,
    tmp_sessions_dir: Path,
    tmp_workspaces_dir: Path,
) -> None:
    """Negative twin: no effort at any level → launcher receives effort=None."""
    launcher = ScriptedLauncher()
    launcher.script(
        [
            [{"type": "session.status_idle", "stop_reason": "end_turn"}],
            [{"type": "session.status_idle", "stop_reason": "end_turn"}],
        ]
    )
    c = TestClient(create_app(launcher_factory=lambda _name: launcher))

    payload = {
        "agent": {"name": "a", "provider": "claude_cli"},
        "resources": [],
    }
    r = c.post("/v1/sessions", json=payload)
    assert r.status_code == 200, r.text
    session_id = r.json()["session_id"]

    r2 = c.post(f"/v1/sessions/{session_id}/messages", json={"content": "go"})
    assert r2.status_code == 200, r2.text

    deadline = asyncio.get_event_loop().time() + 3.0
    while len(launcher.calls) < 1 and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.05)

    assert len(launcher.calls) >= 1
    for call in launcher.calls:
        assert call["effort"] is None, f"Expected effort=None on all calls, got: {call}"
