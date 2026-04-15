from __future__ import annotations

from mad.providers.anthropic_api import AnthropicAPIProvider
from mad.providers.base import LLMProvider
from mad.providers.claude_cli import ClaudeCLIProvider


def get_provider(name: str) -> LLMProvider:
    if name == "claude_cli":
        return ClaudeCLIProvider()
    if name == "anthropic_api":
        return AnthropicAPIProvider()
    raise NotImplementedError(f"Unknown provider: {name!r}")
