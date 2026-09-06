"""AI identity extraction pipeline (B5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import get_structure_provider, structure_provider_active
from app.ai.tracing import (
    canonical_input_hash,
    record_ai_execution,
    redacted_request_summary,
)
from app.ai.types import IdentityExtractionInput, ProviderUnavailable
from app.core.config import Settings, get_settings
from app.db.models import (
    Assessment,
    AuditEvent,
    PipelineJob,
    Student,
    Submission,
    SubmissionIdentityCandidate,
    SubmissionPage,
)


class IdentityPipelineError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def run_identity_extraction(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
    job_id: uuid.UUID,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
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
        raise IdentityPipelineError("NOT_FOUND", "Submission or job not found")

    if job.status == "SUCCEEDED" and submission.workflow_state == "IDENTITY_REVIEW":
        return

    job.status = "RUNNING"
    job.started_at = datetime.now(UTC)
    job.attempt = max(job.attempt, 1)
    submission.workflow_state = "PROCESSING"
    await db.commit()

    try:
        if not structure_provider_active(settings):
            submission.workflow_state = "IDENTITY_REVIEW"
            submission.student_match_state = "REVIEW_REQUIRED"
            submission.identity_confidence = Decimal("0.0000")
            job.status = "SUCCEEDED"
            job.finished_at = datetime.now(UTC)
            db.add(
                AuditEvent(
                    tenant_id=tenant_id,
                    actor_user_id=None,
                    entity_type="Submission",
                    entity_id=submission.id,
                    action="identity_provider_unavailable",
                    payload_json={"provider": "none"},
                )
            )
            await db.commit()
            return

        page = await db.scalar(
            select(SubmissionPage)
            .where(
                SubmissionPage.tenant_id == tenant_id,
                SubmissionPage.submission_id == submission_id,
            )
            .order_by(SubmissionPage.page_index.asc())
            .limit(1)
        )
        if page is None:
            raise IdentityPipelineError("PAGES_MISSING", "No normalized pages")

        assessment = await db.scalar(
            select(Assessment).where(
                Assessment.id == submission.assessment_id,
                Assessment.tenant_id == tenant_id,
            )
        )
        students_q = select(Student).where(
            Student.tenant_id == tenant_id,
            Student.status == "active",
        )
        if assessment is not None and assessment.class_section_id is not None:
            students_q = students_q.where(
                Student.class_section_id == assessment.class_section_id
            )
        students = list((await db.scalars(students_q.limit(100))).all())
        roster_hints = [
            {
                "student_id": str(s.id),
                "name": (s.full_name or "")[:100],
                "roll": (s.student_code or "")[:64],
            }
            for s in students
        ]
        allowed_ids = {s.id for s in students}

        provider = get_structure_provider(settings)
        request = IdentityExtractionInput(
            submission_id=submission.id,
            page_id=page.id,
            roster_hints=roster_hints,
            assessment_code=assessment.code if assessment else None,
        )
        started = datetime.now(UTC)
        input_hash = canonical_input_hash(request.model_dump(mode="json"))
        response_summary: dict[str, Any]
        try:
            result = await provider.extract_student_identity(request)
            status = "SUCCEEDED"
            error_class = None
            response_summary = {
                "candidate_count": len(result.candidate_student_ids),
                "confidence": float(result.identity_confidence),
                "has_name": result.extracted_name is not None,
                "has_roll": result.extracted_roll is not None,
            }
        except ProviderUnavailable as exc:
            status = "UNAVAILABLE"
            error_class = "ProviderUnavailable"
            response_summary = {"error": str(exc)[:200]}
            result = None
        except Exception as exc:
            status = "FAILED"
            error_class = type(exc).__name__
            response_summary = {"error": str(exc)[:200]}
            result = None

        finished = datetime.now(UTC)
        exec_row = await record_ai_execution(
            db,
            tenant_id=tenant_id,
            operation="extract_student_identity",
            provider=provider.provider_name,
            status=status,
            request_summary=redacted_request_summary(
                operation="extract_student_identity",
                entity_ids={
                    "submission_id": str(submission.id),
                    "page_id": str(page.id),
                },
                input_refs={"roster_hint_count": len(roster_hints)},
            ),
            response_summary=response_summary,
            submission_id=submission.id,
            model=getattr(settings, "ai_model_identity", None),
            input_refs={"page_id": str(page.id), "roster_hint_count": len(roster_hints)},
            input_hash=input_hash,
            latency_ms=int((finished - started).total_seconds() * 1000),
            error_class=error_class,
            started_at=started,
            finished_at=finished,
        )

        await db.execute(
            delete(SubmissionIdentityCandidate).where(
                SubmissionIdentityCandidate.tenant_id == tenant_id,
                SubmissionIdentityCandidate.submission_id == submission.id,
                SubmissionIdentityCandidate.source_type == "AI",
            )
        )

        if result is not None:
            submission.name_detected = result.extracted_name
            submission.roll_number_detected = result.extracted_roll
            submission.identity_confidence = result.identity_confidence
            submission.student_match_state = "REVIEW_REQUIRED"
            for rank, sid in enumerate(result.candidate_student_ids):
                if sid not in allowed_ids:
                    continue
                db.add(
                    SubmissionIdentityCandidate(
                        tenant_id=tenant_id,
                        submission_id=submission.id,
                        student_id=sid,
                        confidence=result.identity_confidence,
                        source_type="AI",
                        ai_execution_record_id=exec_row.id,
                        rank_order=rank,
                        reason="AI identity candidate",
                    )
                )
        else:
            submission.identity_confidence = Decimal("0.0000")
            submission.student_match_state = "REVIEW_REQUIRED"

        submission.workflow_state = "IDENTITY_REVIEW"
        job.status = "SUCCEEDED" if status != "FAILED" else "FAILED"
        if status == "FAILED":
            job.error_code = error_class or "IDENTITY_FAILED"
            job.error_detail = str(response_summary.get("error", ""))[:4000]
        else:
            job.error_code = None
            job.error_detail = None
        job.finished_at = finished
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=None,
                entity_type="Submission",
                entity_id=submission.id,
                action="identity_extraction_finished",
                payload_json={
                    "status": status,
                    "execution_id": str(exec_row.id),
                    "provider": provider.provider_name,
                },
            )
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        job = await db.scalar(select(PipelineJob).where(PipelineJob.id == job_id))
        submission = await db.scalar(
            select(Submission).where(Submission.id == submission_id)
        )
        if job is not None and submission is not None:
            code = getattr(exc, "code", "IDENTITY_FAILED")
            message = getattr(exc, "message", str(exc))
            job.status = "FAILED"
            job.error_code = str(code)[:100]
            job.error_detail = str(message)[:4000]
            job.finished_at = datetime.now(UTC)
            # Do not fail the whole submission solely for optional AI identity.
            submission.workflow_state = "IDENTITY_REVIEW"
            submission.student_match_state = "REVIEW_REQUIRED"
            await db.commit()
        raise
