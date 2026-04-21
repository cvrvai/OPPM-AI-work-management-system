"""
Semantic cache — embedding-based response cache using Redis.

Stores (query_embedding, response) pairs in Redis with a TTL.
On lookup, computes cosine similarity against recent cache entries
and returns a hit if similarity >= SIMILARITY_THRESHOLD.

Falls back gracefully when Redis is unavailable.
"""

import json
import logging
import math
import time
from typing import Any

logger = logging.getLogger(__name__)

# Cache entry TTL in seconds (5 minutes)
_CACHE_TTL_SECONDS = 300

# Cosine similarity threshold for a cache hit (0.0–1.0)
SIMILARITY_THRESHOLD = 0.92

# Max cached entries to scan per lookup (prevents full-scan slowness)
_MAX_SCAN_ENTRIES = 200

# Redis key prefix
_KEY_PREFIX = "ai:sem_cache:"
_INDEX_KEY = "ai:sem_cache:index"


class SemanticCache:
    """Embedding-based Redis cache for AI responses."""

    def __init__(self) -> None:
        self._redis: Any = None

    def _get_redis(self) -> Any:
        if self._redis is None:
            try:
                from shared.redis_client import get_redis_client
                self._redis = get_redis_client()
            except Exception as exc:
                logger.debug("Redis unavailable for semantic cache: %s", exc)
        return self._redis

    async def lookup(
        self,
        query_embedding: list[float],
        *,
        workspace_id: str,
        project_id: str | None = None,
    ) -> str | None:
        """Return cached response text if a similar query was recently cached, else None."""
        redis = self._get_redis()
        if redis is None:
            return None

        try:
            scope = f"{workspace_id}:{project_id or 'ws'}"
            index_key = f"{_INDEX_KEY}:{scope}"

            # Retrieve the most recent entry IDs
            entry_ids: list[bytes] = await redis.lrange(index_key, 0, _MAX_SCAN_ENTRIES - 1)
            if not entry_ids:
                return None

            for entry_id in entry_ids:
                entry_key = f"{_KEY_PREFIX}{entry_id.decode()}"
                raw = await redis.get(entry_key)
                if not raw:
                    continue  # Expired

                try:
                    entry = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue

                cached_emb = entry.get("embedding")
                if not cached_emb:
                    continue

                sim = _cosine_similarity(query_embedding, cached_emb)
                if sim >= SIMILARITY_THRESHOLD:
                    logger.debug(
                        "Semantic cache HIT (similarity=%.3f) for scope %s",
                        sim, scope,
                    )
                    return entry.get("response", "")

        except Exception as exc:
            logger.debug("Semantic cache lookup failed: %s", exc)

        return None

    async def store(
        self,
        query_embedding: list[float],
        response: str,
        *,
        workspace_id: str,
        project_id: str | None = None,
    ) -> None:
        """Store an embedding+response pair in the cache."""
        redis = self._get_redis()
        if redis is None:
            return

        try:
            scope = f"{workspace_id}:{project_id or 'ws'}"
            entry_id = f"{scope}:{int(time.time() * 1000)}"
            entry_key = f"{_KEY_PREFIX}{entry_id}"
            index_key = f"{_INDEX_KEY}:{scope}"

            payload = json.dumps({
                "embedding": query_embedding,
                "response": response,
                "timestamp": time.time(),
            })

            # Store entry with TTL
            await redis.set(entry_key, payload, ex=_CACHE_TTL_SECONDS)

            # Maintain index (prepend so newest is first)
            await redis.lpush(index_key, entry_id)
            await redis.expire(index_key, _CACHE_TTL_SECONDS)

            # Keep index bounded
            await redis.ltrim(index_key, 0, _MAX_SCAN_ENTRIES - 1)

            logger.debug("Semantic cache stored entry for scope %s", scope)

        except Exception as exc:
            logger.debug("Semantic cache store failed: %s", exc)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# Module-level singleton
_cache_instance: SemanticCache | None = None


def get_semantic_cache() -> SemanticCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance
