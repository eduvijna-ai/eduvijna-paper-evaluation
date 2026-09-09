"""B8 MasteryEvidence + B12 longitudinal MasteryState / snapshots / mistake notebook."""

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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

ALGORITHM_VERSION_B8_V1 = "B8_V1"
ALGORITHM_VERSION_B12_V1 = "B12_V1"


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


class MasteryState(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mastery_states"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_node_id",
            "algorithm_version",
            name="uq_mastery_states_student_node_algo",
        ),
        CheckConstraint(
            "concept_mastery IS NULL OR (concept_mastery >= 0 AND concept_mastery <= 1)",
            name="ck_mastery_states_concept_mastery",
        ),
        CheckConstraint(
            "execution_accuracy IS NULL OR "
            "(execution_accuracy >= 0 AND execution_accuracy <= 1)",
            name="ck_mastery_states_execution_accuracy",
        ),
        CheckConstraint(
            "concept_decisive_count >= 0 AND execution_decisive_count >= 0 "
            "AND concept_inconclusive_count >= 0 AND execution_inconclusive_count >= 0 "
            "AND evidence_count >= 0",
            name="ck_mastery_states_counts",
        ),
        Index("ix_mastery_states_tenant_student", "tenant_id", "student_id"),
        Index("ix_mastery_states_tenant_node", "tenant_id", "curriculum_node_id"),
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
    concept_mastery: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    execution_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    concept_decisive_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_decisive_count: Mapped[int] = mapped_column(Integer, default=0)
    concept_inconclusive_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_inconclusive_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    source_evidence_hash: Mapped[str] = mapped_column(String(64))
    algorithm_version: Mapped[str] = mapped_column(
        String(32), default=ALGORITHM_VERSION_B12_V1
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MasteryStateSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mastery_state_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_node_id",
            "published_result_id",
            "algorithm_version",
            name="uq_mastery_state_snapshots_grain",
        ),
        CheckConstraint(
            "concept_mastery IS NULL OR (concept_mastery >= 0 AND concept_mastery <= 1)",
            name="ck_mastery_state_snapshots_concept_mastery",
        ),
        CheckConstraint(
            "execution_accuracy IS NULL OR "
            "(execution_accuracy >= 0 AND execution_accuracy <= 1)",
            name="ck_mastery_state_snapshots_execution_accuracy",
        ),
        CheckConstraint(
            "concept_decisive_count >= 0 AND execution_decisive_count >= 0 "
            "AND concept_inconclusive_count >= 0 AND execution_inconclusive_count >= 0 "
            "AND evidence_count >= 0",
            name="ck_mastery_state_snapshots_counts",
        ),
        Index(
            "ix_mastery_state_snapshots_tenant_student_effective",
            "tenant_id",
            "student_id",
            "effective_at",
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
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    concept_mastery: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    execution_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    concept_decisive_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_decisive_count: Mapped[int] = mapped_column(Integer, default=0)
    concept_inconclusive_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_inconclusive_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    source_evidence_hash: Mapped[str] = mapped_column(String(64))
    algorithm_version: Mapped[str] = mapped_column(
        String(32), default=ALGORITHM_VERSION_B12_V1
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MistakeNotebookEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mistake_notebook_entries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "published_result_id",
            "question_evaluation_id",
            "academic_error_code",
            "algorithm_version",
            name="uq_mistake_notebook_entries_grain",
        ),
        CheckConstraint(
            "recommended_practice_kind IN ("
            "'CONCEPT_CHECK','EXECUTION_PRACTICE','PROCEDURE_PRACTICE')",
            name="ck_mistake_notebook_practice_kind",
        ),
        CheckConstraint(
            "final_score >= 0 AND max_mark > 0 AND final_score <= max_mark",
            name="ck_mistake_notebook_scores",
        ),
        Index(
            "ix_mistake_notebook_tenant_student_effective",
            "tenant_id",
            "student_id",
            "effective_at",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE")
    )
    published_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("published_results.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    question_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="CASCADE")
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    academic_error_code: Mapped[str] = mapped_column(String(64))
    final_score: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    max_mark: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    deduction_reasons: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    first_divergence_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    curriculum_node_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    recommended_practice_kind: Mapped[str] = mapped_column(String(32))
    linked_learning_recommendation_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    source_ledger_snapshot_hash: Mapped[str] = mapped_column(String(64))
    source_mastery_evidence_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(32), default=ALGORITHM_VERSION_B12_V1
    )
    materialized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
