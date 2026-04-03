"""
OPPM Core Service — workspace, project, task, OPPM, notification, dashboard endpoints.
"""

import logging
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import get_settings
from middleware.logging import RequestLoggingMiddleware
from shared.database import init_db, close_db
from shared.redis_client import init_redis, close_redis
from routers.v1 import router as v1_router
from routers.auth import router as auth_router

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
# Silence noisy logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    yield
    await close_redis()
    await close_db()


def create_app() -> FastAPI:
    """Application factory for the core service."""
    app = FastAPI(
        title="OPPM Core Service",
        version="2.0.0",
        description="Core service — workspaces, projects, tasks, OPPM, notifications, dashboard",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)

    @app.exception_handler(Exception)
    async def _debug_exception_handler(request: Request, exc: Exception):
        tb = traceback.format_exc()
        logging.getLogger("oppm.debug").error("500 on %s: %s\n%s", request.url.path, exc, tb)
        return JSONResponse({"detail": str(exc), "traceback": tb}, status_code=500)

    app.include_router(v1_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "core", "version": "2.0.0"}

    return app


app = create_app()
