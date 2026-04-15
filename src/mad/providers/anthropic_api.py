from __future__ import annotations

from mad.providers.base import LLMProvider, ProviderResponse


class AnthropicAPIProvider(LLMProvider):
    async def complete(self, system: str, messages: list[dict], tools: list[dict]) -> ProviderResponse:
        raise NotImplementedError("AnthropicAPIProvider not implemented in MVP")
