"""Celery application and pipeline tasks (B3 + B4)."""

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
    from app.db.session import async_session_factory, engine
    from app.services.page_normalization import run_page_normalization

    # Celery uses a fresh asyncio loop per task; dispose pooled connections first.
    await engine.dispose()
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


async def _mapping_prepare_async(
    tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    from app.db.session import async_session_factory, engine
    from app.services.mapping_prepare import run_mapping_preparation

    await engine.dispose()
    async with async_session_factory() as db:
        await run_mapping_preparation(
            db,
            tenant_id=tenant_id,
            submission_id=submission_id,
            job_id=job_id,
        )


def _prepare_mapping_impl(tenant_id: str, submission_id: str, job_id: str) -> dict[str, str]:
    asyncio.run(
        _mapping_prepare_async(
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


prepare_mapping_task = cast(
    Any, celery_app.task(name="submissions.prepare_mapping")(_prepare_mapping_impl)
)


async def enqueue_mapping_preparation(
    *, tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> str | None:
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _mapping_prepare_async(tenant_id, submission_id, job_id)
        return f"eager:{job_id}"

    result = prepare_mapping_task.delay(str(tenant_id), str(submission_id), str(job_id))
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None


async def _identity_async(
    tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    from app.db.session import async_session_factory, engine
    from app.services.identity_ai import run_identity_extraction

    await engine.dispose()
    async with async_session_factory() as db:
        await run_identity_extraction(
            db,
            tenant_id=tenant_id,
            submission_id=submission_id,
            job_id=job_id,
        )


def _identity_impl(tenant_id: str, submission_id: str, job_id: str) -> dict[str, str]:
    asyncio.run(
        _identity_async(
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


identity_extraction_task = cast(
    Any, celery_app.task(name="submissions.extract_identity")(_identity_impl)
)


async def enqueue_identity_extraction(
    *, tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> str | None:
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _identity_async(tenant_id, submission_id, job_id)
        return f"eager:{job_id}"

    result = identity_extraction_task.delay(
        str(tenant_id), str(submission_id), str(job_id)
    )
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None


async def _transcription_async(
    tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    from app.db.session import async_session_factory, engine
    from app.services.transcription import run_transcription_pipeline

    await engine.dispose()
    async with async_session_factory() as db:
        await run_transcription_pipeline(
            db,
            tenant_id=tenant_id,
            submission_id=submission_id,
            job_id=job_id,
        )


def _transcription_impl(tenant_id: str, submission_id: str, job_id: str) -> dict[str, str]:
    asyncio.run(
        _transcription_async(
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


transcription_task = cast(
    Any, celery_app.task(name="submissions.run_transcription")(_transcription_impl)
)


async def enqueue_transcription(
    *, tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> str | None:
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _transcription_async(tenant_id, submission_id, job_id)
        return f"eager:{job_id}"

    result = transcription_task.delay(str(tenant_id), str(submission_id), str(job_id))
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None


async def _evaluation_async(
    tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    from app.db.session import async_session_factory, engine
    from app.services.evaluation import run_evaluation_pipeline

    await engine.dispose()
    async with async_session_factory() as db:
        await run_evaluation_pipeline(
            db,
            tenant_id=tenant_id,
            submission_id=submission_id,
            job_id=job_id,
        )


def _evaluation_impl(tenant_id: str, submission_id: str, job_id: str) -> dict[str, str]:
    asyncio.run(
        _evaluation_async(
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


evaluation_task = cast(
    Any, celery_app.task(name="submissions.run_evaluation")(_evaluation_impl)
)


async def enqueue_evaluation(
    *, tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> str | None:
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _evaluation_async(tenant_id, submission_id, job_id)
        return f"eager:{job_id}"

    result = evaluation_task.delay(str(tenant_id), str(submission_id), str(job_id))
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None


async def _publication_async(
    tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    from app.db.session import async_session_factory, engine
    from app.services.publication import run_publication_pipeline

    await engine.dispose()
    async with async_session_factory() as db:
        await run_publication_pipeline(
            db,
            tenant_id=tenant_id,
            submission_id=submission_id,
            job_id=job_id,
        )


def _publication_impl(tenant_id: str, submission_id: str, job_id: str) -> dict[str, str]:
    asyncio.run(
        _publication_async(
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


publication_task = cast(
    Any, celery_app.task(name="submissions.run_publication")(_publication_impl)
)


async def enqueue_publication(
    *, tenant_id: uuid.UUID, submission_id: uuid.UUID, job_id: uuid.UUID
) -> str | None:
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _publication_async(tenant_id, submission_id, job_id)
        return f"eager:{job_id}"

    result = publication_task.delay(str(tenant_id), str(submission_id), str(job_id))
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None


async def _analytics_async(
    tenant_id: uuid.UUID, published_result_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    from app.db.session import async_session_factory, engine
    from app.services.analytics import materialize_published_result

    await engine.dispose()
    async with async_session_factory() as db:
        await materialize_published_result(
            db,
            tenant_id=tenant_id,
            published_result_id=published_result_id,
            job_id=job_id,
        )


def _analytics_impl(
    tenant_id: str, published_result_id: str, job_id: str
) -> dict[str, str]:
    asyncio.run(
        _analytics_async(
            uuid.UUID(tenant_id),
            uuid.UUID(published_result_id),
            uuid.UUID(job_id),
        )
    )
    return {
        "tenant_id": tenant_id,
        "published_result_id": published_result_id,
        "job_id": job_id,
        "status": "ok",
    }


analytics_task = cast(
    Any, celery_app.task(name="analytics.materialize_published_result")(_analytics_impl)
)


async def enqueue_analytics(
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
    job_id: uuid.UUID,
) -> str | None:
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _analytics_async(tenant_id, published_result_id, job_id)
        return f"eager:{job_id}"

    result = analytics_task.delay(
        str(tenant_id), str(published_result_id), str(job_id)
    )
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None

async def _learning_plan_async(tenant_id: uuid.UUID, run_id: uuid.UUID) -> None:
    from app.db.session import async_session_factory, engine
    from app.services.learning import run_learning_plan_pipeline

    await engine.dispose()
    async with async_session_factory() as db:
        await run_learning_plan_pipeline(db, tenant_id=tenant_id, run_id=run_id)


def _learning_plan_impl(tenant_id: str, run_id: str) -> dict[str, str]:
    asyncio.run(_learning_plan_async(uuid.UUID(tenant_id), uuid.UUID(run_id)))
    return {"tenant_id": tenant_id, "run_id": run_id, "status": "ok"}


learning_plan_task = cast(
    Any, celery_app.task(name="learning.generate_plan")(_learning_plan_impl)
)


async def enqueue_learning_plan(
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> str | None:
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _learning_plan_async(tenant_id, run_id)
        return f"eager:{run_id}"

    result = learning_plan_task.delay(str(tenant_id), str(run_id))
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None


async def _improvement_blueprint_async(
    tenant_id: uuid.UUID, blueprint_id: uuid.UUID
) -> None:
    from app.db.session import async_session_factory, engine
    from app.services.learning import run_blueprint_pipeline

    await engine.dispose()
    async with async_session_factory() as db:
        await run_blueprint_pipeline(db, tenant_id=tenant_id, blueprint_id=blueprint_id)


def _improvement_blueprint_impl(tenant_id: str, blueprint_id: str) -> dict[str, str]:
    asyncio.run(
        _improvement_blueprint_async(uuid.UUID(tenant_id), uuid.UUID(blueprint_id))
    )
    return {
        "tenant_id": tenant_id,
        "blueprint_id": blueprint_id,
        "status": "ok",
    }


improvement_blueprint_task = cast(
    Any,
    celery_app.task(name="learning.generate_improvement_blueprint")(
        _improvement_blueprint_impl
    ),
)


async def enqueue_improvement_blueprint(
    *,
    tenant_id: uuid.UUID,
    blueprint_id: uuid.UUID,
) -> str | None:
    settings = get_settings()
    if settings.celery_task_always_eager:
        await _improvement_blueprint_async(tenant_id, blueprint_id)
        return f"eager:{blueprint_id}"

    result = improvement_blueprint_task.delay(str(tenant_id), str(blueprint_id))
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id is not None else None
