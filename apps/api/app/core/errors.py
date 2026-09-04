from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorBody(BaseModel):
    code: str
    message: str
    correlation_id: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def _response(
    request: Request, status_code: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    content = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            correlation_id=correlation_id,
            details=details,
        )
    ).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=content)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        details = None if isinstance(exc.detail, str) else exc.detail
        return _response(request, exc.status_code, f"http_{exc.status_code}", message, details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _response(
            request, 422, "validation_error", "Request validation failed", exc.errors()
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        return _response(request, 500, "internal_error", "An unexpected error occurred")
