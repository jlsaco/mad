from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from mad.api.routes.sessions import router as sessions_router
from mad.core import log
from mad.core.domain.exceptions.base import PathTraversalError, SessionNotFound
from mad.core.log import JsonlSessionRepository
from mad.core.ports.outbound.session_repository import SessionRepository
from mad.core.ports.outbound.workspace_provisioner import WorkspaceProvisioner
from mad.core.resources import LocalWorkspaceProvisioner
from mad.core.sessions import SessionStore


def create_app(
    store: SessionStore | None = None,
    session_repo: SessionRepository | None = None,
    workspace_provisioner: WorkspaceProvisioner | None = None,
) -> FastAPI:
    """Build a FastAPI app with injected dependencies.

    Every call creates an isolated instance — tests get a fresh store so state
    never leaks across cases.

    ``session_repo`` and ``workspace_provisioner`` are the outbound ports
    introduced in Phase 3. If not supplied, sensible defaults are used:
    - ``JsonlSessionRepository`` — JSONL file-backed session log.
    - ``LocalWorkspaceProvisioner`` — local temp-dir workspace management.

    Routes delegate to use cases from mad.core.use_cases.sessions.*.
    """
    app = FastAPI(title="Mad", version="0.1.0")
    app.state.store = store or SessionStore()
    app.state.session_repo = session_repo or JsonlSessionRepository()
    app.state.workspace_provisioner = workspace_provisioner or LocalWorkspaceProvisioner()

    @app.exception_handler(PathTraversalError)
    async def _path_traversal_handler(request: Request, exc: PathTraversalError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(SessionNotFound)
    async def _session_not_found_handler(request: Request, exc: SessionNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.on_event("startup")
    async def _startup() -> None:
        log.ensure_sessions_dir()

    app.include_router(sessions_router)
    return app
