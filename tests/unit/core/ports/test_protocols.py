"""Tests that concrete implementations satisfy the outbound port Protocols.

Only imports from mad.core.ports and the adapter implementations — no HTTP.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mad.core.log import JsonlSessionRepository
from mad.core.ports import AgentLauncher, SessionRepository, WorkspaceProvisioner
from mad.core.resources import LocalWorkspaceProvisioner
from mad.providers.fake import FakeLauncher


# ---------------------------------------------------------------------------
# AgentLauncher port
# ---------------------------------------------------------------------------


class TestAgentLauncherPort:
    def test_fake_launcher_is_agent_launcher(self):
        launcher = FakeLauncher()
        assert isinstance(launcher, AgentLauncher)

    def test_fake_launcher_has_run_method(self):
        launcher = FakeLauncher()
        assert hasattr(launcher, "run")
        assert callable(launcher.run)

    def test_fake_launcher_satisfies_typed_variable(self):
        """Structural check: assignment to AgentLauncher-typed var works."""
        launcher: AgentLauncher = FakeLauncher()
        assert launcher is not None

    def test_fake_launcher_run_emits_events(self):
        """Verify FakeLauncher.run actually invokes the emit callback."""
        launcher = FakeLauncher()
        launcher.script([[{"type": "agent.output", "text": "hi"}]])

        emitted: list[tuple[str, dict | None]] = []

        async def _emit(event_type: str, data: dict | None = None) -> None:
            emitted.append((event_type, data))

        workspace = Path("/tmp/test_workspace")

        asyncio.get_event_loop().run_until_complete(
            launcher.run(prompt="hello", workspace=workspace, emit=_emit)
        )
        assert len(emitted) == 1
        assert emitted[0][0] == "agent.output"


# ---------------------------------------------------------------------------
# SessionRepository port
# ---------------------------------------------------------------------------


class TestSessionRepositoryPort:
    def test_jsonl_repo_is_session_repository(self):
        repo = JsonlSessionRepository()
        assert isinstance(repo, SessionRepository)

    def test_jsonl_repo_has_required_methods(self):
        repo = JsonlSessionRepository()
        assert hasattr(repo, "append_event")
        assert hasattr(repo, "read_events")
        assert hasattr(repo, "exists")

    def test_jsonl_repo_satisfies_typed_variable(self):
        """Structural check: assignment to SessionRepository-typed var works."""
        repo: SessionRepository = JsonlSessionRepository()
        assert repo is not None

    def test_read_events_returns_list_for_unknown_session(self, tmp_path, monkeypatch):
        import mad.core.log as _log
        monkeypatch.setattr(_log, "SESSIONS_DIR", tmp_path / "sessions")
        repo = JsonlSessionRepository()
        events = repo.read_events("nonexistent_session")
        assert events == []

    def test_exists_returns_false_for_unknown_session(self, tmp_path, monkeypatch):
        import mad.core.log as _log
        monkeypatch.setattr(_log, "SESSIONS_DIR", tmp_path / "sessions")
        repo = JsonlSessionRepository()
        assert repo.exists("nonexistent_session") is False

    def test_append_and_read_roundtrip(self, tmp_path, monkeypatch):
        import mad.core.log as _log
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        monkeypatch.setattr(_log, "SESSIONS_DIR", sessions)
        repo = JsonlSessionRepository()
        repo.append_event("sid_001", "session.created", {"agent": "test"})
        events = repo.read_events("sid_001")
        assert len(events) == 1
        assert events[0]["type"] == "session.created"
        assert repo.exists("sid_001") is True


# ---------------------------------------------------------------------------
# WorkspaceProvisioner port
# ---------------------------------------------------------------------------


class TestWorkspaceProvisionerPort:
    def test_local_provisioner_is_workspace_provisioner(self):
        provisioner = LocalWorkspaceProvisioner()
        assert isinstance(provisioner, WorkspaceProvisioner)

    def test_local_provisioner_has_required_methods(self):
        provisioner = LocalWorkspaceProvisioner()
        for method in ("create", "destroy", "materialize_github_repo", "materialize_file"):
            assert hasattr(provisioner, method), f"Missing method: {method}"
            assert callable(getattr(provisioner, method))

    def test_local_provisioner_satisfies_typed_variable(self):
        """Structural check: assignment to WorkspaceProvisioner-typed var works."""
        provisioner: WorkspaceProvisioner = LocalWorkspaceProvisioner()
        assert provisioner is not None

    def test_create_returns_path(self, tmp_path, monkeypatch):
        # Patch the imported name in resources, not in workspace module
        import mad.core.resources as _res
        monkeypatch.setattr(_res, "workspace_path", lambda sid: tmp_path / f"mad_{sid}")
        provisioner = LocalWorkspaceProvisioner()
        path = provisioner.create("sid_test")
        assert path.exists()
        assert path.is_dir()

    def test_destroy_removes_workspace(self, tmp_path, monkeypatch):
        import mad.core.resources as _res
        ws = tmp_path / "mad_sid_del"
        ws.mkdir()
        monkeypatch.setattr(_res, "workspace_path", lambda sid: tmp_path / f"mad_{sid}")
        provisioner = LocalWorkspaceProvisioner()
        provisioner.destroy("sid_del")
        assert not ws.exists()

    def test_destroy_noop_if_missing(self, tmp_path, monkeypatch):
        import mad.core.resources as _res
        monkeypatch.setattr(_res, "workspace_path", lambda sid: tmp_path / f"mad_{sid}")
        provisioner = LocalWorkspaceProvisioner()
        # Should not raise even if workspace doesn't exist
        provisioner.destroy("sid_never_created")

    def test_materialize_file(self, tmp_path):
        provisioner = LocalWorkspaceProvisioner()
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        provisioner.materialize_file(workspace, "/workspace/notes.txt", "hello")
        assert (workspace / "notes.txt").read_text() == "hello"
