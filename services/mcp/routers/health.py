"""Liveness and readiness probes — MCP service (port 8003)."""

import sqlalchemy
from fastapi import APIRouter
from shared.database import get_engine
from shared.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/health", include_in_schema=False)
async def liveness():
    return {"status": "ok", "service": "mcp", "version": "2.0.0"}


@router.get("/ready", include_in_schema=False)
async def readiness():
    checks: dict[str, str] = {}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"
    try:
        redis = await get_redis()
        checks["redis"] = "ok" if await redis.ping() else "unavailable"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
    all_ok = all(v in ("ok", "unavailable") for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
