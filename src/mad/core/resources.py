from __future__ import annotations

import shutil
import subprocess

from mad.core.workspace import local_path_for_mount


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
