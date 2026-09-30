import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.storage import ObjectStorage

router = APIRouter(tags=["system"])


class StatusResponse(BaseModel):
    status: str


class DependencyCheck(BaseModel):
    status: str
    required: bool = True
    detail: str | None = None


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, DependencyCheck] = Field(default_factory=dict)


@router.get("/health", response_model=StatusResponse)
async def health() -> StatusResponse:
    return StatusResponse(status="ok")


def _ping_redis(url: str) -> None:
    client: Redis[Any] = Redis.from_url(
        url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        if not client.ping():
            raise RuntimeError("redis ping returned false")
    finally:
        client.close()


def _head_object_bucket(settings: Settings) -> None:
    storage = ObjectStorage(settings)
    storage.client.head_bucket(Bucket=settings.s3_bucket)


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
async def ready(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadyResponse:
    checks: dict[str, DependencyCheck] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["postgres"] = DependencyCheck(status="ok", required=True)
    except Exception as exc:
        checks["postgres"] = DependencyCheck(
            status="fail",
            required=True,
            detail=type(exc).__name__,
        )

    try:
        await asyncio.to_thread(_ping_redis, settings.celery_broker_url)
        checks["redis"] = DependencyCheck(status="ok", required=True)
    except Exception as exc:
        checks["redis"] = DependencyCheck(
            status="fail",
            required=True,
            detail=type(exc).__name__,
        )

    try:
        await asyncio.to_thread(_head_object_bucket, settings)
        checks["object_storage"] = DependencyCheck(status="ok", required=True)
    except Exception as exc:
        checks["object_storage"] = DependencyCheck(
            status="fail",
            required=True,
            detail=type(exc).__name__,
        )

    required_failed = any(
        check.required and check.status != "ok" for check in checks.values()
    )
    if required_failed:
        response.status_code = 503
        return ReadyResponse(status="not_ready", checks=checks)
    return ReadyResponse(status="ready", checks=checks)
