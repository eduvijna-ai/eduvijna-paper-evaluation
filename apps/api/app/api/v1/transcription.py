# ruff: noqa: B008
"""B5 transcription review API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.models import AnswerRegion, AnswerRegionTranscription, Submission, SubmissionPage
from app.db.session import get_db_session
from app.services.crop_generation import ensure_region_crop
from app.services.storage import ObjectStorage, StorageNotFoundError
from app.services.transcription import (
    TranscriptionError,
    build_transcription_workspace,
    confirm_transcription,
    ensure_transcription_job_and_state,
    finalize_transcription,
    put_manual_transcription,
)
from app.tasks.celery_app import enqueue_transcription

router = APIRouter(tags=["transcription"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _http_error(
    status: int, code: str, message: str, **extra: Any
) -> HTTPException:
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


class ManualTranscriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=20_000)
    latex: str | None = Field(default=None, max_length=20_000)
    unreadable: bool = False
    visual_only: bool = False
    outcome: Literal["TRANSCRIBED", "UNREADABLE", "VISUAL_ONLY"] | None = None


@router.post("/submissions/{submission_id}/transcription/prepare")
async def prepare_transcription(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("transcription:review")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    try:
        job = await ensure_transcription_job_and_state(
            db, tenant_id=auth.tenant_id, submission=item
        )
    except TranscriptionError as exc:
        raise _http_error(409, exc.code, exc.message) from exc
    await db.commit()
    if job is not None and job.status == "QUEUED":
        task_id = await enqueue_transcription(
            tenant_id=auth.tenant_id,
            submission_id=item.id,
            job_id=job.id,
        )
        if task_id:
            job.celery_task_id = task_id
            await db.commit()
    await db.refresh(item)
    return {
        "submission_id": str(item.id),
        "workflow_state": item.workflow_state,
        "transcription_state": item.transcription_state,
        "job_id": str(job.id) if job else None,
    }


@router.get("/submissions/{submission_id}/transcription")
async def get_transcription_workspace(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("transcription:read")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    return await build_transcription_workspace(
        db, tenant_id=auth.tenant_id, submission=item
    )


@router.put("/answer-regions/{region_id}/transcription")
async def put_region_transcription(
    region_id: uuid.UUID,
    payload: ManualTranscriptionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("transcription:review")),
) -> dict[str, Any]:
    region = await db.scalar(
        select(AnswerRegion).where(
            AnswerRegion.id == region_id,
            AnswerRegion.tenant_id == auth.tenant_id,
        )
    )
    if region is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")

    unreadable = payload.unreadable or payload.outcome == "UNREADABLE"
    visual_only = payload.visual_only or payload.outcome == "VISUAL_ONLY"
    text = payload.text
    if unreadable or visual_only:
        text = None

    row = await put_manual_transcription(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        region=region,
        text=text,
        latex=None if (unreadable or visual_only) else payload.latex,
        unreadable=unreadable,
        visual_only=visual_only,
    )
    await db.commit()
    await db.refresh(row)
    return {
        "id": str(row.id),
        "answer_region_id": str(row.answer_region_id),
        "version_number": row.version_number,
        "source_type": row.source_type,
        "text": row.text,
        "latex": row.latex,
        "segments": row.segments or [],
        "transcription_confidence": None,
        "unreadable": row.unreadable,
        "visual_only": row.visual_only,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("/answer-region-transcriptions/{transcription_id}/confirm")
async def confirm_region_transcription(
    transcription_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("transcription:review")),
) -> dict[str, Any]:
    row = await db.scalar(
        select(AnswerRegionTranscription).where(
            AnswerRegionTranscription.id == transcription_id,
            AnswerRegionTranscription.tenant_id == auth.tenant_id,
        )
    )
    if row is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    try:
        row = await confirm_transcription(
            db,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            transcription=row,
        )
    except TranscriptionError as exc:
        raise _http_error(409, exc.code, exc.message) from exc
    await db.commit()
    await db.refresh(row)
    return {
        "id": str(row.id),
        "answer_region_id": str(row.answer_region_id),
        "version_number": row.version_number,
        "source_type": row.source_type,
        "text": row.text,
        "latex": row.latex,
        "segments": row.segments or [],
        "transcription_confidence": (
            float(row.transcription_confidence)
            if row.transcription_confidence is not None
            else None
        ),
        "unreadable": row.unreadable,
        "visual_only": row.visual_only,
        "status": row.status,
        "confirmed_by": str(row.confirmed_by) if row.confirmed_by else None,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
    }


@router.post("/submissions/{submission_id}/transcription/finalize")
async def finalize_submission_transcription(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("transcription:review")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    try:
        item = await finalize_transcription(
            db, tenant_id=auth.tenant_id, submission=item
        )
    except TranscriptionError as exc:
        raise _http_error(409, exc.code, exc.message) from exc
    await db.commit()
    await db.refresh(item)
    return {
        "submission_id": str(item.id),
        "workflow_state": item.workflow_state,
        "transcription_state": item.transcription_state,
        "evaluation_enqueued": False,
    }


@router.get("/answer-regions/{region_id}/crop")
async def get_region_crop(
    region_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("transcription:read")),
) -> StreamingResponse:
    region = await db.scalar(
        select(AnswerRegion).where(
            AnswerRegion.id == region_id,
            AnswerRegion.tenant_id == auth.tenant_id,
        )
    )
    if region is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    page = await db.scalar(
        select(SubmissionPage).where(
            SubmissionPage.id == region.submission_page_id,
            SubmissionPage.tenant_id == auth.tenant_id,
        )
    )
    if page is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    storage = ObjectStorage()
    try:
        if not region.crop_storage_key:
            key, _ = await ensure_region_crop(
                db,
                tenant_id=auth.tenant_id,
                submission_id=page.submission_id,
                region=region,
                page=page,
                storage=storage,
            )
            await db.commit()
        else:
            key = region.crop_storage_key
        body = storage.get_bytes(key)
    except (StorageNotFoundError, PermissionError, ValueError) as exc:
        raise _http_error(404, "NOT_FOUND", "Crop not available") from exc
    return StreamingResponse(iter([body]), media_type="image/png")
