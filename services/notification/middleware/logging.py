"""Request logging middleware."""

import logging, time, uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("oppm.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.time()
        request.state.request_id = request_id
        response: Response = await call_next(request)
        elapsed_ms = round((time.time() - start) * 1000, 1)
        logger.info("%s %s %s %sms [%s]", request.method, request.url.path, response.status_code, elapsed_ms, request_id)
        response.headers["X-Request-ID"] = request_id
        return response
