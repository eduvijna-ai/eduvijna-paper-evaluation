"""B10 assessment question-paper artifact upload (scan → store → link)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext
from app.core.config import Settings, get_settings
from app.db.models import (
    Assessment,
    AssessmentArtifact,
    AssessmentVersion,
    QuestionVersion,
)
from app.services.audit import add_audit_event
from app.services.storage import (
    ObjectStorage,
    StorageImmutabilityError,
    assessment_source_key,
)
from app.services.upload_scanner import UploadScanResult, get_upload_scanner
from app.services.upload_validation import ValidatedUpload, validate_and_buffer_upload


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def dump_assessment_artifact(item: AssessmentArtifact) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "tenant_id": str(item.tenant_id),
        "assessment_id": str(item.assessment_id),
        "artifact_type": item.artifact_type,
        "original_filename": item.original_filename,
        "mime_type": item.mime_type,
        "byte_size": item.byte_size,
        "content_sha256": item.content_sha256,
        "storage_key": item.storage_key,
        "security_scan_status": item.security_scan_status,
        "uploaded_by": str(item.uploaded_by) if item.uploaded_by else None,
        "uploaded_at": item.uploaded_at.isoformat(),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


async def get_assessment_artifact(
    db: AsyncSession, *, tenant_id: uuid.UUID, artifact_id: uuid.UUID
) -> AssessmentArtifact:
    artifact = await db.scalar(
        select(AssessmentArtifact).where(
            AssessmentArtifact.id == artifact_id,
            AssessmentArtifact.tenant_id == tenant_id,
        )
    )
    if artifact is None:
        raise _http_error(404, "NOT_FOUND", "Assessment artifact not found")
    return artifact


async def enforce_upload_scan(
    *,
    filename: str,
    mime_type: str,
    content: bytes,
    settings: Settings | None = None,
) -> UploadScanResult:
    """Run scan hook; reject before any storage write on REJECTED/ERROR."""
    scanner = get_upload_scanner(settings)
    result = await scanner.scan(filename=filename, mime_type=mime_type, content=content)
    if result.status == "REJECTED":
        raise _http_error(
            422,
            "MALWARE_DETECTED",
            "Upload rejected by security scanner",
        )
    if result.status == "ERROR":
        raise _http_error(
            502,
            "UPLOAD_SCAN_FAILED",
            "Upload security scan failed",
        )
    return result


async def upload_question_paper(
    db: AsyncSession,
    *,
    auth: AuthContext,
    version_id: uuid.UUID,
    file: UploadFile,
    settings: Settings | None = None,
) -> AssessmentArtifact:
    settings = settings or get_settings()
    version = await db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.id == version_id,
            AssessmentVersion.tenant_id == auth.tenant_id,
        )
    )
    if version is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    if version.status != "DRAFT":
        raise _http_error(
            409,
            "ASSESSMENT_VERSION_NOT_DRAFT",
            "Question paper uploads are only allowed for DRAFT versions",
        )

    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == version.assessment_id,
            Assessment.tenant_id == auth.tenant_id,
        )
    )
    if assessment is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")

    question_count = await db.scalar(
        select(func.count())
        .select_from(QuestionVersion)
        .where(
            QuestionVersion.tenant_id == auth.tenant_id,
            QuestionVersion.assessment_version_id == version.id,
        )
    )
    if question_count and int(question_count) > 0:
        raise _http_error(
            409,
            "QUESTION_PAPER_STRUCTURE_EXISTS",
            "Assessment version already has applied questions",
        )

    validated: ValidatedUpload = await validate_and_buffer_upload(
        file, max_bytes=settings.assessment_paper_upload_max_bytes
    )
    scan = await enforce_upload_scan(
        filename=validated.filename,
        mime_type=validated.mime_type,
        content=validated.body,
        settings=settings,
    )

    artifact_id = uuid.uuid4()
    key = assessment_source_key(
        auth.tenant_id, assessment.id, artifact_id, validated.filename
    )
    now = datetime.now(UTC)
    artifact = AssessmentArtifact(
        id=artifact_id,
        tenant_id=auth.tenant_id,
        assessment_id=assessment.id,
        artifact_type="QUESTION_PAPER",
        original_filename=validated.filename,
        mime_type=validated.mime_type,
        byte_size=validated.byte_size,
        content_sha256=validated.content_sha256,
        storage_key=key,
        security_scan_status=scan.status,
        uploaded_by=auth.user_id,
        uploaded_at=now,
    )
    db.add(artifact)
    version.question_paper_artifact_id = artifact.id
    await db.flush()

    storage = ObjectStorage(settings)
    try:
        storage.ensure_bucket()
    except Exception:
        pass

    try:
        storage.put_assessment_source_bytes(
            key=key, body=validated.body, content_type=validated.mime_type
        )
    except StorageImmutabilityError as exc:
        await db.rollback()
        raise _http_error(
            409,
            "STORAGE_KEY_COLLISION",
            "Assessment source key already exists and cannot be overwritten",
        ) from exc
    except Exception as exc:
        await db.rollback()
        raise _http_error(
            502, "STORAGE_UPLOAD_FAILED", "Failed to store assessment source"
        ) from exc

    await add_audit_event(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        entity_type="AssessmentArtifact",
        entity_id=artifact.id,
        action="question_paper_uploaded",
        after={
            "assessment_version_id": str(version.id),
            "security_scan_status": scan.status,
            "content_sha256": validated.content_sha256,
        },
    )
    await db.commit()
    await db.refresh(artifact)
    return artifact
