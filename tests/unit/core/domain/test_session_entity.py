"""Unit tests for the Session entity.

Validates state transitions and invariants.
No HTTP, no I/O — pure domain logic.
"""
from __future__ import annotations

from mad.core.domain.entities.session import Session


def _make_session(**kwargs) -> Session:
    defaults = dict(
        session_id="sesn_test001",
        agent={"name": "test", "provider": "fake"},
        workspace="/tmp/mad_sesn_test001",
    )
    defaults.update(kwargs)
    return Session(**defaults)


def test_initial_status_is_created():
    s = _make_session()
    assert s.status == "created"


def test_mark_running_transitions_to_running():
    s = _make_session()
    s.mark_running()
    assert s.status == "running"


def test_mark_idle_transitions_to_idle():
    s = _make_session()
    s.mark_running()
    s.mark_idle()
    assert s.status == "idle"


def test_mark_error_transitions_to_error():
    s = _make_session()
    s.mark_running()
    s.mark_error(reason="timeout")
    assert s.status == "error"


def test_mark_deleted_transitions_to_deleted():
    s = _make_session()
    s.mark_running()
    s.mark_deleted()
    assert s.status == "deleted"


def test_to_dict_excludes_tokens():
    s = _make_session(tokens_to_redact=["ghp_secret"])
    d = s.to_dict()
    assert "tokens_to_redact" not in d
    raw = str(d)
    assert "ghp_secret" not in raw


def test_from_dict_round_trip():
    s = _make_session(status="idle")
    d = s.to_dict()
    s2 = Session.from_dict(d)
    assert s2.session_id == s.session_id
    assert s2.status == "idle"
    assert s2.workspace == s.workspace


def test_resources_mounted_defaults_to_empty_list():
    s = _make_session()
    assert s.resources_mounted == []
