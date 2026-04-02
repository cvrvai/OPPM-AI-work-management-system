"""
OPPM Core Service — workspace, project, task, OPPM, notification, dashboard endpoints.
"""

import logging
from fastapi import FastAPI

from config import get_settings
from middleware.logging import RequestLoggingMiddleware
from routers.v1 import router as v1_router

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


def create_app() -> FastAPI:
    """Application factory for the core service."""
    app = FastAPI(
        title="OPPM Core Service",
        version="2.0.0",
        description="Core service — workspaces, projects, tasks, OPPM, notifications, dashboard",
    )

    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(v1_router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "core", "version": "2.0.0"}

    return app


app = create_app()
