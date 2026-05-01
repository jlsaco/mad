"""DEPRECATED shim — will be removed in Phase 6.

Imports re-exported here for backwards compatibility only.
Use mad.adapters.outbound.agents.* directly.
"""
from __future__ import annotations

from mad.adapters.outbound.agents import factory
from mad.adapters.outbound.agents.factory import get_launcher
from mad.core.ports.outbound.agent_launcher import AgentLauncher

__all__ = ["AgentLauncher", "get_launcher", "factory"]
