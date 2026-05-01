"""Unit tests for SendUserMessageUseCase.

Tests the synchronous validation path. The async launcher run is tested
via integration tests.
"""
from __future__ import annotations

import asyncio

import pytest

from mad.core.domain.entities.session import Session
from mad.core.domain.exceptions.base import SessionNotFound
from mad.core.use_cases.sessions.send_user_message import (
    SendUserMessageInput,
    SendUserMessageUseCase,
    _redact_tokens,
)


class FakeRepo:
    def __init__(self):
        self.events: list[dict] = []

    def append_event(self, session_id, event_type, data=None):
        event = {"type": event_type, **(data or {})}
        self.events.append(event)
        return event

    def read_events(self, session_id):
        return self.events

    def exists(self, session_id):
        return True


def _make_session(session_id="sesn_msg", tokens=None):
    return Session(
        session_id=session_id,
        agent={"name": "t", "provider": "fake"},
        workspace="/tmp/mad_sesn_msg",
        tokens_to_redact=tokens or [],
    )


def test_send_message_session_not_found():
    sessions: dict = {}
    uc = SendUserMessageUseCase(
        repo=FakeRepo(),
        sessions_index=sessions,
        sse_queues={},
        get_launcher=lambda name: None,
    )
    with pytest.raises(SessionNotFound):
        uc.execute(SendUserMessageInput(session_id="sesn_missing", content="hi"))


def test_send_message_emits_user_message_event():
    repo = FakeRepo()
    sessions = {"sesn_msg": _make_session()}
    sse_queues: dict = {}

    async def fake_launcher_run(prompt, workspace, emit):
        pass

    class FakeLauncher:
        async def run(self, prompt, workspace, emit):
            pass

    uc = SendUserMessageUseCase(
        repo=repo,
        sessions_index=sessions,
        sse_queues=sse_queues,
        get_launcher=lambda name: FakeLauncher(),
    )

    # execute() creates an asyncio task — run in event loop
    async def run():
        uc.execute(SendUserMessageInput(session_id="sesn_msg", content="hello"))
        # Let the task run
        await asyncio.sleep(0.05)

    asyncio.get_event_loop().run_until_complete(run())

    user_msg_events = [e for e in repo.events if e["type"] == "user.message"]
    assert len(user_msg_events) == 1
    assert user_msg_events[0]["content"] == "hello"


def test_redact_tokens_replaces_in_string_values():
    data = {"line": "output containing ghp_secret and more"}
    result = _redact_tokens(data, ["ghp_secret"])
    assert "ghp_secret" not in result["line"]
    assert "[REDACTED]" in result["line"]


def test_redact_tokens_leaves_non_string_values_unchanged():
    data = {"count": 42, "flag": True}
    result = _redact_tokens(data, ["ghp_secret"])
    assert result["count"] == 42
    assert result["flag"] is True


def test_redact_tokens_empty_tokens_returns_same():
    data = {"line": "nothing to redact"}
    result = _redact_tokens(data, [])
    assert result == data
