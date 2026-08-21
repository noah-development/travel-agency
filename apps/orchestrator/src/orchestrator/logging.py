"""Structured JSON logging via structlog.

Every log line carries request_id, path, method, status, and duration_ms,
propagated through structlog's contextvars (bound once per request by
RequestContextMiddleware), never passed as an explicit per-call argument.

NEVER log: token contents (raw or decoded claims), ANTHROPIC_API_KEY, or
full LLM response bodies. Call sites in auth/ and llm/ must only log
metadata (e.g. a claim's `sub`, response length, model name), never the
token or the response body itself.
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from orchestrator.config import Settings

logger = structlog.get_logger("orchestrator")


def configure_logging(settings: Settings) -> None:
    level = logging.getLevelName(settings.log_level.upper())
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, path=request.url.path, method=request.method
        )
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        structlog.contextvars.bind_contextvars(status=response.status_code, duration_ms=duration_ms)
        logger.info("request_completed")
        response.headers["x-request-id"] = request_id
        return response
