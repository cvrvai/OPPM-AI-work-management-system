"""
Health-aware round-robin load balancer.
Periodically health-checks upstream instances and removes dead ones from rotation.
"""

import asyncio
import itertools
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class HealthyRoundRobin:
    """Round-robin load balancer that skips unhealthy instances."""

    def __init__(self, urls: list[str], health_path: str = "/health"):
        self._all_urls = urls
        self._healthy: list[str] = list(urls)
        self._cycle = itertools.cycle(self._healthy)
        self._health_path = health_path
        self._lock = asyncio.Lock()

    def next(self) -> Optional[str]:
        if not self._healthy:
            return None
        return next(self._cycle)

    async def start_health_checks(self, interval: int = 10):
        while True:
            await asyncio.sleep(interval)
            await self._check_all()

    async def _check_all(self):
        results = await asyncio.gather(
            *[self._ping(url) for url in self._all_urls],
            return_exceptions=True,
        )
        healthy = [url for url, ok in zip(self._all_urls, results) if ok is True]
        async with self._lock:
            if healthy != self._healthy:
                logger.warning("Healthy upstreams changed: %s -> %s", self._healthy, healthy)
            self._healthy = healthy
            self._cycle = itertools.cycle(healthy) if healthy else iter([])

    async def _ping(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(url + self._health_path)
                return r.status_code < 500
        except Exception:
            return False
