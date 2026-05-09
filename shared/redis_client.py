"""
Redis async singleton shared across all microservices.
Used for token blacklist, rate limiting, caching.
"""

import logging
from redis.asyncio import Redis
from shared.config import get_settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _redis


async def init_redis() -> None:
    """Verify Redis connectivity on startup."""
    r = await get_redis()
    try:
        await r.ping()
        logger.info("Redis connection verified")
    except Exception as e:
        logger.warning("Redis not available — falling back to in-memory: %s", e)


async def close_redis() -> None:
    """Close Redis connection on shutdown."""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
        logger.info("Redis connection closed")
