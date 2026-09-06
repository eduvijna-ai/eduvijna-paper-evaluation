"""B6 evaluation ledger persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
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


class EvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "submission_id",
            "run_number",
            name="uq_evaluation_runs_tenant_submission_run",
        ),
        CheckConstraint(
            "status IN ("
            "'QUEUED','RUNNING','REVIEW_REQUIRED','COMPLETED','FAILED','SUPERSEDED')",
            name="ck_evaluation_runs_status",
        ),
        Index("ix_evaluation_runs_tenant_submission", "tenant_id", "submission_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    run_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rules_engine_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuestionEvaluation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "evaluation_run_id",
            "question_version_id",
            name="uq_question_evaluations_tenant_run_qv",
        ),
        CheckConstraint(
            "workflow_state IN ("
            "'PENDING','PROPOSED','REVIEW_REQUIRED','ACCEPTED','OVERRIDDEN','ESCALATED')",
            name="ck_question_evaluations_workflow",
        ),
        Index("ix_question_evaluations_tenant_submission", "tenant_id", "submission_id"),
        Index("ix_question_evaluations_tenant_run", "tenant_id", "evaluation_run_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE")
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT")
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    rubric_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubric_versions.id", ondelete="RESTRICT")
    )
    answer_key_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_key_versions.id", ondelete="RESTRICT")
    )
    mapping_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_answer_mappings.id", ondelete="SET NULL"), nullable=True
    )
    answer_region_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    transcription_refs: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    max_mark: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    proposed_ai_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    final_human_approved_score: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    first_divergence_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ecf_applied: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    ecf_chain: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    alternative_method_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alternative_method_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_codes: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default="[]")
    deduction_reasons: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    criterion_snapshot: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    identity_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    mapping_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    transcription_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    evaluation_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    math_verification_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    workflow_state: Mapped[str] = mapped_column(String(32), default="PENDING")
    ledger_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    supersedes_ledger_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_execution_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_execution_records.id", ondelete="SET NULL"), nullable=True
    )


class CriterionEvaluation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "criterion_evaluations"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('AWARDED','PARTIAL','DEDUCTED','NOT_APPLICABLE','UNREADABLE')",
            name="ck_criterion_evaluations_decision",
        ),
        Index("ix_criterion_evaluations_tenant_qe", "tenant_id", "question_evaluation_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    question_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="CASCADE")
    )
    rubric_criterion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubric_criteria.id", ondelete="RESTRICT")
    )
    criterion_code: Mapped[str] = mapped_column(String(100))
    criterion_label: Mapped[str] = mapped_column(String(255))
    max_marks: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    proposed_marks: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    final_marks: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    decision: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deduction_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ecf_source_criterion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rubric_criteria.id", ondelete="SET NULL"), nullable=True
    )
    unit_check_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    precision_check_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    accepted_alternative_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_execution_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_execution_records.id", ondelete="SET NULL"), nullable=True
    )


class ReviewAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "review_actions"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ("
            "'ACCEPT','OVERRIDE','EDIT_FEEDBACK','VALID_ALTERNATIVE','ESCALATE')",
            name="ck_review_actions_type",
        ),
        Index("ix_review_actions_tenant_qe", "tenant_id", "question_evaluation_id"),
        Index("ix_review_actions_tenant_submission", "tenant_id", "submission_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    question_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="CASCADE")
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE")
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    action_type: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    after_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    previous_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    new_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
