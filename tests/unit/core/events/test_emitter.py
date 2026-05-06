"""Unit tests for EventEmitter.

EventEmitter is the single write gateway for the session log.
Every event MUST be persisted before it is published.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from mad.core.events.domain.event import Event
from mad.core.events.emitter import EventEmitter

# ---------------------------------------------------------------------------
# Test-local fakes
# ---------------------------------------------------------------------------


class FakeEventStore:
    """Records append calls and returns a typed Event."""

    def __init__(self, *, raise_on_append: Exception | None = None) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []
        self._raise = raise_on_append

    def append(
        self,
        session_id: str,
        type: str,
        data: dict[str, Any] | None = None,
    ) -> Event:
        if self._raise is not None:
            raise self._raise
        self.calls.append((session_id, type, data))
        return Event(
            event_id=UUID("00000000-0000-0000-0000-000000000001"),
            session_id=session_id,
            type=type,
            data=data or {},
            timestamp=__import__("datetime").datetime(
                2025, 1, 1, tzinfo=__import__("datetime").timezone.utc
            ),
        )


class FakeEventBus:
    """Records publish calls."""

    def __init__(self) -> None:
        self.published: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.published.append(event)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_emit_calls_store_append_once():
    """emit() must call store.append exactly once with the same args."""
    store = FakeEventStore()
    bus = FakeEventBus()
    emitter = EventEmitter(store=store, bus=bus)

    await emitter.emit("sesn_abc", "session.created", {"agent": "claude_cli"})

    assert len(store.calls) == 1
    sid, typ, data = store.calls[0]
    assert sid == "sesn_abc"
    assert typ == "session.created"
    assert data == {"agent": "claude_cli"}


async def test_emit_calls_bus_publish_once_with_store_event():
    """emit() must call bus.publish exactly once with the Event returned by the store."""
    store = FakeEventStore()
    bus = FakeEventBus()
    emitter = EventEmitter(store=store, bus=bus)

    await emitter.emit("sesn_abc", "agent.output", {"line": "hello"})

    assert len(bus.published) == 1
    assert bus.published[0].session_id == "sesn_abc"
    assert bus.published[0].type == "agent.output"
    assert bus.published[0].data == {"line": "hello"}


async def test_emit_returns_the_event_from_store():
    """emit() must return the Event returned by store.append."""
    store = FakeEventStore()
    bus = FakeEventBus()
    emitter = EventEmitter(store=store, bus=bus)

    result = await emitter.emit("sesn_xyz", "user.message", {"content": "hi"})

    assert isinstance(result, Event)
    assert result.session_id == "sesn_xyz"
    assert result.type == "user.message"


async def test_emit_does_not_publish_when_store_raises():
    """If store.append raises, bus.publish must NOT be called (persist first)."""
    store = FakeEventStore(raise_on_append=RuntimeError("disk full"))
    bus = FakeEventBus()
    emitter = EventEmitter(store=store, bus=bus)

    with pytest.raises(RuntimeError, match="disk full"):
        await emitter.emit("sesn_err", "session.error", {"error": "boom"})

    assert len(bus.published) == 0, "bus.publish must not be called when store.append raises"
