from __future__ import annotations

from fastapi import FastAPI

from mad.api.routes.sessions import router as sessions_router
from mad.core import log
from mad.core.sessions import SessionStore


def create_app(store: SessionStore | None = None) -> FastAPI:
    """Build a FastAPI app with an injected SessionStore.

    Every call creates an isolated instance — tests get a fresh store
    so state never leaks across cases.
    """
    app = FastAPI(title="Mad", version="0.1.0")
    app.state.store = store or SessionStore()

    @app.on_event("startup")
    async def _startup() -> None:
        log.ensure_sessions_dir()

    app.include_router(sessions_router)
    return app
