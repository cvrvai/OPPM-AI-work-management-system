"""Git service — GitHub integration, webhooks, commits."""

import logging
from fastapi import FastAPI
from routers.v1 import router as v1_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="OPPM Git Service", version="2.0.0")

    # CORS handled by nginx gateway
    app.include_router(v1_router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "git", "version": "2.0.0"}

    return app


app = create_app()
