from __future__ import annotations

from mad.core.ports.outbound.agent_launcher import AgentLauncher
from mad.providers.claude_cli import ClaudeCLIProvider


def get_launcher(name: str) -> AgentLauncher:
    if name == "claude_cli":
        return ClaudeCLIProvider()
    raise NotImplementedError(f"Unknown launcher: {name!r}")
