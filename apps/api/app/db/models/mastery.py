"""B8 MasteryEvidence — immutable published-ledger evidence rows (no MasteryState)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

ALGORITHM_VERSION_B8_V1 = "B8_V1"


class MasteryEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mastery_evidence"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "published_result_id",
            "question_evaluation_id",
            "curriculum_node_id",
            "evidence_type",
            "algorithm_version",
            name="uq_mastery_evidence_idempotency",
        ),
        CheckConstraint(
            "evidence_type IN ('CONCEPT','EXECUTION','PROCEDURE')",
            name="ck_mastery_evidence_type",
        ),
        CheckConstraint(
            "strength IN ('STRONG','WEAK','INCONCLUSIVE')",
            name="ck_mastery_evidence_strength",
        ),
        CheckConstraint(
            "score_ratio >= 0 AND score_ratio <= 1",
            name="ck_mastery_evidence_score_ratio",
        ),
        CheckConstraint(
            "source_final_score >= 0 AND source_max_mark > 0 "
            "AND source_final_score <= source_max_mark",
            name="ck_mastery_evidence_scores",
        ),
        Index(
            "ix_mastery_evidence_tenant_student_node",
            "tenant_id",
            "student_id",
            "curriculum_node_id",
        ),
        Index(
            "ix_mastery_evidence_tenant_assessment_node",
            "tenant_id",
            "assessment_id",
            "curriculum_node_id",
        ),
        Index(
            "ix_mastery_evidence_tenant_published_result",
            "tenant_id",
            "published_result_id",
        ),
        Index(
            "ix_mastery_evidence_tenant_question_evaluation",
            "tenant_id",
            "question_evaluation_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE")
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curricula.id", ondelete="RESTRICT")
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT")
    )
    published_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("published_results.id", ondelete="CASCADE")
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT")
    )
    question_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="CASCADE")
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    evidence_type: Mapped[str] = mapped_column(String(32))
    strength: Mapped[str] = mapped_column(String(32))
    score_ratio: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    source_final_score: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    source_max_mark: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    mapping_types: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    mapping_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    academic_error_codes: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    review_condition_codes: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    reason_codes: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    source_ledger_snapshot_hash: Mapped[str] = mapped_column(String(64))
    algorithm_version: Mapped[str] = mapped_column(String(32), default=ALGORITHM_VERSION_B8_V1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
