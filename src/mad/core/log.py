from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SESSIONS_DIR = Path("sessions")


def ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(exist_ok=True)


def log_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.jsonl"


def emit(session_id: str, event_type: str, data: dict[str, Any] | None = None) -> dict:
    """Print an event to stdout AND append it to the session JSONL log.

    The log is the source of truth (CLAUDE.md hard rule 6).
    """
    event = {"type": event_type, "timestamp": datetime.now(timezone.utc).isoformat()}
    if data:
        event.update(data)
    line = json.dumps(event)
    print(line)
    ensure_sessions_dir()
    with log_path(session_id).open("a") as f:
        f.write(line + "\n")
    return event


def get_events(session_id: str) -> list[dict]:
    p = log_path(session_id)
    if not p.exists():
        return []
    events: list[dict] = []
    for ln in p.read_text().splitlines():
        ln = ln.strip()
        if ln:
            events.append(json.loads(ln))
    return events
