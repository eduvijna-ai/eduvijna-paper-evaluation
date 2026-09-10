"""B18 answer clustering (PEV-050) and CO/PO outcome reporting (PEV-051)."""

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ALGORITHM_COSINE_GRAPH_V1 = "COSINE_GRAPH_V1"
ALGORITHM_MARKS_WEIGHTED_V1 = "MARKS_WEIGHTED_V1"
DEFAULT_SIMILARITY_THRESHOLD = Decimal("0.75")
DEFAULT_EMBEDDING_DIM = 32


class AnswerClusterRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_cluster_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_version_id",
            "question_id",
            "source_set_hash",
            "algorithm_version",
            "similarity_threshold",
            "embedding_provider",
            "embedding_model",
            "embedding_model_version",
            "embedding_dim",
            name="uq_answer_cluster_runs_repro_identity",
        ),
        CheckConstraint(
            "status IN ('PENDING','COMPLETED','INSUFFICIENT_SAMPLE','FAILED')",
            name="ck_answer_cluster_runs_status",
        ),
        Index("ix_answer_cluster_runs_tenant", "tenant_id"),
        Index(
            "ix_answer_cluster_runs_tenant_assessment_version",
            "tenant_id",
            "assessment_version_id",
        ),
        Index(
            "ix_answer_cluster_runs_tenant_question",
            "tenant_id",
            "question_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"))
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    cohort_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    algorithm_version: Mapped[str] = mapped_column(String(64))
    similarity_threshold: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), default=DEFAULT_SIMILARITY_THRESHOLD
    )
    source_set_hash: Mapped[str] = mapped_column(String(64))
    source_result_count: Mapped[int] = mapped_column(Integer, default=0)
    source_published_result_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    embedding_provider: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(128))
    embedding_model_version: Mapped[str] = mapped_column(String(64))
    embedding_dim: Mapped[int] = mapped_column(Integer, default=DEFAULT_EMBEDDING_DIM)
    cluster_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnswerCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_clusters"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_id",
            "cluster_index",
            name="uq_answer_clusters_tenant_run_index",
        ),
        Index("ix_answer_clusters_tenant_run", "tenant_id", "run_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_cluster_runs.id", ondelete="CASCADE")
    )
    cluster_index: Mapped[int] = mapped_column(Integer)
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AnswerClusterMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_cluster_members"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_id",
            "question_evaluation_id",
            name="uq_answer_cluster_members_tenant_run_qe",
        ),
        Index("ix_answer_cluster_members_tenant_cluster", "tenant_id", "cluster_id"),
        Index("ix_answer_cluster_members_tenant_run", "tenant_id", "run_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_cluster_runs.id", ondelete="CASCADE")
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_clusters.id", ondelete="CASCADE")
    )
    published_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("published_results.id", ondelete="RESTRICT")
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT")
    )
    question_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="RESTRICT")
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="RESTRICT")
    )
    transcription_text: Mapped[str] = mapped_column(Text)
    transcription_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default="[]")
    final_human_approved_score: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )


class AnswerClusterReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Advisory cluster observation only — never mutates ledger/rubric/publication."""

    __tablename__ = "answer_cluster_reviews"
    __table_args__ = (
        Index("ix_answer_cluster_reviews_tenant_cluster", "tenant_id", "cluster_id"),
        Index("ix_answer_cluster_reviews_tenant_run", "tenant_id", "run_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_cluster_runs.id", ondelete="CASCADE")
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_clusters.id", ondelete="CASCADE")
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    observation: Mapped[str] = mapped_column(Text)
    suggested_rubric_refinement: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutcomeDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outcome_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "outcome_type",
            "code",
            name="uq_outcome_definitions_tenant_type_code",
        ),
        CheckConstraint(
            "outcome_type IN ('CO','PO')",
            name="ck_outcome_definitions_outcome_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','RETIRED')",
            name="ck_outcome_definitions_status",
        ),
        Index("ix_outcome_definitions_tenant", "tenant_id"),
        Index(
            "ix_outcome_definitions_tenant_type",
            "tenant_id",
            "outcome_type",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    outcome_type: Mapped[str] = mapped_column(String(8))
    code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class OutcomeMappingSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outcome_mapping_sets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_version_id",
            "version_number",
            name="uq_outcome_mapping_sets_tenant_av_version",
        ),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','RETIRED')",
            name="ck_outcome_mapping_sets_status",
        ),
        Index("ix_outcome_mapping_sets_tenant", "tenant_id"),
        Index(
            "ix_outcome_mapping_sets_tenant_assessment_version",
            "tenant_id",
            "assessment_version_id",
        ),
        Index(
            "ix_outcome_mapping_sets_tenant_status",
            "tenant_id",
            "status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class QuestionOutcomeMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_outcome_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "mapping_set_id",
            "question_id",
            "outcome_definition_id",
            name="uq_question_outcome_mappings_tenant_set_q_outcome",
        ),
        CheckConstraint(
            "("
            "(weight_policy_version = 1 AND weight > 0) OR "
            "(weight_policy_version >= 2 AND weight > 0 AND weight <= 1)"
            ")",
            name="ck_question_outcome_mappings_weight_policy",
        ),
        Index(
            "ix_question_outcome_mappings_tenant_set",
            "tenant_id",
            "mapping_set_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    mapping_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outcome_mapping_sets.id", ondelete="CASCADE")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"))
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    outcome_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outcome_definitions.id", ondelete="RESTRICT")
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("1.0000"))
    # 1 = legacy B18 (weight > 0); 2+ = strict B18.1+ (0 < weight <= 1). Server-controlled.
    weight_policy_version: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2"
    )


class OutcomeAttainmentReportRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outcome_attainment_report_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_version_id",
            "mapping_set_id",
            "source_set_hash",
            "algorithm_version",
            name="uq_outcome_attainment_runs_tenant_av_map_hash_algo",
        ),
        CheckConstraint(
            "status IN ('PENDING','COMPLETED','INSUFFICIENT_SAMPLE','FAILED')",
            name="ck_outcome_attainment_report_runs_status",
        ),
        Index("ix_outcome_attainment_report_runs_tenant", "tenant_id"),
        Index(
            "ix_outcome_attainment_report_runs_tenant_av",
            "tenant_id",
            "assessment_version_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    mapping_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outcome_mapping_sets.id", ondelete="RESTRICT")
    )
    mapping_set_version_number: Mapped[int] = mapped_column(Integer)
    mapping_activation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cohort_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    algorithm_version: Mapped[str] = mapped_column(String(64))
    source_set_hash: Mapped[str] = mapped_column(String(64))
    source_result_count: Mapped[int] = mapped_column(Integer, default=0)
    source_published_result_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutcomeAttainmentMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outcome_attainment_metrics"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "report_run_id",
            "outcome_definition_id",
            name="uq_outcome_attainment_metrics_tenant_run_outcome",
        ),
        CheckConstraint(
            "denom_status IN ('OK','ZERO_DENOM')",
            name="ck_outcome_attainment_metrics_denom_status",
        ),
        Index(
            "ix_outcome_attainment_metrics_tenant_run",
            "tenant_id",
            "report_run_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    report_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outcome_attainment_report_runs.id", ondelete="CASCADE")
    )
    outcome_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outcome_definitions.id", ondelete="RESTRICT")
    )
    outcome_type: Mapped[str] = mapped_column(String(8))
    outcome_code: Mapped[str] = mapped_column(String(100))
    outcome_title: Mapped[str] = mapped_column(String(255))
    weighted_earned: Mapped[Decimal] = mapped_column(Numeric(16, 6))
    weighted_max: Mapped[Decimal] = mapped_column(Numeric(16, 6))
    attainment_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    denom_status: Mapped[str] = mapped_column(String(32), default="OK")
    mapped_question_count: Mapped[int] = mapped_column(Integer, default=0)
    contribution_count: Mapped[int] = mapped_column(Integer, default=0)
