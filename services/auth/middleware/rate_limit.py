"""
Rate limiter middleware — Redis sliding-window with in-memory fallback.
"""

import logging
import time
from collections import defaultdict
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

_redis = None


async def init_rate_limit_redis(redis_url: str) -> None:
    global _redis
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(redis_url, decode_responses=True)
        await _redis.ping()
        logger.info("Rate limiter: Redis connected")
    except Exception as exc:
        logger.warning("Rate limiter: Redis unavailable (%s), using in-memory fallback", exc)
        _redis = None


async def _check_redis(key: str, limit: int, window: int) -> bool:
    now = time.time()
    pipe = _redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    return results[2] <= limit


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


async def rate_limit(request: Request, limit: int = 60, window: int = 60) -> None:
    """FastAPI dependency — raises 429 when the caller exceeds the rate limit."""
    key = f"rl:{request.client.host if request.client else 'unknown'}"
    if _redis is not None:
        try:
            allowed = await _check_redis(key, limit, window)
        except Exception as exc:
            logger.warning("Redis rate limit error: %s — fallback", exc)
            allowed = _fallback.check(key, limit, window)
    else:
        allowed = _fallback.check(key, limit, window)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(window)},
        )
