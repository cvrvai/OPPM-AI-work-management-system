"""
Rate limiter — Redis-backed sliding window for distributed deployments,
with in-memory fallback for local dev.
"""

import logging
import time
from collections import defaultdict
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

# ── Redis-backed sliding window ──────────────────────────────────────────────

_redis = None


async def init_redis(redis_url: str = "redis://localhost:6379"):
    """Call on startup to enable distributed rate limiting."""
    global _redis
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        await _redis.ping()
        logger.info("Rate limiter: Redis connected at %s", redis_url)
    except Exception as e:
        logger.warning("Rate limiter: Redis unavailable (%s), using in-memory fallback", e)
        _redis = None


async def _check_redis_rate_limit(key: str, limit: int, window: int) -> bool:
    """Sliding window counter using Redis sorted set."""
    now = time.time()
    window_start = now - window
    pipe = _redis.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    count = results[2]
    return count <= limit


# ── In-memory fallback (single-process dev) ──────────────────────────────────

class _InMemoryLimiter:
    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        cutoff = now - window
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]
        if len(self._buckets[key]) >= limit:
            return False
        self._buckets[key].append(now)
        return True


_fallback = _InMemoryLimiter()


# ── Public API ───────────────────────────────────────────────────────────────

async def _rate_limit(key: str, limit: int, window: int):
    if _redis is not None:
        try:
            allowed = await _check_redis_rate_limit(key, limit, window)
        except Exception as e:
            logger.warning("Redis rate limit error: %s — falling back to in-memory", e)
            allowed = _fallback.check(key, limit, window)
    else:
        allowed = _fallback.check(key, limit, window)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(window)},
        )


async def rate_limit_api(request: Request):
    """Rate limit standard API calls (100/min per IP)."""
    client_ip = request.client.host if request.client else "unknown"
    await _rate_limit(f"rl:api:{client_ip}", limit=100, window=60)


async def rate_limit_webhook(request: Request):
    """Rate limit webhook calls (30/min per IP)."""
    client_ip = request.client.host if request.client else "unknown"
    await _rate_limit(f"rl:webhook:{client_ip}", limit=30, window=60)


async def rate_limit_ai(request: Request):
    """Rate limit AI calls (10/min per IP)."""
    client_ip = request.client.host if request.client else "unknown"
    await _rate_limit(f"rl:ai:{client_ip}", limit=10, window=60)
