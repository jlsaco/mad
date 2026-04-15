from __future__ import annotations

from collections import deque

from mad.providers.base import LLMProvider, ProviderResponse


class FakeScriptedProvider(LLMProvider):
    """Test double that replays a pre-recorded sequence of ProviderResponses."""

    def __init__(self) -> None:
        self._queue: deque[ProviderResponse] = deque()

    def script(self, responses: list[ProviderResponse]) -> None:
        self._queue = deque(responses)

    async def complete(self, system: str, messages: list[dict], tools: list[dict]) -> ProviderResponse:
        if not self._queue:
            return ProviderResponse(text="(fake provider exhausted)", stop_reason="end_turn")
        return self._queue.popleft()
