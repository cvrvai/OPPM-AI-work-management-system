"""
Python API Gateway — mirrors nginx routing for native development.

Routes all /api/* requests to the correct backend service using the same
URL patterns as gateway/nginx.conf. Supports health-aware round-robin load
balancing when multiple instances are configured via environment variables.

Set CORE_URLS, AI_URLS, GIT_URLS, MCP_URLS to comma-separated lists to
enable load balancing across multiple instances of the same service.
"""

import re
import asyncio
import logging

import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from load_balancer import HealthyRoundRobin

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Build instance pools from comma-separated env vars ──────────────────────
def _parse_urls(raw: str) -> list[str]:
    return [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]


lb: dict[str, HealthyRoundRobin] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    lb["core"] = HealthyRoundRobin(_parse_urls(settings.core_urls))
    lb["ai"]   = HealthyRoundRobin(_parse_urls(settings.ai_urls))
    lb["git"]  = HealthyRoundRobin(_parse_urls(settings.git_urls))
    lb["mcp"]  = HealthyRoundRobin(_parse_urls(settings.mcp_urls))
    tasks = [asyncio.create_task(v.start_health_checks()) for v in lb.values()]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="OPPM API Gateway", lifespan=lifespan)


# ── Route table — order matters, most specific first ────────────────────────
ROUTES: list[tuple[re.Pattern, str, int]] = [
    # pattern, service, timeout_seconds
    (re.compile(r"^/api/v1/workspaces/[^/]+/projects/[^/]+/ai/"), "ai",  120),
    (re.compile(r"^/api/v1/workspaces/[^/]+/rag/"),                "ai",  120),
    (re.compile(r"^/api/v1/workspaces/[^/]+/ai/"),                 "ai",  120),
    (re.compile(r"^/internal/analyze-commits$"),                   "ai",  120),
    (re.compile(r"^/api/v1/workspaces/[^/]+/mcp/"),                "mcp", 120),
    (re.compile(r"^/api/v1/workspaces/[^/]+/github-accounts"),     "git",  30),
    (re.compile(r"^/api/v1/workspaces/[^/]+/commits"),             "git",  30),
    (re.compile(r"^/api/v1/workspaces/[^/]+/git/"),                "git",  30),
    (re.compile(r"^/api/v1/git/webhook"),                          "git",  30),
    (re.compile(r"^/mcp"),                                         "mcp", 300),
    (re.compile(r"^/api/"),                                        "core",  30),
]

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://localhost(:[0-9]+)?",
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    allow_credentials=True,
    max_age=86400,
)


async def _forward_upstream_health(service: str) -> Response:
    target_base = lb[service].next()
    if target_base is None:
        return Response(
            content=f"Service '{service}' unavailable",
            status_code=503,
            headers={"Retry-After": "10"},
        )

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            upstream = await client.get(f"{target_base}/health")

        response = Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type"),
        )
        for key, value in upstream.headers.multi_items():
            if key.lower() not in {"content-length", "transfer-encoding", "connection", "content-type"}:
                response.headers.append(key, value)
        return response
    except httpx.ConnectError:
        logger.warning("Gateway: cannot reach %s at %s", service, target_base)
        return Response(
            content=f"Service '{service}' is not running",
            status_code=502,
            headers={"Retry-After": "5"},
        )
    except httpx.TimeoutException:
        logger.warning("Gateway: timeout reaching %s", service)
        return Response(
            content=f"Service '{service}' timed out",
            status_code=504,
        )


@app.get("/health")
async def gateway_health() -> dict:
    return {"status": "ok", "service": "gateway"}


@app.get("/health/core")
async def core_health() -> Response:
    return await _forward_upstream_health("core")


@app.get("/health/ai")
async def ai_health() -> Response:
    return await _forward_upstream_health("ai")


@app.get("/health/git")
async def git_health() -> Response:
    return await _forward_upstream_health("git")


@app.get("/health/mcp")
async def mcp_health() -> Response:
    return await _forward_upstream_health("mcp")


# ── Proxy handler ─────────────────────────────────────────────────────────────
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy(request: Request, path: str) -> Response:
    url_path = "/" + path
    if request.url.query:
        url_path += "?" + request.url.query

    # Find matching service
    target_service: str | None = None
    timeout = 30
    for pattern, service, t in ROUTES:
        if pattern.match(url_path.split("?")[0]):
            target_service = service
            timeout = t
            break

    if target_service is None:
        return Response(status_code=404, content="No route matched")

    target_base = lb[target_service].next()
    if target_base is None:
        return Response(
            content=f"Service '{target_service}' unavailable",
            status_code=503,
            headers={"Retry-After": "10"},
        )

    target_url = target_base + url_path

    # Strip hop-by-hop headers before forwarding
    skip_headers = {"host", "content-length", "transfer-encoding", "connection"}
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in skip_headers
    }

    logger.debug("Gateway -> %s %s", target_service, target_url)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=await request.body(),
            )

        # Preserve multi-value headers (especially Set-Cookie).
        # dict(upstream.headers) collapses duplicates — browser loses cookies.
        skip_response = {"content-length", "transfer-encoding", "connection"}
        response = Response(
            content=upstream.content,
            status_code=upstream.status_code,
        )
        for key, value in upstream.headers.multi_items():
            if key.lower() not in skip_response:
                response.headers.append(key, value)
        return response
    except httpx.ConnectError:
        logger.warning("Gateway: cannot reach %s at %s", target_service, target_base)
        return Response(
            content=f"Service '{target_service}' is not running",
            status_code=502,
            headers={"Retry-After": "5"},
        )
    except httpx.TimeoutException:
        logger.warning("Gateway: timeout reaching %s", target_service)
        return Response(
            content=f"Service '{target_service}' timed out",
            status_code=504,
        )


