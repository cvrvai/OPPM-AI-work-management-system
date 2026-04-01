"""
OPPM AI Work Management System — Application Entry Point.

Clean architecture with versioned API routes, middleware chain,
and workspace-scoped multi-tenant design.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from middleware.logging import RequestLoggingMiddleware
from routers.v1 import router as v1_router

# ── Legacy routers (kept for backwards compatibility during migration) ──
from routers import projects, tasks, git, ai, dashboard, notifications

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="OPPM AI Work Management",
        version="2.0.0",
        description="AI-powered One Page Project Manager backend — multi-tenant, workspace-scoped",
    )

    # ── Middleware (order matters — outermost first) ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    # ── v1 routes (new workspace-scoped endpoints) ──
    app.include_router(v1_router, prefix="/api")

    # ── Legacy routes (will be removed after frontend migration) ──
    app.include_router(dashboard.router, prefix="/api", tags=["legacy"])
    app.include_router(projects.router, prefix="/api", tags=["legacy"])
    app.include_router(tasks.router, prefix="/api", tags=["legacy"])
    app.include_router(git.router, prefix="/api", tags=["legacy"])
    app.include_router(ai.router, prefix="/api", tags=["legacy"])
    app.include_router(notifications.router, prefix="/api", tags=["legacy"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "oppm-ai-backend", "version": "2.0.0"}

    return app


app = create_app()
