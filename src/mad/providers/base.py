"""Backwards-compatibility shim for AgentLauncher.

The authoritative definition now lives in mad.core.ports.outbound.agent_launcher.
This module re-exports it so existing imports keep working until Phase 5.

# DEPRECATED: re-export, will move in Phase 5
"""
from __future__ import annotations

from mad.core.ports.outbound.agent_launcher import AgentLauncher

__all__ = ["AgentLauncher"]
