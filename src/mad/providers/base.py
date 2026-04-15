from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolUse:
    id: str
    name: str
    input: dict


@dataclass
class ProviderResponse:
    text: str | None = None
    tool_uses: list[ToolUse] = field(default_factory=list)
    stop_reason: str = "end_turn"


class LLMProvider(Protocol):
    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
    ) -> ProviderResponse: ...
