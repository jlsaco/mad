from __future__ import annotations

from mad.providers.base import LLMProvider, ProviderResponse


class ClaudeCLIProvider(LLMProvider):
    async def complete(self, system: str, messages: list[dict], tools: list[dict]) -> ProviderResponse:
        raise NotImplementedError("ClaudeCLIProvider not implemented in MVP")
