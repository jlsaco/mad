"""AgentEvent value object.

Represents a single event in the agent session event stream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentEvent:
    """Immutable representation of a session event.

    type: the event type string (e.g. 'agent.output', 'session.status_idle')
    data: optional dict of event-specific data
    timestamp: ISO-8601 string (set by the log layer)
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the dict format stored in JSONL."""
        d: dict[str, Any] = {"type": self.type}
        if self.timestamp:
            d["timestamp"] = self.timestamp
        d.update(self.data)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentEvent:
        """Reconstruct from a JSONL event dict."""
        event_type = d.get("type", "")
        timestamp = d.get("timestamp", "")
        data = {k: v for k, v in d.items() if k not in ("type", "timestamp")}
        return cls(type=event_type, data=data, timestamp=timestamp)
