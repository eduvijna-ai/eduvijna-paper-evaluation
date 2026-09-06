"""Deterministic mapping-preparation for B4 (no AI/OCR)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssessmentVersion,
    AuditEvent,
    PipelineJob,
    QuestionVersion,
    Submission,
    SubmissionPage,
)


class MappingPrepareError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def leaf_scorable_questions(
    questions: list[QuestionVersion],
) -> list[QuestionVersion]:
    parent_ids = {
        q.parent_question_version_id
        for q in questions
        if q.parent_question_version_id is not None
    }
    return [
        q
        for q in questions
        if q.id not in parent_ids and q.scoring_mode == "LEAF_SCORABLE"
    ]


async def run_mapping_preparation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
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
        raise MappingPrepareError("NOT_FOUND", "Submission or job not found")

    if job.status == "SUCCEEDED" and submission.workflow_state in {
        "MAPPING_REVIEW",
        "READY_FOR_EVALUATION",
    }:
        return

    job.status = "RUNNING"
    job.started_at = datetime.now(UTC)
    job.attempt = max(job.attempt, 1)
    await db.commit()

    try:
        if submission.student_match_state != "CONFIRMED":
            raise MappingPrepareError(
                "IDENTITY_NOT_CONFIRMED",
                "Identity must be confirmed before mapping review",
            )

        pages = list(
            (
                await db.scalars(
                    select(SubmissionPage).where(
                        SubmissionPage.tenant_id == tenant_id,
                        SubmissionPage.submission_id == submission_id,
                    )
                )
            ).all()
        )
        if not pages:
            raise MappingPrepareError(
                "PAGES_MISSING",
                "Normalized submission pages are required before mapping",
            )

        version = await db.scalar(
            select(AssessmentVersion).where(
                AssessmentVersion.id == submission.assessment_version_id,
                AssessmentVersion.tenant_id == tenant_id,
            )
        )
        if version is None:
            raise MappingPrepareError(
                "ASSESSMENT_VERSION_MISSING",
                "Bound assessment version not found",
            )

        questions = list(
            (
                await db.scalars(
                    select(QuestionVersion).where(
                        QuestionVersion.tenant_id == tenant_id,
                        QuestionVersion.assessment_version_id == version.id,
                    )
                )
            ).all()
        )
        leaves = leaf_scorable_questions(questions)
        if not leaves:
            raise MappingPrepareError(
                "NO_SCORABLE_QUESTIONS",
                "Bound assessment version has no LEAF_SCORABLE questions",
            )

        if submission.workflow_state not in {
            "PROCESSING",
            "MAPPING_REVIEW",
            "READY_FOR_EVALUATION",
        }:
            raise MappingPrepareError(
                "INVALID_WORKFLOW_STATE",
                f"Cannot prepare mapping from workflow_state={submission.workflow_state}",
            )

        if submission.workflow_state == "PROCESSING":
            submission.workflow_state = "MAPPING_REVIEW"
        submission.mapping_confidence = Decimal("0.0000")

        from app.services.mapping_ai import apply_ai_mapping_proposals

        ai_meta = await apply_ai_mapping_proposals(
            db,
            tenant_id=tenant_id,
            submission=submission,
            pages=pages,
            leaves=leaves,
        )

        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=None,
                entity_type="Submission",
                entity_id=submission.id,
                action="mapping_prepare_succeeded",
                payload_json={
                    "job_id": str(job.id),
                    "leaf_count": len(leaves),
                    "page_count": len(pages),
                    "assessment_version_id": str(version.id),
                    "automated_region_detection_active": ai_meta[
                        "automated_region_detection_active"
                    ],
                    "automated_mapping_active": ai_meta["automated_mapping_active"],
                    "ai_region_count": ai_meta["ai_region_count"],
                    "ai_mapping_count": ai_meta["ai_mapping_count"],
                },
            )
        )
        job.status = "SUCCEEDED"
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        job.error_detail = None
        await db.commit()
    except MappingPrepareError as exc:
        job.status = "FAILED"
        job.finished_at = datetime.now(UTC)
        job.error_code = exc.code
        job.error_detail = exc.message
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=None,
                entity_type="Submission",
                entity_id=submission_id,
                action="mapping_prepare_failed",
                payload_json={"code": exc.code, "message": exc.message},
            )
        )
        await db.commit()
        raise
