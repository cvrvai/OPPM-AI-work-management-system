"""AI service — LLM, RAG, chat, commit analysis."""

import logging
from fastapi import FastAPI, Request
from routers.v1 import router as v1_router
from routers.internal import router as internal_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="OPPM AI Service", version="2.0.0")

    # Public API routes (proxied by gateway, CORS handled by nginx)
    app.include_router(v1_router, prefix="/api")

    # Internal routes (service-to-service, not proxied)
    app.include_router(internal_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "ai", "version": "2.0.0"}

    return app


app = create_app()
