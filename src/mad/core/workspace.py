"""DEPRECATED shim — implementation moved to mad.adapters.outbound.persistence.local_workspace_provisioner.

This module re-exports everything for backwards compatibility until Phase 6.
Do not import this module in new code.
"""
from __future__ import annotations

from mad.adapters.outbound.persistence.local_workspace_provisioner import (
    local_path_for_mount,
    workspace_path,
)

__all__ = ["local_path_for_mount", "workspace_path"]
