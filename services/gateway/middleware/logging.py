"""
Request logging middleware for the gateway.
Generates request IDs and logs method, path, status, and duration.
"""

import time
import uuid
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


async def log_requests_middleware(request: Request, call_next):
    """Log incoming requests with timing and request ID propagation."""
    start = time.time()
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)

    duration = (time.time() - start) * 1000
    logger.info(
        "[%s] %s %s -> %d in %.2fms",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    response.headers["X-Request-ID"] = request_id
    return response
