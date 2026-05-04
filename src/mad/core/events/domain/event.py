"""Event domain entity for the cross-session events module.

The events module accepts and emits Mad's existing vocabulary verbatim
(ADR-0004): ``session.created``, ``user.message``, ``session.status_running``,
``agent.output``, ``session.status_idle``, ``session.error``. ``type`` is
left as a free-form string deliberately so new vocabulary can be added
without changing this entity.

``event_id`` may be ``None`` for events written before UUIDv7 minting was
introduced (ADR-0005). The query layer surfaces such events as-is until
they age out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Event:
    """A single observation in Mad's persisted event log."""

    event_id: UUID | None
    session_id: str
    type: str
    data: dict[str, Any]
    timestamp: datetime
