"""B9 learning plan runs, recommendations, path steps, and improvement blueprints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

ALGORITHM_VERSION_B9_V1 = "B9_V1"


class LearningPlanRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "learning_plan_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_id",
            "version_number",
            name="uq_learning_plan_runs_version",
        ),
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_id",
            "input_hash",
            "algorithm_version",
            name="uq_learning_plan_runs_input_idempotency",
        ),
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','READY','FAILED','SUPERSEDED')",
            name="ck_learning_plan_runs_status",
        ),
        CheckConstraint(
            "generation_source IS NULL OR generation_source IN "
            "('AI','FIXED','RULES_FALLBACK')",
            name="ck_learning_plan_runs_generation_source",
        ),
        Index(
            "ix_learning_plan_runs_tenant_student_curriculum",
            "tenant_id",
            "student_id",
            "curriculum_id",
        ),
        Index("ix_learning_plan_runs_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE")
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curricula.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    source_evidence_hash: Mapped[str] = mapped_column(String(64))
    curriculum_graph_hash: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    algorithm_version: Mapped[str] = mapped_column(
        String(32), default=ALGORITHM_VERSION_B9_V1, server_default=ALGORITHM_VERSION_B9_V1
    )
    generation_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningRecommendation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "learning_recommendations"
    __table_args__ = (
        CheckConstraint(
            "recommendation_kind IN ("
            "'PREREQUISITE_REPAIR','TARGET_CONCEPT',"
            "'PROCEDURE_PRACTICE','EXECUTION_PRACTICE')",
            name="ck_learning_recommendations_kind",
        ),
        CheckConstraint(
            "priority IN (1, 2, 3)",
            name="ck_learning_recommendations_priority",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','DISMISSED','COMPLETED')",
            name="ck_learning_recommendations_status",
        ),
        CheckConstraint(
            "concept_signal IN ('STRONG','WEAK','INCONCLUSIVE')",
            name="ck_learning_recommendations_concept_signal",
        ),
        CheckConstraint(
            "execution_signal IN ('STRONG','WEAK','INCONCLUSIVE')",
            name="ck_learning_recommendations_execution_signal",
        ),
        CheckConstraint(
            "procedure_signal IN ('STRONG','WEAK','INCONCLUSIVE')",
            name="ck_learning_recommendations_procedure_signal",
        ),
        Index(
            "ix_learning_recommendations_tenant_run",
            "tenant_id",
            "learning_plan_run_id",
        ),
        Index(
            "ix_learning_recommendations_tenant_student_curriculum",
            "tenant_id",
            "student_id",
            "curriculum_id",
        ),
        Index(
            "ix_learning_recommendations_tenant_target_node",
            "tenant_id",
            "target_node_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    learning_plan_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_plan_runs.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE")
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curricula.id", ondelete="RESTRICT")
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT")
    )
    recommendation_kind: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text)
    concept_signal: Mapped[str] = mapped_column(String(32))
    execution_signal: Mapped[str] = mapped_column(String(32))
    procedure_signal: Mapped[str] = mapped_column(String(32))
    evidence_count: Mapped[int] = mapped_column(Integer)
    mean_evidence_score_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    target_node_code_snapshot: Mapped[str] = mapped_column(String(100))
    target_node_title_snapshot: Mapped[str] = mapped_column(String(255))
    target_node_type_snapshot: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningRecommendationPrerequisite(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "learning_recommendation_prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "learning_recommendation_id",
            "curriculum_node_id",
            "relationship_type",
            name="uq_learning_recommendation_prerequisites_edge",
        ),
        CheckConstraint(
            "relationship_type IN ('REQUIRED','RECOMMENDED')",
            name="ck_learning_recommendation_prerequisites_type",
        ),
        Index(
            "ix_learning_rec_prereq_tenant_rec",
            "tenant_id",
            "learning_recommendation_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    learning_recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_recommendations.id", ondelete="CASCADE")
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT")
    )
    relationship_type: Mapped[str] = mapped_column(String(32))
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LearningRecommendationEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "learning_recommendation_evidence"
    __table_args__ = (
        UniqueConstraint(
            "learning_recommendation_id",
            "mastery_evidence_id",
            name="uq_learning_recommendation_evidence",
        ),
        Index(
            "ix_learning_rec_evidence_tenant_rec",
            "tenant_id",
            "learning_recommendation_id",
        ),
        Index(
            "ix_learning_rec_evidence_tenant_mastery",
            "tenant_id",
            "mastery_evidence_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    learning_recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_recommendations.id", ondelete="CASCADE")
    )
    mastery_evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mastery_evidence.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LearningPathStep(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "learning_path_steps"
    __table_args__ = (
        UniqueConstraint(
            "learning_plan_run_id",
            "sequence",
            name="uq_learning_path_steps_sequence",
        ),
        CheckConstraint(
            "kind IN ("
            "'PREREQUISITE','LEARN','GUIDED','INDEPENDENT','MASTERY_CHECK')",
            name="ck_learning_path_steps_kind",
        ),
        CheckConstraint(
            "relationship_type IS NULL OR relationship_type IN "
            "('REQUIRED','RECOMMENDED')",
            name="ck_learning_path_steps_relationship",
        ),
        Index(
            "ix_learning_path_steps_tenant_run",
            "tenant_id",
            "learning_plan_run_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    learning_plan_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_plan_runs.id", ondelete="CASCADE")
    )
    learning_recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_recommendations.id", ondelete="SET NULL"), nullable=True
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(32))
    sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_basis: Mapped[str] = mapped_column(String(64))
    relationship_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ImprovementAssessment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "improvement_assessments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "learning_plan_run_id",
            "version_number",
            name="uq_improvement_assessments_version",
        ),
        CheckConstraint(
            "status IN ("
            "'DRAFT','GENERATING','PENDING_APPROVAL',"
            "'APPROVED','REJECTED','FAILED')",
            name="ck_improvement_assessments_status",
        ),
        CheckConstraint(
            "generation_source IS NULL OR generation_source IN "
            "('AI','FIXED','RULES_FALLBACK')",
            name="ck_improvement_assessments_generation_source",
        ),
        Index(
            "ix_improvement_assessments_tenant_run",
            "tenant_id",
            "learning_plan_run_id",
        ),
        Index(
            "ix_improvement_assessments_tenant_student_curriculum",
            "tenant_id",
            "student_id",
            "curriculum_id",
        ),
        Index(
            "ix_improvement_assessments_tenant_status",
            "tenant_id",
            "status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE")
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curricula.id", ondelete="RESTRICT")
    )
    learning_plan_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_plan_runs.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    source_evidence_hash: Mapped[str] = mapped_column(String(64))
    curriculum_graph_hash: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    generation_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    blueprint_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    blueprint_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    blueprint_byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    generated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImprovementAssessmentItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "improvement_assessment_items"
    __table_args__ = (
        UniqueConstraint(
            "improvement_assessment_id",
            "item_code",
            name="uq_improvement_assessment_items_code",
        ),
        CheckConstraint(
            "template_kind IN ("
            "'CONCEPT_CHECK','PREREQUISITE_CHECK',"
            "'PROCEDURE_PRACTICE','EXECUTION_PRACTICE','TRANSFER_CHECK')",
            name="ck_improvement_assessment_items_template_kind",
        ),
        CheckConstraint(
            "difficulty IN ('EASY','MEDIUM','HARD')",
            name="ck_improvement_assessment_items_difficulty",
        ),
        CheckConstraint(
            "suggested_marks IS NULL OR suggested_marks > 0",
            name="ck_improvement_assessment_items_suggested_marks",
        ),
        Index(
            "ix_improvement_assessment_items_tenant_assessment",
            "tenant_id",
            "improvement_assessment_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    improvement_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("improvement_assessments.id", ondelete="CASCADE")
    )
    learning_recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_recommendations.id", ondelete="RESTRICT")
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT")
    )
    item_code: Mapped[str] = mapped_column(String(100))
    template_kind: Mapped[str] = mapped_column(String(64))
    question_template_ref: Mapped[str] = mapped_column(String(255))
    focus: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16))
    suggested_marks: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
