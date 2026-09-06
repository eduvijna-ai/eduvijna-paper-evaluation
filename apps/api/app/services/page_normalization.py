"""Page normalization pipeline for submission evidence (B3)."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import fitz
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import AuditEvent, PipelineJob, Submission, SubmissionPage
from app.services.storage import ObjectStorage, derived_page_key
from app.services.upload_validation import sha256_bytes


class PageNormalizationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def run_page_normalization(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
    job_id: uuid.UUID,
    storage: ObjectStorage | None = None,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    storage = storage or ObjectStorage(settings)

    job = await db.scalar(
        select(PipelineJob).where(
            PipelineJob.id == job_id,
            PipelineJob.tenant_id == tenant_id,
        )
    )
    submission = await db.scalar(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.tenant_id == tenant_id,
        )
    )
    if job is None or submission is None:
        raise PageNormalizationError("NOT_FOUND", "Submission or job not found")

    job.status = "RUNNING"
    job.started_at = datetime.now(UTC)
    job.attempt = max(job.attempt, 1)
    submission.workflow_state = "PROCESSING"
    await db.commit()

    try:
        raw = storage.get_bytes(submission.source_storage_key)
        actual_hash = sha256_bytes(raw)
        if actual_hash != submission.source_content_sha256:
            db.add(
                AuditEvent(
                    tenant_id=tenant_id,
                    actor_user_id=submission.uploaded_by,
                    entity_type="Submission",
                    entity_id=submission.id,
                    action="source_integrity_mismatch",
                    payload_json={
                        "expected": submission.source_content_sha256,
                        "actual": actual_hash,
                    },
                )
            )
            raise PageNormalizationError(
                "SOURCE_INTEGRITY_MISMATCH",
                "Persisted source hash does not match stored object bytes",
            )

        pages = _render_pages(raw, submission.mime_type, settings.submission_max_pages)
        for index, (png_bytes, width, height) in enumerate(pages):
            key = derived_page_key(tenant_id, submission.id, index)
            storage.put_derived_bytes(key=key, body=png_bytes, content_type="image/png")
            existing = await db.scalar(
                select(SubmissionPage).where(
                    SubmissionPage.tenant_id == tenant_id,
                    SubmissionPage.submission_id == submission.id,
                    SubmissionPage.page_index == index,
                )
            )
            if existing is None:
                db.add(
                    SubmissionPage(
                        tenant_id=tenant_id,
                        submission_id=submission.id,
                        page_index=index,
                        image_storage_key=key,
                        width=width,
                        height=height,
                        is_continuation=index > 0,
                    )
                )
            else:
                existing.image_storage_key = key
                existing.width = width
                existing.height = height
                existing.is_continuation = index > 0

        # Drop stale pages beyond current count (idempotent shrink after prior larger render).
        stale = await db.scalars(
            select(SubmissionPage).where(
                SubmissionPage.tenant_id == tenant_id,
                SubmissionPage.submission_id == submission.id,
                SubmissionPage.page_index >= len(pages),
            )
        )
        for page in stale:
            await db.delete(page)

        submission.page_count = len(pages)
        submission.workflow_state = "IDENTITY_REVIEW"
        submission.student_match_state = "REVIEW_REQUIRED"
        submission.roll_number_detected = None
        submission.name_detected = None
        submission.identity_confidence = Decimal("0.0000")
        submission.mapping_confidence = Decimal("0.0000")
        job.status = "SUCCEEDED"
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        job.error_detail = None
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=submission.uploaded_by,
                entity_type="Submission",
                entity_id=submission.id,
                action="page_normalization_succeeded",
                payload_json={"page_count": len(pages), "job_id": str(job.id)},
            )
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        job = await db.scalar(select(PipelineJob).where(PipelineJob.id == job_id))
        submission = await db.scalar(select(Submission).where(Submission.id == submission_id))
        if job is not None and submission is not None:
            code = getattr(exc, "code", "PAGE_NORMALIZATION_FAILED")
            message = getattr(exc, "message", str(exc))
            job.status = "FAILED"
            job.error_code = str(code)[:100]
            job.error_detail = str(message)[:4000]
            job.finished_at = datetime.now(UTC)
            submission.workflow_state = "FAILED"
            await db.commit()
        raise


def _render_pages(
    raw: bytes, mime_type: str, max_pages: int
) -> list[tuple[bytes, int, int]]:
    if mime_type == "application/pdf":
        return _render_pdf(raw, max_pages)
    if mime_type in {"image/png", "image/jpeg"}:
        return [_render_image(raw)]
    raise PageNormalizationError("UNSUPPORTED_MEDIA_TYPE", f"Unsupported mime {mime_type}")


def _render_pdf(raw: bytes, max_pages: int) -> list[tuple[bytes, int, int]]:
    doc = fitz.open(stream=raw, filetype="pdf")
    try:
        if doc.page_count == 0:
            raise PageNormalizationError("EMPTY_DOCUMENT", "PDF has no pages")
        if doc.page_count > max_pages:
            raise PageNormalizationError(
                "TOO_MANY_PAGES",
                f"PDF has {doc.page_count} pages; maximum is {max_pages}",
            )
        rendered: list[tuple[bytes, int, int]] = []
        for index in range(doc.page_count):
            page = doc.load_page(index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            png = pix.tobytes("png")
            rendered.append((png, pix.width, pix.height))
        return rendered
    finally:
        doc.close()


def _render_image(raw: bytes) -> tuple[bytes, int, int]:
    with Image.open(io.BytesIO(raw)) as image:
        image = image.convert("RGB")
        width, height = image.size
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue(), width, height
