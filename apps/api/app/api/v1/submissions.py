# ruff: noqa: B008
"""B3 submission ingestion, page access, and identity review APIs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.core.config import get_settings
from app.db.models import (
    Assessment,
    AssessmentVersion,
    AuditEvent,
    Institution,
    PipelineJob,
    Student,
    Submission,
    SubmissionPage,
)
from app.db.session import get_db_session
from app.services.storage import ObjectStorage, StorageImmutabilityError, raw_object_key
from app.services.upload_validation import validate_and_buffer_upload
from app.tasks import enqueue_page_normalization

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db_session)]


class IdentityConfirmIn(BaseModel):
    student_id: uuid.UUID


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


async def _audit(
    db: AsyncSession,
    auth: AuthContext,
    entity: Any,
    action: str,
    payload: dict[str, Any],
) -> None:
    db.add(
        AuditEvent(
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            entity_type=entity.__class__.__name__,
            entity_id=entity.id,
            action=action,
            payload_json=payload,
        )
    )


def _dump_submission(
    item: Submission,
    *,
    assessment_title: str | None = None,
    student_display_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "tenant_id": str(item.tenant_id),
        "assessment_id": str(item.assessment_id),
        "assessment_version_id": str(item.assessment_version_id),
        "assessment_title": assessment_title,
        "student_id": str(item.student_id) if item.student_id else None,
        "student_display_name": student_display_name,
        "workflow_state": item.workflow_state,
        "student_match_state": item.student_match_state,
        "roll_number_detected": item.roll_number_detected,
        "name_detected": item.name_detected,
        "identity_confidence": float(item.identity_confidence),
        "mapping_confidence": float(item.mapping_confidence),
        "source_storage_key": item.source_storage_key,
        "source_content_sha256": item.source_content_sha256,
        "original_filename": item.original_filename,
        "mime_type": item.mime_type,
        "byte_size": item.byte_size,
        "storage_status": item.storage_status,
        "page_count": item.page_count,
        "bundle_name": item.bundle_name,
        "uploaded_by": str(item.uploaded_by),
        "uploaded_at": item.uploaded_at.isoformat(),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _dump_page(page: SubmissionPage) -> dict[str, Any]:
    return {
        "id": str(page.id),
        "tenant_id": str(page.tenant_id),
        "submission_id": str(page.submission_id),
        "page_index": page.page_index,
        "page_number": page.page_index + 1,
        "label": f"Page {page.page_index + 1}",
        "width": page.width,
        "height": page.height,
        "is_continuation": page.is_continuation,
        "created_at": page.created_at.isoformat(),
    }


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


async def _assessment_title(db: AsyncSession, assessment_id: uuid.UUID) -> str | None:
    title = await db.scalar(select(Assessment.title).where(Assessment.id == assessment_id))
    return str(title) if title is not None else None


async def _student_name(db: AsyncSession, student_id: uuid.UUID | None) -> str | None:
    if student_id is None:
        return None
    name = await db.scalar(select(Student.full_name).where(Student.id == student_id))
    return str(name) if name is not None else None


async def _resolve_active_version(
    db: AsyncSession, assessment: Assessment, tenant_id: uuid.UUID
) -> AssessmentVersion:
    version = await db.scalar(
        select(AssessmentVersion)
        .where(
            AssessmentVersion.assessment_id == assessment.id,
            AssessmentVersion.tenant_id == tenant_id,
        )
        .order_by(AssessmentVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise _http_error(409, "ASSESSMENT_VERSION_MISSING", "Assessment has no versions")
    return version


@router.post("/submissions", status_code=201)
async def upload_submission(
    db: Db,
    assessment_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    auth: AuthContext = Depends(require_permissions("submission:upload")),
    bundle_name: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    settings = get_settings()
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.tenant_id == auth.tenant_id,
        )
    )
    if assessment is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    if assessment.status != "ACTIVE":
        raise _http_error(
            409,
            "ASSESSMENT_NOT_ACTIVE",
            "Uploads are only allowed for ACTIVE assessments",
        )

    version = await _resolve_active_version(db, assessment, auth.tenant_id)
    validated = await validate_and_buffer_upload(
        file, max_bytes=settings.submission_upload_max_bytes
    )

    duplicate = await db.scalar(
        select(Submission.id).where(
            Submission.tenant_id == auth.tenant_id,
            Submission.assessment_id == assessment.id,
            Submission.source_content_sha256 == validated.content_sha256,
        )
    )
    if duplicate is not None:
        raise _http_error(
            409,
            "DUPLICATE_SUBMISSION_SOURCE",
            "An identical source file already exists for this assessment",
        )

    storage = ObjectStorage(settings)
    try:
        storage.ensure_bucket()
    except Exception:
        # Bucket bootstrap is best-effort for local/CI; production should pre-provision.
        pass

    key = raw_object_key(auth.tenant_id, validated.content_sha256, validated.filename)
    now = datetime.now(UTC)
    submission = Submission(
        tenant_id=auth.tenant_id,
        assessment_id=assessment.id,
        assessment_version_id=version.id,
        student_id=None,
        workflow_state="UPLOADED",
        student_match_state="REVIEW_REQUIRED",
        roll_number_detected=None,
        name_detected=None,
        identity_confidence=Decimal("0.0000"),
        mapping_confidence=Decimal("0.0000"),
        source_storage_key=key,
        source_content_sha256=validated.content_sha256,
        original_filename=validated.filename,
        mime_type=validated.mime_type,
        byte_size=validated.byte_size,
        storage_status="PENDING",
        page_count=0,
        bundle_name=bundle_name or validated.filename,
        uploaded_by=auth.user_id,
        uploaded_at=now,
    )
    db.add(submission)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _http_error(
            409,
            "DUPLICATE_SUBMISSION_SOURCE",
            "An identical source file already exists for this assessment",
        ) from exc

    try:
        storage.put_raw_bytes(
            key=key, body=validated.body, content_type=validated.mime_type
        )
    except StorageImmutabilityError as exc:
        submission.storage_status = "FAILED"
        submission.workflow_state = "FAILED"
        await _audit(
            db,
            auth,
            submission,
            "source_upload_failed",
            {"reason": "immutable_key_collision", "key": key},
        )
        await db.commit()
        raise _http_error(
            409,
            "STORAGE_KEY_COLLISION",
            "Raw source key already exists and cannot be overwritten",
        ) from exc
    except Exception as exc:
        submission.storage_status = "FAILED"
        submission.workflow_state = "FAILED"
        await _audit(
            db,
            auth,
            submission,
            "source_upload_failed",
            {"reason": str(exc)[:500]},
        )
        await db.commit()
        raise _http_error(502, "STORAGE_UPLOAD_FAILED", "Failed to store raw source") from exc

    submission.storage_status = "AVAILABLE"
    job = PipelineJob(
        tenant_id=auth.tenant_id,
        submission_id=submission.id,
        stage="PAGE_NORMALIZATION",
        status="QUEUED",
        attempt=1,
        idempotency_key=f"page-norm:{submission.id}:v1",
    )
    db.add(job)
    await _audit(
        db,
        auth,
        submission,
        "uploaded",
        {
            "assessment_id": str(assessment.id),
            "assessment_version_id": str(version.id),
            "sha256": validated.content_sha256,
            "byte_size": validated.byte_size,
            "mime_type": validated.mime_type,
        },
    )
    await db.commit()
    await db.refresh(submission)
    await db.refresh(job)

    task_id = await enqueue_page_normalization(
        tenant_id=auth.tenant_id,
        submission_id=submission.id,
        job_id=job.id,
    )
    if task_id:
        job.celery_task_id = task_id
        await db.commit()

    return _dump_submission(submission, assessment_title=assessment.title)


@router.get("/submissions")
async def list_submissions(
    db: Db,
    auth: AuthContext = Depends(require_permissions("submission:read")),
    assessment_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    query = select(Submission).where(Submission.tenant_id == auth.tenant_id)
    if assessment_id is not None:
        query = query.where(Submission.assessment_id == assessment_id)
    rows = (
        await db.scalars(query.order_by(Submission.uploaded_at.desc()))
    ).all()
    titles = {
        row.id: title
        for row, title in (
            await db.execute(
                select(Assessment.id, Assessment.title).where(
                    Assessment.tenant_id == auth.tenant_id,
                    Assessment.id.in_({item.assessment_id for item in rows} or {uuid.uuid4()}),
                )
            )
        ).all()
    }
    student_names = {
        row.id: name
        for row, name in (
            await db.execute(
                select(Student.id, Student.full_name).where(
                    Student.tenant_id == auth.tenant_id,
                    Student.id.in_(
                        {item.student_id for item in rows if item.student_id} or {uuid.uuid4()}
                    ),
                )
            )
        ).all()
    }
    return [
        _dump_submission(
            item,
            assessment_title=titles.get(item.assessment_id),
            student_display_name=student_names.get(item.student_id) if item.student_id else None,
        )
        for item in rows
    ]


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("submission:read")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    return _dump_submission(
        item,
        assessment_title=await _assessment_title(db, item.assessment_id),
        student_display_name=await _student_name(db, item.student_id),
    )


@router.get("/submissions/{submission_id}/pages")
async def list_submission_pages(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("submission:read")),
) -> list[dict[str, Any]]:
    await _scoped_submission(db, submission_id, auth.tenant_id)
    pages = (
        await db.scalars(
            select(SubmissionPage)
            .where(
                SubmissionPage.tenant_id == auth.tenant_id,
                SubmissionPage.submission_id == submission_id,
            )
            .order_by(SubmissionPage.page_index)
        )
    ).all()
    return [_dump_page(page) for page in pages]


@router.get("/submissions/{submission_id}/source")
async def get_submission_source(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("submission:read")),
) -> Response:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    if item.storage_status != "AVAILABLE":
        raise _http_error(409, "SOURCE_NOT_AVAILABLE", "Raw source is not available")
    storage = ObjectStorage()
    body = storage.get_bytes(item.source_storage_key)
    await _audit(
        db,
        auth,
        item,
        "source_accessed",
        {"byte_size": item.byte_size, "mime_type": item.mime_type},
    )
    await db.commit()
    return Response(
        content=body,
        media_type=item.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{item.original_filename}"',
            "X-Content-SHA256": item.source_content_sha256,
        },
    )


@router.get("/submission-pages/{page_id}/image")
async def get_submission_page_image(
    page_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("submission:read")),
) -> StreamingResponse:
    page = await db.scalar(
        select(SubmissionPage).where(
            SubmissionPage.id == page_id,
            SubmissionPage.tenant_id == auth.tenant_id,
        )
    )
    if page is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    storage = ObjectStorage()
    body = storage.get_bytes(page.image_storage_key)

    def _iter() -> Any:
        yield body

    return StreamingResponse(
        _iter(),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.get("/submissions/{submission_id}/identity")
async def get_identity_review(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("submission:read")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    pages = (
        await db.scalars(
            select(SubmissionPage)
            .where(
                SubmissionPage.tenant_id == auth.tenant_id,
                SubmissionPage.submission_id == submission_id,
            )
            .order_by(SubmissionPage.page_index)
        )
    ).all()
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == item.assessment_id,
            Assessment.tenant_id == auth.tenant_id,
        )
    )
    if assessment is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")

    institution = await db.scalar(
        select(Institution).where(Institution.tenant_id == auth.tenant_id).limit(1)
    )
    student_query = select(Student).where(
        Student.tenant_id == auth.tenant_id,
        Student.status == "active",
    )
    if assessment.class_section_id is not None:
        student_query = student_query.where(
            Student.class_section_id == assessment.class_section_id
        )
    elif institution is not None:
        student_query = student_query.where(Student.institution_id == institution.id)

    students = (
        await db.scalars(
            student_query.order_by(Student.full_name.asc(), Student.student_code.asc()).limit(100)
        )
    ).all()

    candidates = [
        {
            "student_id": str(student.id),
            "display_name": student.full_name,
            "external_ref": student.student_code,
            "grade": "",
            "section": "",
            "confidence": 0.0,
            "match_reasons": [
                "Manual roster selection — automated identity extraction is not active in B3"
            ],
        }
        for student in students
    ]
    return {
        "submission": _dump_submission(
            item,
            assessment_title=assessment.title,
            student_display_name=await _student_name(db, item.student_id),
        ),
        "pages": [_dump_page(page) for page in pages],
        "candidates": candidates,
        "automated_matching_active": False,
    }


@router.post("/submissions/{submission_id}/identity/confirm")
async def confirm_identity(
    submission_id: uuid.UUID,
    payload: IdentityConfirmIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("submission:review")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == item.assessment_id,
            Assessment.tenant_id == auth.tenant_id,
        )
    )
    if assessment is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")

    student = await db.scalar(
        select(Student).where(
            Student.id == payload.student_id,
            Student.tenant_id == auth.tenant_id,
            Student.status == "active",
        )
    )
    if student is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    if (
        assessment.class_section_id is not None
        and student.class_section_id != assessment.class_section_id
    ):
        raise _http_error(
            409,
            "STUDENT_COHORT_MISMATCH",
            "Student is not in the assessment class section",
        )

    item.student_id = student.id
    item.student_match_state = "CONFIRMED"
    item.workflow_state = "PROCESSING"
    await _audit(
        db,
        auth,
        item,
        "identity_confirmed",
        {"student_id": str(student.id), "actor": str(auth.user_id)},
    )
    await db.commit()
    await db.refresh(item)
    return _dump_submission(
        item,
        assessment_title=assessment.title,
        student_display_name=student.full_name,
    )


@router.post("/submissions/{submission_id}/identity/unmatched")
async def mark_identity_unmatched(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("submission:review")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    item.student_id = None
    item.student_match_state = "UNMATCHED"
    item.workflow_state = "IDENTITY_REVIEW"
    await _audit(
        db,
        auth,
        item,
        "identity_unmatched",
        {"actor": str(auth.user_id)},
    )
    await db.commit()
    await db.refresh(item)
    return _dump_submission(
        item,
        assessment_title=await _assessment_title(db, item.assessment_id),
        student_display_name=None,
    )
