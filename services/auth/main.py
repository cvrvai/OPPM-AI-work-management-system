"""
Auth Service — user registration, login, JWT issuance, token refresh, signout.
Port: 8004
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
from routers.health import router as health_router
from routers.v1 import router as v1_router

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    yield
    await close_redis()
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="OPPM Auth Service",
        version="1.0.0",
        description="Authentication — register, login, token refresh, signout, profile",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        tb = traceback.format_exc()
        logger.error("500 %s: %s\n%s", request.url.path, exc, tb)
        detail = str(exc) if settings.debug else "Internal server error"
        return JSONResponse({"detail": detail}, status_code=500)

    app.include_router(health_router)
    app.include_router(v1_router, prefix="/api")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=settings.debug)
