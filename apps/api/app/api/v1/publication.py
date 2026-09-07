# ruff: noqa: B008
"""B7 publication / reports / annotated paper API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.models import Submission
from app.db.session import get_db_session
from app.services.publication import (
    PublicationError,
    add_manual_annotation,
    get_artifact_bytes,
    get_publication_workspace,
    get_published_result_for_consumer,
    get_report_preview,
    get_scoped_published_result,
    prepare_publication,
    publish_result,
    regenerate_publication,
    resolve_audience_report,
)
from app.tasks.celery_app import enqueue_publication

router = APIRouter(tags=["publication"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _http_error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message, **extra},
    )


async def _scoped_submission(
    db: AsyncSession, submission_id: uuid.UUID, tenant_id: uuid.UUID
) -> Submission:
    item = await db.scalar(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    return item


class ManualAnnotationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_type: Literal["COMMENT", "HIGHLIGHT"]
    submission_page_id: uuid.UUID
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/submissions/{submission_id}/publication/prepare")
async def prepare_submission_publication(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:generate")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    try:
        result, job = await prepare_publication(
            db,
            tenant_id=auth.tenant_id,
            submission=item,
            actor_user_id=auth.user_id,
        )
    except PublicationError as exc:
        raise _http_error(409, exc.code, exc.message) from exc
    await db.commit()

    if job is not None and job.status == "QUEUED":
        task_id = await enqueue_publication(
            tenant_id=auth.tenant_id,
            submission_id=item.id,
            job_id=job.id,
        )
        if task_id:
            job.celery_task_id = task_id
            await db.commit()

    await db.refresh(item)
    await db.refresh(result)
    return {
        "submission_id": str(item.id),
        "workflow_state": item.workflow_state,
        "published_result_id": str(result.id),
        "status": result.status,
        "version_number": result.version_number,
        "job_id": str(job.id) if job else None,
    }


@router.get("/submissions/{submission_id}/publication")
async def get_submission_publication(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:read")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    return await get_publication_workspace(
        db, tenant_id=auth.tenant_id, submission=item
    )


@router.get("/submissions/{submission_id}/published-result")
async def get_submission_published_result(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:read")),
) -> dict[str, Any]:
    await _scoped_submission(db, submission_id, auth.tenant_id)
    try:
        return await get_published_result_for_consumer(
            db, tenant_id=auth.tenant_id, submission_id=submission_id
        )
    except PublicationError as exc:
        raise _http_error(404, exc.code, exc.message) from exc


@router.post("/publication-results/{published_result_id}/regenerate")
async def regenerate_published_result(
    published_result_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:generate")),
) -> dict[str, Any]:
    try:
        result, job = await regenerate_publication(
            db,
            tenant_id=auth.tenant_id,
            published_result_id=published_result_id,
            actor_user_id=auth.user_id,
        )
    except PublicationError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 409
        raise _http_error(status, exc.code, exc.message) from exc
    await db.commit()

    if job.status == "QUEUED":
        task_id = await enqueue_publication(
            tenant_id=auth.tenant_id,
            submission_id=result.submission_id,
            job_id=job.id,
        )
        if task_id:
            job.celery_task_id = task_id
            await db.commit()

    return {
        "published_result_id": str(result.id),
        "status": result.status,
        "version_number": result.version_number,
        "job_id": str(job.id),
        "supersedes_result_id": str(result.supersedes_result_id)
        if result.supersedes_result_id
        else None,
    }


@router.post("/publication-results/{published_result_id}/publish")
async def publish_published_result(
    published_result_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:publish")),
) -> dict[str, Any]:
    import logging

    logger = logging.getLogger(__name__)
    try:
        result, analytics_job = await publish_result(
            db,
            tenant_id=auth.tenant_id,
            published_result_id=published_result_id,
            actor_user_id=auth.user_id,
        )
    except PublicationError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 409
        raise _http_error(status, exc.code, exc.message) from exc
    await db.commit()

    # Enqueue analytics after academic publish commits. Broker failure must not unpublish.
    try:
        from app.tasks.celery_app import enqueue_analytics

        task_id = await enqueue_analytics(
            tenant_id=auth.tenant_id,
            published_result_id=result.id,
            job_id=analytics_job.id,
        )
        if task_id:
            analytics_job.celery_task_id = task_id
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "analytics enqueue failed after publish published_result_id=%s",
            published_result_id,
        )

    return {
        "published_result_id": str(result.id),
        "status": result.status,
        "submission_id": str(result.submission_id),
        "published_at": result.published_at.isoformat() if result.published_at else None,
        "analytics_job_id": str(analytics_job.id),
    }


@router.get("/publication-results/{published_result_id}/artifacts/{artifact_type}")
async def download_publication_artifact(
    published_result_id: uuid.UUID,
    artifact_type: str,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:read")),
) -> Response:
    try:
        data, filename = await get_artifact_bytes(
            db,
            tenant_id=auth.tenant_id,
            published_result_id=published_result_id,
            artifact_type=artifact_type,
        )
    except PublicationError as exc:
        status = 404 if exc.code in {"NOT_FOUND", "ARTIFACT_MISSING"} else 409
        raise _http_error(status, exc.code, exc.message) from exc
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/publication-results/{published_result_id}/reports/{audience}")
async def preview_publication_report(
    published_result_id: uuid.UUID,
    audience: Literal["student", "parent", "teacher"],
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:read")),
) -> dict[str, Any]:
    try:
        return await get_report_preview(
            db,
            tenant_id=auth.tenant_id,
            published_result_id=published_result_id,
            audience=audience,
        )
    except PublicationError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 409
        raise _http_error(status, exc.code, exc.message) from exc


@router.post("/publication-results/{published_result_id}/annotations")
async def create_manual_annotation(
    published_result_id: uuid.UUID,
    body: ManualAnnotationIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:generate")),
) -> dict[str, Any]:
    try:
        await get_scoped_published_result(
            db, tenant_id=auth.tenant_id, published_result_id=published_result_id
        )
        ann = await add_manual_annotation(
            db,
            tenant_id=auth.tenant_id,
            published_result_id=published_result_id,
            actor_user_id=auth.user_id,
            annotation_type=body.annotation_type,
            submission_page_id=body.submission_page_id,
            x=body.x,
            y=body.y,
            width=body.width,
            height=body.height,
            payload=body.payload,
        )
    except PublicationError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 409
        raise _http_error(status, exc.code, exc.message) from exc
    await db.commit()
    return {
        "id": str(ann.id),
        "annotation_type": ann.annotation_type,
        "submission_page_id": str(ann.submission_page_id),
        "x": ann.x,
        "y": ann.y,
        "width": ann.width,
        "height": ann.height,
        "payload": ann.payload or {},
        "source_type": ann.source_type,
    }


@router.get("/reports/student/{student_id}/assessments/{assessment_id}")
async def get_student_audience_report(
    student_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:read")),
) -> dict[str, Any]:
    try:
        return await resolve_audience_report(
            db,
            tenant_id=auth.tenant_id,
            student_id=student_id,
            assessment_id=assessment_id,
            audience="student",
        )
    except PublicationError as exc:
        raise _http_error(404, exc.code, exc.message) from exc


@router.get("/reports/parent/{student_id}/assessments/{assessment_id}")
async def get_parent_audience_report(
    student_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:read")),
) -> dict[str, Any]:
    try:
        return await resolve_audience_report(
            db,
            tenant_id=auth.tenant_id,
            student_id=student_id,
            assessment_id=assessment_id,
            audience="parent",
        )
    except PublicationError as exc:
        raise _http_error(404, exc.code, exc.message) from exc


@router.get("/reports/teacher/{student_id}/assessments/{assessment_id}")
async def get_teacher_audience_report(
    student_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("publication:read")),
) -> dict[str, Any]:
    try:
        return await resolve_audience_report(
            db,
            tenant_id=auth.tenant_id,
            student_id=student_id,
            assessment_id=assessment_id,
            audience="teacher",
        )
    except PublicationError as exc:
        raise _http_error(404, exc.code, exc.message) from exc
