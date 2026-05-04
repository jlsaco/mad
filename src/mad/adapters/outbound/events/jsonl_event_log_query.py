"""JSONL-backed ``EventLogQuery`` implementation.

Reads from the same ``sessions/*.jsonl`` files that
``JsonlSessionRepository`` writes (CLAUDE.md hard rule 6 — single source
of truth). For v1 Mad volume the implementation loads + sorts in
memory; ADR-0004 records the migration path to a streaming/indexed
store when this becomes a hotspot.

Sort key is the textual ``event_id`` (UUIDv7 → lex order = mint order
across milliseconds). Pre-existing events without an ``event_id`` sort
first (treated as "older than any known id"), per ADR-0005.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from mad.adapters.outbound.persistence import jsonl_session_repository as _persistence
from mad.core.events.domain.event import Event
from mad.core.events.ports.event_log_query import EventQuery

_META_KEYS = frozenset({"event_id", "type", "timestamp"})


class JsonlEventLogQuery:
    """Read-side query over ``sessions/*.jsonl``."""

    def __init__(self, sessions_dir: Path | None = None) -> None:
        self._explicit_sessions_dir = sessions_dir

    @property
    def _sessions_dir(self) -> Path:
        # Read SESSIONS_DIR lazily so tests that monkeypatch it after
        # construction (via tmp_sessions_dir) still take effect.
        if self._explicit_sessions_dir is not None:
            return self._explicit_sessions_dir
        return _persistence.SESSIONS_DIR

    def query(self, q: EventQuery) -> list[Event]:
        events = [e for e in self._all_events() if _matches(e, q)]
        events.sort(key=_sort_key)
        return events[: q.limit]

    def session_ids_for_agent(self, agent_name: str) -> frozenset[str]:
        return frozenset(
            event.session_id
            for event in self._all_events()
            if event.type == "session.created" and event.data.get("agent") == agent_name
        )

    def _all_events(self) -> Iterator[Event]:
        if not self._sessions_dir.exists():
            return
        for path in sorted(self._sessions_dir.glob("*.jsonl")):
            session_id = path.stem
            for raw_line in path.read_text().splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                yield _to_event(json.loads(line), session_id)


def _to_event(raw: dict, session_id: str) -> Event:
    eid_str = raw.get("event_id")
    eid = UUID(eid_str) if isinstance(eid_str, str) and eid_str else None
    ts_str = raw.get("timestamp")
    if isinstance(ts_str, str) and ts_str:
        ts = datetime.fromisoformat(ts_str)
    else:
        ts = datetime.fromtimestamp(0, tz=UTC)
    type_ = raw.get("type", "")
    data = {k: v for k, v in raw.items() if k not in _META_KEYS}
    return Event(
        event_id=eid,
        session_id=session_id,
        type=type_,
        data=data,
        timestamp=ts,
    )


def _matches(event: Event, q: EventQuery) -> bool:
    if q.session_id is not None and event.session_id != q.session_id:
        return False
    if q.kind is not None and event.type != q.kind:
        return False
    if (
        q.session_ids_for_agent is not None
        and event.session_id not in q.session_ids_for_agent
    ):
        return False
    if q.since is not None and event.timestamp < q.since:
        return False
    return not (
        q.after_event_id is not None
        and (event.event_id is None or event.event_id <= q.after_event_id)
    )


def _sort_key(event: Event) -> tuple[str, datetime]:
    """Lex-sortable key. Legacy events without an id sort first."""
    eid_str = str(event.event_id) if event.event_id is not None else ""
    return (eid_str, event.timestamp)
