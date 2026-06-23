"""Rate-limit retry re-gates on the work window (issue #79).

Before #79 a rate-limited retry would relaunch the agent on the backoff
schedule even if the session's ``WorkWindowPolicy`` window had closed in
the meantime — so a run that started inside the window could resume
*outside* it. The fix re-checks ``WorkWindowPolicy.is_open`` at the
moment the dispatcher would relaunch (before and after the backoff
sleep); if the window is shut it emits ``task.deferred`` and returns the
task to the queue instead of running the agent outside the window.

These tests pin that behavior end-to-end against the real ``Dispatcher``,
``InMemoryEventBus``, ``InMemoryTaskProjection``, and ``EventEmitter`` —
only the clock (``FakeClock``, manually advanced so the window can be
closed at a controlled instant) and the launcher (``ScriptedLauncher``,
scripted to raise ``RateLimitError``) are doubled.

The harness mirrors ``test_dispatcher_dst.py`` and is self-contained per
that file's convention. State-based polling only (``_wait_for_event_type``
/ ``_wait_for_event_absent``); backoff is monkeypatched to ~0 s so the
only governing delay is the rate-limit floor, keeping each test well
under the 15 s ``pytest-timeout`` cap (heuristics 7 and 8).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from datetime import time as dtime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from mad.adapters.outbound.events.in_memory_event_bus import InMemoryEventBus
from mad.adapters.outbound.orchestration.projection import InMemoryTaskProjection
from mad.core.events.emitter import EventEmitter
from mad.core.orchestration.domain.dispatch_policy import (
    ImmediatePolicy,
    Window,
    WorkWindowPolicy,
)
from mad.core.orchestration.domain.exceptions.rate_limit import RateLimitError
from mad.core.orchestration.use_cases.dispatcher import Dispatcher
from mad.core.orchestration.use_cases.enqueue_task import (
    EnqueueTaskInput,
    EnqueueTaskUseCase,
)
from mad.core.sessions.domain.entities.session import Session
from support.clock import FakeClock
from support.events import FakeEventStore
from support.launchers import ScriptedLauncher

_DEADLINE_S = 5.0
# Open 01:00-02:00 UTC so "inside" / "outside" the window is trivial to
# reason about: 01:30 is in, 02:30 is out.
_WINDOW = Window(start=dtime(1, 0), end=dtime(2, 0), timezone=ZoneInfo("UTC"))
_INSIDE = datetime(1970, 1, 2, 1, 30, tzinfo=UTC)
_OUTSIDE = datetime(1970, 1, 2, 2, 30, tzinfo=UTC)
_IDLE: dict = {"type": "session.status_idle", "stop_reason": "end_turn"}


def _session(workspace: Path, policy: WorkWindowPolicy | ImmediatePolicy | None) -> Session:
    s = Session(
        session_id="sesn_a",
        agent={"name": "test", "provider": "fake"},
        workspace=str(workspace),
        tokens_to_redact=[],
    )
    s.dispatch_policy = policy
    return s


async def _wait_for_event_type(
    store: FakeEventStore,
    *,
    session_id: str,
    event_type: str,
    deadline: float = _DEADLINE_S,
) -> None:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if any(c for c in store.calls if c[0] == session_id and c[1] == event_type):
            return
        await asyncio.sleep(0.01)
    types = [c[1] for c in store.calls if c[0] == session_id]
    pytest.fail(f"timeout waiting for {event_type!r} on {session_id}; got {types}")


async def _wait_for_event_absent(
    store: FakeEventStore,
    *,
    session_id: str,
    event_type: str,
    deadline: float = 0.3,
) -> None:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if any(c for c in store.calls if c[0] == session_id and c[1] == event_type):
            pytest.fail(f"unexpected {event_type!r} on {session_id}")
        await asyncio.sleep(0.01)


def _build_dispatcher(
    sessions: dict[str, Session],
    launcher: ScriptedLauncher,
    clock: FakeClock,
    *,
    tick_interval_s: float = 0.05,
) -> tuple[Dispatcher, EventEmitter, FakeEventStore, InMemoryEventBus, EnqueueTaskUseCase]:
    store = FakeEventStore()
    bus = InMemoryEventBus()
    projection = InMemoryTaskProjection()
    emitter = EventEmitter(store=store, bus=bus)

    def factory(_name: str) -> Any:
        return launcher

    factory_typed: Callable[[str], Any] = factory
    dispatcher = Dispatcher(
        projection=projection,
        emitter=emitter,
        bus=bus,
        sessions_index=sessions,
        get_launcher=factory_typed,
        clock=clock,
        tick_interval_s=tick_interval_s,
    )
    enqueue = EnqueueTaskUseCase(sessions_index=sessions, emitter=emitter)
    return dispatcher, emitter, store, bus, enqueue


def _force_fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collapse the exponential schedule to ~0 s so only an explicit
    rate-limit floor governs the sleep — keeps the tests fast and makes
    the floor the single lever for the window-closing race in test #1."""
    import mad.core.orchestration.domain.retry_schedule as sched

    monkeypatch.setattr(sched, "_BASE_S", 0.01)
    monkeypatch.setattr(sched, "_JITTER_FRACTION", 0.0)
    monkeypatch.setattr(sched, "_MIN_BACKOFF_S", 0.0)


