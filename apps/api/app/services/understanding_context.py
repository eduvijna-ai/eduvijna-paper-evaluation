"""Load tenant-scoped B20 understanding context from the canonical assessment node."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Assessment, CurriculumNode, Submission
from app.services.language_context import LanguageDecision, decision_from_submission
from app.services.subject_profile import (
    SUBJECT_PROFILE_UNSUPPORTED,
    SubjectProfileResolution,
    resolve_subject_profile,
)


@dataclass(frozen=True, slots=True)
class UnderstandingContext:
    assessment: Assessment
    subject: SubjectProfileResolution
    language: LanguageDecision

    def automation_block_code(self) -> str | None:
        if self.subject.profile == SUBJECT_PROFILE_UNSUPPORTED:
            return "SUBJECT_PROFILE_UNSUPPORTED"
        return self.language.gate_code

    def routing_metadata(self) -> dict[str, str | None]:
        return {
            **self.subject.routing_dict(),
            "language_code": self.language.language_code,
            "script_code": self.language.script_code,
            "routing_language_code": self.language.routing_language_code,
            "routing_script_code": self.language.routing_script_code,
            "language_state": self.language.language_state,
            "language_source": self.language.language_source,
        }


async def load_subject_node(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    subject_node_id: uuid.UUID | None,
) -> CurriculumNode | None:
    if subject_node_id is None:
        return None
    node: CurriculumNode | None = await db.scalar(
        select(CurriculumNode).where(
            CurriculumNode.id == subject_node_id,
            CurriculumNode.tenant_id == tenant_id,
        )
    )
    return node


async def resolve_assessment_subject(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment: Assessment,
) -> SubjectProfileResolution:
    node = await load_subject_node(
        db, tenant_id=tenant_id, subject_node_id=assessment.subject_node_id
    )
    return resolve_subject_profile(node, subject_node_id=assessment.subject_node_id)


async def load_understanding_context(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
) -> UnderstandingContext:
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == submission.assessment_id,
            Assessment.tenant_id == tenant_id,
        )
    )
    if assessment is None:
        raise LookupError("Assessment not found for submission")
    subject = await resolve_assessment_subject(
        db, tenant_id=tenant_id, assessment=assessment
    )
    return UnderstandingContext(
        assessment=assessment,
        subject=subject,
        language=decision_from_submission(submission),
    )


async def enrich_assessment_dump(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    node_id = payload.get("subject_node_id")
    node = None
    if node_id:
        try:
            parsed = node_id if isinstance(node_id, uuid.UUID) else uuid.UUID(str(node_id))
        except ValueError:
            parsed = None
        if parsed is not None:
            node = await load_subject_node(
                db, tenant_id=tenant_id, subject_node_id=parsed
            )
    resolution = resolve_subject_profile(node, subject_node_id=node_id)
    payload.update(resolution.as_public_dict())
    return payload
