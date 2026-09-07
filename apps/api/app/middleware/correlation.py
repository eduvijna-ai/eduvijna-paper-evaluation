import re
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

MAX_CORRELATION_ID_LENGTH = 100  # Matches audit_events.correlation_id String(100)
# Safe printable charset for inbound correlation IDs (UUID-friendly + common tracers).
_CORRELATION_ID_RE = re.compile(r"^[A-Za-z0-9._\-]+$")

_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Return the correlation ID bound for the current request/task, if any."""
    return _correlation_id_ctx.get()


def normalize_correlation_id(raw: str | None) -> str:
    """Accept a client correlation ID when safe; otherwise generate a UUID."""
    if raw is None:
        return str(uuid.uuid4())
    value = raw.strip()
    if (
        value
        and len(value) <= MAX_CORRELATION_ID_LENGTH
        and _CORRELATION_ID_RE.fullmatch(value)
    ):
        return value
    return str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = normalize_correlation_id(request.headers.get("X-Correlation-ID"))
        request.state.correlation_id = correlation_id
        token = _correlation_id_ctx.set(correlation_id)
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            _correlation_id_ctx.reset(token)
            structlog.contextvars.clear_contextvars()