# -- Tests ------------------------------------------------------------------


async def test_window_closing_during_backoff_defers_instead_of_running_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Core AC (issue #79): a run starts inside the 01:00-02:00 UTC window,
    the primary launch rate-limits, and the window closes *during* the
    backoff sleep. The dispatcher MUST defer the task (emit ``task.deferred``
    with ``reason="work_window_closed"``) and return it to the queue rather
    than relaunch the agent outside the window.

    The single scripted run (``script_raising`` with one ``RateLimitError``)
    is the regression guard: a second launcher call would mean the
    dispatcher relaunched outside the window (the pre-#79 bug) — or
    livelocked re-dispatching into a still-open window."""
    _force_fast_backoff(monkeypatch)

    workspace = tmp_path / "ws"
    workspace.mkdir()
    policy = WorkWindowPolicy(windows=(_WINDOW,))
    sessions = {"sesn_a": _session(workspace, policy)}
    launcher = ScriptedLauncher()
    # Exactly ONE scripted entry: the primary launch raises. After the defer
    # there must be NO second launch. The 0.3 s floor governs the sleep
    # (backoff is ~0), giving a comfortable window to close the clock.
    launcher.script_raising(
        [RateLimitError(captured_id=None, reason="rate_limit", retry_after_floor_s=0.3)]
    )

    # Clock starts INSIDE the window so the initial dispatch is allowed.
    clock = FakeClock(_INSIDE)
    dispatcher, _, store, _, enqueue = _build_dispatcher(sessions, launcher, clock)

    await dispatcher.start()
    try:
        await enqueue.execute(EnqueueTaskInput(session_id="sesn_a", content="overnight"))
        # The primary launch raises → task.retrying is emitted right before
        # the backoff sleep. Wait for it, THEN close the window so the
        # post-sleep re-gate (issue #79 part 2) sees a shut window.
        await _wait_for_event_type(store, session_id="sesn_a", event_type="task.retrying")
        clock.set(_OUTSIDE)

        # The post-sleep window check defers the task.
        await _wait_for_event_type(store, session_id="sesn_a", event_type="task.deferred")

        deferred = next(c for c in store.calls if c[0] == "sesn_a" and c[1] == "task.deferred")
        assert deferred[2]["reason"] == "work_window_closed"
        assert deferred[2]["scheduled_for"] is not None

        # The agent did NOT relaunch outside the window: exactly one call.
        assert len(launcher.calls) == 1

        # Terminal completion/failure must NOT fire — the task was returned
        # to the queue, not finished.
        await _wait_for_event_absent(store, session_id="sesn_a", event_type="task.completed")
        completed = [c for c in store.calls if c[0] == "sesn_a" and c[1] == "task.completed"]
        assert not completed
        failed = [c for c in store.calls if c[0] == "sesn_a" and c[1] == "task.failed"]
        assert not failed

        # The projection moved the task back to the head of the queue.
        queued_task_id = deferred[2]["task_id"]
        projection = dispatcher._projection
        assert projection.in_flight("sesn_a") is None
        requeued = projection.queued("sesn_a")
        assert [str(t.task_id) for t in requeued] == [queued_task_id]
    finally:
        await dispatcher.stop()


async def test_window_staying_open_retries_normally_no_defer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative twin to the core AC: the window stays open across the whole
    retry, so the rate limit is retried normally and the task completes.
    Proves the defer in test #1 fires *because the window closed*, not on
    every rate limit under a ``WorkWindowPolicy``."""
    _force_fast_backoff(monkeypatch)

    workspace = tmp_path / "ws"
    workspace.mkdir()
    policy = WorkWindowPolicy(windows=(_WINDOW,))
    sessions = {"sesn_a": _session(workspace, policy)}
    launcher = ScriptedLauncher()
    # Primary raises, retry succeeds, auto-sync succeeds. No floor → the
    # ~0 s backoff governs, and the window is open at both re-gate checks.
    launcher.script_raising(
        [
            RateLimitError(captured_id=None, reason="rate_limit"),
            ([_IDLE], None),
            ([_IDLE], None),
        ]
    )

    # Clock stays INSIDE the window for the whole test — never advanced.
    clock = FakeClock(_INSIDE)
    dispatcher, _, store, _, enqueue = _build_dispatcher(sessions, launcher, clock)

    await dispatcher.start()
    try:
        await enqueue.execute(EnqueueTaskInput(session_id="sesn_a", content="overnight"))
        await _wait_for_event_type(store, session_id="sesn_a", event_type="task.retrying")
        await _wait_for_event_type(store, session_id="sesn_a", event_type="task.completed")

        # task.deferred must NOT appear — the window never closed.
        deferred = [c for c in store.calls if c[0] == "sesn_a" and c[1] == "task.deferred"]
        assert not deferred
    finally:
        await dispatcher.stop()


async def test_immediate_policy_rate_limit_does_not_defer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative twin to the core AC (policy gate): a session on
    ``ImmediatePolicy`` with a clock wired retries the rate limit normally
    and completes — defer is ``WorkWindowPolicy``-specific. Proves the
    re-gate in test #1 is gated on the policy type, not merely on a clock
    being present."""
    _force_fast_backoff(monkeypatch)

    workspace = tmp_path / "ws"
    workspace.mkdir()
    sessions = {"sesn_a": _session(workspace, ImmediatePolicy())}
    launcher = ScriptedLauncher()
    launcher.script_raising(
        [
            RateLimitError(captured_id=None, reason="rate_limit"),
            ([_IDLE], None),
            ([_IDLE], None),
        ]
    )

    # A clock IS wired (so the only thing keeping defer off is the policy).
    clock = FakeClock(_INSIDE)
    dispatcher, _, store, _, enqueue = _build_dispatcher(sessions, launcher, clock)

    await dispatcher.start()
    try:
        await enqueue.execute(EnqueueTaskInput(session_id="sesn_a", content="work"))
        await _wait_for_event_type(store, session_id="sesn_a", event_type="task.retrying")
        await _wait_for_event_type(store, session_id="sesn_a", event_type="task.completed")

        # Even with a clock wired, an ImmediatePolicy never defers.
        deferred = [c for c in store.calls if c[0] == "sesn_a" and c[1] == "task.deferred"]
        assert not deferred
    finally:
        await dispatcher.stop()
