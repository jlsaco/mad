"""DEPRECATED shim — implementation moved to mad.adapters.outbound.persistence.local_workspace_provisioner.

This module re-exports everything for backwards compatibility until Phase 6.
Do not import this module in new code.
"""
from __future__ import annotations

from mad.adapters.outbound.persistence.local_workspace_provisioner import (
    LocalWorkspaceProvisioner,
    local_path_for_mount,
    provision_file,
    provision_github_repo,
    workspace_path,
)

__all__ = [
    "LocalWorkspaceProvisioner",
    "local_path_for_mount",
    "provision_file",
    "provision_github_repo",
    "workspace_path",
]
