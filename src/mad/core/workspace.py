from __future__ import annotations

import tempfile
from pathlib import Path


def workspace_path(session_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"mad_{session_id}"


def local_path_for_mount(session_id: str, mount_path: str) -> Path:
    """Map a /workspace/... mount_path into the real temp workspace directory."""
    relative = mount_path.lstrip("/")
    if relative.startswith("workspace/") or relative == "workspace":
        relative = relative[len("workspace"):]
    relative = relative.lstrip("/")
    base = workspace_path(session_id)
    if relative:
        return base / relative
    return base
