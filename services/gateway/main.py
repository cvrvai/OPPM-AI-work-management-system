"""
Python API Gateway — mirrors nginx routing for native development.

Routes all /api/* requests to the correct backend service using the same
URL patterns as gateway/nginx.conf. Supports health-aware round-robin load
balancing when multiple instances are configured via environment variables.

Set WORKSPACE_URLS, INTELLIGENCE_URLS, INTEGRATIONS_URLS, AUTOMATION_URLS
to comma-separated lists to enable load balancing across multiple instances.
Legacy env vars (CORE_URLS, AI_URLS, GIT_URLS, MCP_URLS) are still supported.
"""

import re
import asyncio
import logging
import uuid

import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from infrastructure.load_balancer import HealthyRoundRobin
from middleware.logging import log_requests_middleware

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Build instance pools from comma-separated env vars ──────────────────────
def _parse_urls(raw: str) -> list[str]:
    return [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]


lb: dict[str, HealthyRoundRobin] = {}

# Persistent HTTP client for connection pooling
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    lb["workspace"]     = HealthyRoundRobin(_parse_urls(settings.resolved_workspace_urls()))
    lb["intelligence"]  = HealthyRoundRobin(_parse_urls(settings.resolved_intelligence_urls()))
    lb["integrations"] = HealthyRoundRobin(_parse_urls(settings.resolved_integrations_urls()))
    lb["automation"]    = HealthyRoundRobin(_parse_urls(settings.resolved_automation_urls()))
    tasks = [asyncio.create_task(v.start_health_checks()) for v in lb.values()]
    http_client = httpx.AsyncClient(timeout=120, limits=httpx.Limits(max_connections=100, max_keepalive_connections=20))
    yield
    for t in tasks:
        t.cancel()
    if http_client:
        await http_client.aclose()


app = FastAPI(title="OPPM API Gateway", lifespan=lifespan)


# ── Route table — order matters, most specific first ────────────────────────
ROUTES: list[tuple[re.Pattern, str, int]] = [
    # pattern, service, timeout_seconds
    # Long-running AI endpoints (agent loops, SSE streaming) — must come before
    # the generic /ai/ catch-all. SSE keeps the connection warm but the
    # client-side httpx still needs a generous read timeout.
    (re.compile(r"^/api/v1/workspaces/[^/]+/projects/[^/]+/ai/oppm-agent-fill"), "intelligence", 600),
    (re.compile(r"^/api/v1/workspaces/[^/]+/projects/[^/]+/ai/chat/stream"),     "intelligence", 600),
    (re.compile(r"^/api/v1/workspaces/[^/]+/projects/[^/]+/ai/"), "intelligence",  120),
    (re.compile(r"^/api/v1/workspaces/[^/]+/rag/"),                "intelligence",  120),
    (re.compile(r"^/api/v1/workspaces/[^/]+/ai/"),                 "intelligence",  120),
    (re.compile(r"^/internal/analyze-commits$"),                   "intelligence",  120),
    (re.compile(r"^/api/v1/workspaces/[^/]+/mcp/"),                "automation",   120),
    (re.compile(r"^/api/v1/workspaces/[^/]+/github-accounts"),     "integrations",  30),
    (re.compile(r"^/api/v1/workspaces/[^/]+/commits"),             "integrations",  30),
    (re.compile(r"^/api/v1/workspaces/[^/]+/git/"),                "integrations",  30),
    (re.compile(r"^/api/v1/git/webhook"),                          "integrations",  30),
    (re.compile(r"^/mcp"),                                         "automation",   300),
    (re.compile(r"^/api/"),                                       "workspace",     30),
]

# ── CORS ─────────────────────────────────────────────────────────────────────
# Parse comma-separated origins from env var
# SECURITY: Internal headers (X-Internal-API-Key) are intentionally excluded
# from CORS. Internal endpoints are backend-only and must never be reachable
# from browsers. Backend services communicate directly, bypassing CORS entirely.
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    allow_credentials=True,
    max_age=86400,
)


# ── Request logging middleware ────────────────────────────────────────────────
app.middleware("http")(log_requests_middleware)


async def _forward_upstream_health(service: str) -> Response:
    target_base = lb[service].next()
    if target_base is None:
        return Response(
            content=f"Service '{service}' unavailable",
            status_code=503,
            headers={"Retry-After": "10"},
        )

    try:
        upstream = await http_client.get(f"{target_base}/health", timeout=5)

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


@app.get("/health/workspace")
async def workspace_health() -> Response:
    return await _forward_upstream_health("workspace")


@app.get("/health/intelligence")
async def intelligence_health() -> Response:
    return await _forward_upstream_health("intelligence")


@app.get("/health/integrations")
async def integrations_health() -> Response:
    return await _forward_upstream_health("integrations")


@app.get("/health/automation")
async def automation_health() -> Response:
    return await _forward_upstream_health("automation")


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

    # Propagate request ID for distributed tracing
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    forward_headers["X-Request-ID"] = request_id

    logger.debug("Gateway -> %s %s", target_service, target_url)

    try:
        upstream = await http_client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=await request.body(),
            timeout=timeout,
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
        response.headers["X-Request-ID"] = request_id
        return response
    except httpx.ConnectError:
        logger.warning("Gateway: cannot reach %s at %s", target_service, target_base)
        return Response(
            content=f"Service '{target_service}' is not running",
            status_code=502,
            headers={"Retry-After": "5", "X-Request-ID": request_id},
        )
    except httpx.TimeoutException:
        logger.warning("Gateway: timeout reaching %s", target_service)
        return Response(
            content=f"Service '{target_service}' timed out",
            status_code=504,
            headers={"X-Request-ID": request_id},
        )


