"""
Simple in-memory rate limiter (token bucket).
For production at scale, replace with Redis-backed implementation.
"""

import time
from collections import defaultdict
from fastapi import HTTPException, Request, status


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def _clean(self, key: str, now: float):
        cutoff = now - self.window_seconds
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

    def check(self, key: str) -> bool:
        now = time.time()
        self._clean(key, now)
        if len(self._buckets[key]) >= self.max_requests:
            return False
        self._buckets[key].append(now)
        return True


# Global instances for different endpoint groups
api_limiter = RateLimiter(max_requests=100, window_seconds=60)
webhook_limiter = RateLimiter(max_requests=30, window_seconds=60)
ai_limiter = RateLimiter(max_requests=10, window_seconds=60)


async def rate_limit_api(request: Request):
    """Rate limit standard API calls (100/min per IP)."""
    client_ip = request.client.host if request.client else "unknown"
    if not api_limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
        )


async def rate_limit_webhook(request: Request):
    """Rate limit webhook calls (30/min per IP)."""
    client_ip = request.client.host if request.client else "unknown"
    if not webhook_limiter.check(f"webhook:{client_ip}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Webhook rate limit exceeded.",
        )
