"""Intelligence Service — LLM, RAG, chat, commit analysis."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from shared.database import init_db, close_db
from middleware.logging import RequestLoggingMiddleware
from routers.health import router as health_router
from domains import router as v1_router
from domains.analysis.internal_router import router as internal_router

logger = logging.getLogger(__name__)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(title="Intelligence Service", version="2.0.0", lifespan=lifespan)
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(health_router)

    # Public API routes (proxied by gateway, CORS handled by nginx)
    app.include_router(v1_router, prefix="/api")

    # Internal routes (service-to-service, not proxied)
    app.include_router(internal_router)

    return app


app = create_app()
