# ruff: noqa: B008
"""B8 analytics and mastery-evidence API."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.session import get_db_session
from app.services.analytics import (
    AnalyticsError,
    get_assessment_analytics,
    get_student_analytics,
    list_student_mastery_evidence,
    prepare_analytics_materialization,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )


@router.get("/analytics/assessments/{assessment_id}")
async def assessment_analytics(
    assessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("analytics:read")),
    pass_threshold_percent: float | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return await get_assessment_analytics(
            db,
            tenant_id=auth.tenant_id,
            assessment_id=assessment_id,
            pass_threshold_percent=pass_threshold_percent,
        )
    except AnalyticsError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 400
        raise _http_error(status, exc.code, exc.message) from exc


@router.get("/analytics/students/{student_id}")
async def student_analytics(
    student_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("analytics:read")),
) -> dict[str, Any]:
    try:
        return await get_student_analytics(
            db, tenant_id=auth.tenant_id, student_id=student_id
        )
    except AnalyticsError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 400
        raise _http_error(status, exc.code, exc.message) from exc


@router.get("/analytics/students/{student_id}/mastery-evidence")
async def student_mastery_evidence(
    student_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("analytics:read")),
    assessment_id: uuid.UUID | None = None,
    curriculum_id: uuid.UUID | None = None,
    curriculum_node_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    try:
        return await list_student_mastery_evidence(
            db,
            tenant_id=auth.tenant_id,
            student_id=student_id,
            assessment_id=assessment_id,
            curriculum_id=curriculum_id,
            curriculum_node_id=curriculum_node_id,
        )
    except AnalyticsError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 400
        raise _http_error(status, exc.code, exc.message) from exc


@router.post("/analytics/published-results/{published_result_id}/prepare")
async def prepare_published_result_analytics(
    published_result_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("analytics:materialize")),
) -> dict[str, Any]:
    try:
        published, job = await prepare_analytics_materialization(
            db,
            tenant_id=auth.tenant_id,
            published_result_id=published_result_id,
        )
    except AnalyticsError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 409
        raise _http_error(status, exc.code, exc.message) from exc

    await db.commit()

    task_id: str | None = None
    enqueue_error: str | None = None
    if job.status != "SUCCEEDED":
        try:
            from app.tasks.celery_app import enqueue_analytics

            task_id = await enqueue_analytics(
                tenant_id=auth.tenant_id,
                published_result_id=published.id,
                job_id=job.id,
            )
            if task_id:
                job.celery_task_id = task_id
                await db.commit()
        except Exception as exc:  # noqa: BLE001 — publication must not reverse
            enqueue_error = str(exc)[:300]
            logger.exception(
                "analytics enqueue failed published_result_id=%s", published_result_id
            )

    return {
        "published_result_id": str(published.id),
        "pipeline_job_id": str(job.id),
        "job_status": job.status,
        "celery_task_id": task_id or job.celery_task_id,
        "enqueue_error": enqueue_error,
        "algorithm_version": "B8_V1",
    }
