"""MCP service — Model Context Protocol tools for AI integrations."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from shared.database import init_db, close_db
from routers.v1 import router as v1_router

logger = logging.getLogger(__name__)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(title="OPPM MCP Service", version="2.0.0", lifespan=lifespan)

    # CORS handled by nginx gateway
    app.include_router(v1_router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "mcp", "version": "2.0.0"}

    return app


app = create_app()
