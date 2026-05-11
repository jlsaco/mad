"""CleanupSessions use case — bulk-delete sessions older than a cutoff.

Selection rule: ``session.status != "deleted"`` AND ``session.updated_at < older_than``.
No special-casing for ``running`` — a live agent emits stdout continuously per the
``AgentLauncher`` contract, so a session with ``updated_at < older_than`` is by
construction abandoned/wedged regardless of its status flag.

``dry_run=True`` reports the matching IDs in ``would_delete`` without invoking
``destroy_session``; nothing is mutated and no ``session.deleted`` event is emitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from mad.core.events.emitter import EventEmitter
from mad.core.sessions.domain.entities.session import Session
from mad.core.sessions.ports.outbound.workspace_provisioner import WorkspaceProvisioner
from mad.core.sessions.use_cases.delete_session import destroy_session


@dataclass
class CleanupSessionsInput:
    older_than: datetime
    dry_run: bool = False


@dataclass
class CleanupSessionsOutput:
    deleted_session_ids: list[str] = field(default_factory=list)
    would_delete: list[str] = field(default_factory=list)
    examined: int = 0


class CleanupSessionsUseCase:
    """Bulk-delete in-memory sessions whose ``updated_at`` is older than a cutoff."""

    def __init__(
        self,
        provisioner: WorkspaceProvisioner,
        sessions_index: dict[str, Session],
        emitter: EventEmitter,
    ) -> None:
        self._provisioner = provisioner
        self._sessions = sessions_index
        self._emitter = emitter

    async def execute(self, payload: CleanupSessionsInput) -> CleanupSessionsOutput:
        candidates: list[Session] = []
        examined = 0
        for session in list(self._sessions.values()):
            if session.status == "deleted":
                continue
            examined += 1
            if session.updated_at < payload.older_than:
                candidates.append(session)

        if payload.dry_run:
            return CleanupSessionsOutput(
                would_delete=[s.session_id for s in candidates],
                examined=examined,
            )

        deleted_ids: list[str] = []
        for session in candidates:
            await destroy_session(session, self._provisioner, self._emitter)
            deleted_ids.append(session.session_id)

        return CleanupSessionsOutput(
            deleted_session_ids=deleted_ids,
            examined=examined,
        )
