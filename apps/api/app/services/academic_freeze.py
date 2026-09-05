"""Academic configuration freeze for post-READY assessments (CVB)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.db.models import Assessment

EDITABLE_ACADEMIC_STATUSES = frozenset({"DRAFT", "RUBRIC_REVIEW"})
FROZEN_ACADEMIC_STATUSES = frozenset({"READY", "ACTIVE", "CLOSED", "ARCHIVED"})

# Server-controlled provenance; never accepted on public create endpoints.
SERVER_AI_PROPOSED_SOURCE = "AI_PROPOSED"


def ensure_academic_config_mutable(assessment: Assessment) -> None:
    """Block answer-key/rubric/mapping mutation after academic freeze."""
    if assessment.status in EDITABLE_ACADEMIC_STATUSES:
        return
    raise HTTPException(
        409,
        {
            "code": "ASSESSMENT_ACADEMIC_CONFIG_FROZEN",
            "message": (
                "Academic configuration cannot be changed while assessment is "
                f"{assessment.status}"
            ),
        },
    )


def answer_key_audit_payload(item: Any, action: str) -> dict[str, Any]:
    """Metadata-only audit for answer-key versions (no academic content)."""
    return {
        "action": action,
        "answer_key_id": str(item.answer_key_id),
        "answer_key_version_id": str(item.id),
        "question_version_id": str(item.question_version_id),
        "source_type": item.source_type,
        "status": item.status,
        "version_number": item.version_number,
    }


def rubric_version_audit_payload(item: Any, action: str) -> dict[str, Any]:
    return {
        "action": action,
        "rubric_id": str(item.rubric_id),
        "rubric_version_id": str(item.id),
        "question_version_id": str(item.question_version_id),
        "source_type": item.source_type,
        "status": item.status,
        "version_number": item.version_number,
    }


def rubric_criterion_audit_payload(item: Any, action: str) -> dict[str, Any]:
    return {
        "action": action,
        "criterion_id": str(item.id),
        "rubric_version_id": str(item.rubric_version_id),
        "criterion_code": item.criterion_code,
        "scoring_mode": item.scoring_mode,
        "max_marks": str(item.max_marks),
        "sequence": item.sequence,
    }
