from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import HTTPException

WORKSPACE_PREFIX = "/workspace"


def validate_mount_path(mount_path: str) -> None:
    """Reject any mount_path that doesn't resolve inside /workspace.

    Enforces CLAUDE.md hard rule 3 (path traversal prevention).
    """
    if not mount_path.startswith("/"):
        raise HTTPException(status_code=400, detail=f"mount_path {mount_path!r} must be absolute")
    pure = PurePosixPath(mount_path)
    stack: list[str] = []
    for part in pure.parts[1:]:
        if part == "..":
            if not stack:
                raise HTTPException(status_code=400, detail=f"mount_path {mount_path!r} escapes workspace")
            stack.pop()
        elif part and part != ".":
            stack.append(part)
    logical = "/" + "/".join(stack)
    if not (logical == WORKSPACE_PREFIX or logical.startswith(WORKSPACE_PREFIX + "/")):
        raise HTTPException(status_code=400, detail=f"mount_path {mount_path!r} escapes workspace")
