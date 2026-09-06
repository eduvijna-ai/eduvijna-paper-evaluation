"""Celery application and B3 page-normalization task."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

from celery import Celery

from app.core.config import get_settings


def create_celery_app() -> Any:
    settings = get_settings()
    app = Celery("eduvijna")
    app.conf.update(
        broker_url=settings.celery_broker_url,
        result_backend=settings.celery_result_backend,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_always_eager=False,
        task_store_eager_result=True,
    )
    return app


celery_app = create_celery_app()


async def _normalize_async(
    tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    from app.db.session import async_session_factory
    from app.services.page_normalization import run_page_normalization

    async with async_session_factory() as db:
        await run_page_normalization(
            db,
            tenant_id=tenant_id,
            submission_id=submission_id,
            job_id=job_id,
        )


def _normalize_pages_impl(tenant_id: str, submission_id: str, job_id: str) -> dict[str, str]:
    """Worker-process entrypoint (no running asyncio loop)."""
    asyncio.run(
        _normalize_async(
            uuid.UUID(tenant_id),
            uuid.UUID(submission_id),
            uuid.UUID(job_id),
        )
    )
    return {
        "tenant_id": tenant_id,
        "submission_id": submission_id,
        "job_id": job_id,
        "status": "ok",
    }


normalize_pages_task = cast(
    Any, celery_app.task(name="submissions.normalize_pages")(_normalize_pages_impl)
)


async def enqueue_page_normalization(
    *, tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> str | None:
    """Enqueue page normalization.

    When ``CELERY_TASK_ALWAYS_EAGER`` is set (tests), run inline on the current
    event loop instead of Celery eager + ``asyncio.run``.
    """
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _normalize_async(tenant_id, submission_id, job_id)
        return f"eager:{job_id}"

    result = normalize_pages_task.delay(str(tenant_id), str(submission_id), str(job_id))
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None
