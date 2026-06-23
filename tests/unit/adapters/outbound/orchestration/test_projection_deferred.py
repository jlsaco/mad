"""Unit tests for ``InMemoryTaskProjection._on_deferred`` (issue #79).

``task.deferred`` is the projection-side half of the work-window re-gate:
when the dispatcher declines to relaunch a rate-limited task outside its
window, it emits ``task.deferred`` and the projection returns the task
from ``in_flight`` to the *head* of ``queued`` — preserving the original
``Task`` (so ``created_at`` / FIFO / priority ordering survive) and
clearing any ``retry_info`` left over from the rate-limit attempt.

These build ``Event`` objects directly and drive ``apply`` for the
deferred path, mirroring the self-contained ``_event`` helper style of
``tests/integration/adapters/orchestration/test_projection.py``.
Heuristic 1 — the happy path (deferral of the in-flight task) has a
negative twin (deferral of a task that is *not* in flight is a no-op).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from mad.adapters.outbound.orchestration.projection import InMemoryTaskProjection
from mad.core.events.domain.event import Event

_QUEUED_AT = datetime(2026, 5, 8, 1, 30, tzinfo=UTC)


def _event(
    *,
    type: str,
    session_id: str,
    task_id: UUID,
    content: str = "opaque",
    scheduled_for: str = "now",
    attempt: int | None = None,
    retry_after_s: float | None = None,
    reason: str | None = None,
    timestamp: datetime = _QUEUED_AT,
) -> Event:
    data: dict[str, Any] = {"task_id": str(task_id)}
    if type == "task.queued":
        data["content"] = content
        data["scheduled_for"] = scheduled_for
    if type == "task.retrying":
        data["attempt"] = attempt
        data["retry_after_s"] = retry_after_s
        data["reason"] = reason
    if type == "task.deferred":
        data["reason"] = reason if reason is not None else "work_window_closed"
        data["scheduled_for"] = scheduled_for
    return Event(
        event_id=uuid4(),
        session_id=session_id,
        type=type,
        data=data,
        timestamp=timestamp,
    )


def test_on_deferred_moves_in_flight_back_to_queue() -> None:
    """``task.deferred`` for the in-flight task returns it to the head of
    the queue with its original identity and ``created_at`` intact, and
    clears the ``retry_info`` set by the preceding ``task.retrying``."""
    proj = InMemoryTaskProjection()
    sid = "sesn_a"
    task_id = uuid4()

    proj.apply(_event(type="task.queued", session_id=sid, task_id=task_id, content="overnight"))
    proj.apply(_event(type="task.dispatched", session_id=sid, task_id=task_id))
    proj.apply(
        _event(
            type="task.retrying",
            session_id=sid,
            task_id=task_id,
            attempt=1,
            retry_after_s=0.3,
            reason="rate_limit",
        )
    )
    # Pre-conditions: the task is in flight and retry_info is populated.
    assert proj.in_flight(sid) is not None
    assert proj.retry_info(sid) is not None

    proj.apply(_event(type="task.deferred", session_id=sid, task_id=task_id))

    # Slot freed.
    assert proj.in_flight(sid) is None
    # Returned to the queue with identity and created_at preserved
    # (the original Task object, not a fresh one stamped at defer time).
    requeued = proj.queued(sid)
    assert [t.task_id for t in requeued] == [task_id]
    assert requeued[0].created_at == _QUEUED_AT
    assert requeued[0].content == "overnight"
    # retry_info cleared so the next dispatch starts a clean attempt count.
    assert proj.retry_info(sid) is None


def test_on_deferred_at_head_preserves_existing_queue_order() -> None:
    """The deferred task is reinserted at the *head* of the queue, ahead of
    any task that was queued behind it — so it is the next candidate when
    the window reopens (its original FIFO position)."""
    proj = InMemoryTaskProjection()
    sid = "sesn_a"
    flying = uuid4()
    waiting = uuid4()

    proj.apply(_event(type="task.queued", session_id=sid, task_id=flying, content="first"))
    proj.apply(_event(type="task.queued", session_id=sid, task_id=waiting, content="second"))
    proj.apply(_event(type="task.dispatched", session_id=sid, task_id=flying))
    # Now: flying is in_flight, waiting is the sole queued task.
    assert [t.task_id for t in proj.queued(sid)] == [waiting]

    proj.apply(_event(type="task.deferred", session_id=sid, task_id=flying))

    assert proj.in_flight(sid) is None
    assert [t.task_id for t in proj.queued(sid)] == [flying, waiting]


def test_on_deferred_for_non_in_flight_task_is_noop() -> None:
    """Negative twin: ``task.deferred`` naming a task that is NOT the
    in-flight one leaves both the in-flight slot and the queue untouched.
    Pins the projection guard so a stray/duplicate deferral cannot evict
    the real in-flight task or inject a phantom queued entry."""
    proj = InMemoryTaskProjection()
    sid = "sesn_a"
    flying = uuid4()
    other = uuid4()

    proj.apply(_event(type="task.queued", session_id=sid, task_id=flying, content="real"))
    proj.apply(_event(type="task.dispatched", session_id=sid, task_id=flying))
    assert proj.in_flight(sid) is not None
    assert proj.queued(sid) == []

    proj.apply(_event(type="task.deferred", session_id=sid, task_id=other))

    # In-flight slot unchanged (still the original task), queue still empty.
    in_flight = proj.in_flight(sid)
    assert in_flight is not None
    assert in_flight.task_id == flying
    assert proj.queued(sid) == []
