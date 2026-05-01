from __future__ import annotations

import shutil
import subprocess
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


def _resolve_mount(workspace: Path, mount_path: str) -> Path:
    """Resolve mount_path relative to workspace, stripping leading /workspace/."""
    relative = mount_path.lstrip("/")
    if relative.startswith("workspace/") or relative == "workspace":
        relative = relative[len("workspace"):]
    relative = relative.lstrip("/")
    if relative:
        return workspace / relative
    return workspace


def provision_github_repo(session_id: str, resource: dict) -> dict:
    url: str = resource["url"]
    mount_path: str = resource["mount_path"]
    token: str | None = resource.get("authorization_token")
    checkout: dict | None = resource.get("checkout")

    local_path = local_path_for_mount(session_id, mount_path)
    local_path.mkdir(parents=True, exist_ok=True)

    clone_url = url
    if token and url.startswith("https://"):
        clone_url = url.replace("https://", f"https://{token}@", 1)

    cmd = ["git", "clone", "-q", clone_url, str(local_path)]
    if checkout and checkout.get("type") == "branch":
        cmd = ["git", "clone", "-q", "-b", checkout["name"], clone_url, str(local_path)]

    shutil.rmtree(local_path)
    subprocess.run(cmd, check=True, capture_output=True)

    # Strip token from remote after clone (CLAUDE.md hard rule 2)
    subprocess.run(
        ["git", "-C", str(local_path), "remote", "set-url", "origin", url],
        check=True,
        capture_output=True,
    )

    return {
        "type": "github_repository",
        "url": url,
        "mount_path": mount_path,
        "local_path": str(local_path),
        "status": "cloned",
    }


def provision_file(session_id: str, resource: dict) -> dict:
    mount_path: str = resource["mount_path"]
    content: str = resource.get("content", "")
    local_path = local_path_for_mount(session_id, mount_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(content)
    return {
        "type": "file",
        "mount_path": mount_path,
        "local_path": str(local_path),
        "status": "written",
    }


class LocalWorkspaceProvisioner:
    """Concrete implementation of ``WorkspaceProvisioner`` using the local filesystem."""

    def create(self, session_id: str) -> Path:
        """Return (and create if necessary) the temp workspace for a session."""
        path = workspace_path(session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def destroy(self, session_id: str) -> None:
        """Remove the workspace directory if it exists."""
        path = workspace_path(session_id)
        if path.exists():
            shutil.rmtree(path)

    def materialize_github_repo(
        self,
        workspace: Path,
        mount_path: str,
        repo_url: str,
        token: str | None,
    ) -> None:
        """Clone repo_url into workspace at mount_path, stripping the token afterwards."""
        local_path = _resolve_mount(workspace, mount_path)
        local_path.mkdir(parents=True, exist_ok=True)

        clone_url = repo_url
        if token and repo_url.startswith("https://"):
            clone_url = repo_url.replace("https://", f"https://{token}@", 1)

        cmd = ["git", "clone", "-q", clone_url, str(local_path)]
        shutil.rmtree(local_path)
        subprocess.run(cmd, check=True, capture_output=True)

        # Strip token from remote after clone (CLAUDE.md hard rule 2)
        subprocess.run(
            ["git", "-C", str(local_path), "remote", "set-url", "origin", repo_url],
            check=True,
            capture_output=True,
        )

    def materialize_file(
        self,
        workspace: Path,
        mount_path: str,
        content: str,
    ) -> None:
        """Write content to workspace at mount_path."""
        local_path = _resolve_mount(workspace, mount_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(content)
