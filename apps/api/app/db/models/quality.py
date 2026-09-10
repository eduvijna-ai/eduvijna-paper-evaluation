"""B17 assessment quality — psychometrics (PEV-048) and calibration (PEV-049)."""

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

ALGORITHM_PSYCHOMETRICS_V1 = "B17_PSYCHOMETRICS_V1"
ALGORITHM_CALIBRATION_V1 = "B17_CALIBRATION_V1"
DISCRIMINATION_METHOD_V1 = "CORRECTED_ITEM_TOTAL_PEARSON_V1"
ICC_METHOD_V1 = "ICC_A1_V1"
MIN_PSYCHOMETRIC_COHORT_SIZE = 20
MIN_CALIBRATION_CASES = 10


class PsychometricRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "psychometric_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_version_id",
            "source_set_hash",
            "algorithm_version",
            name="uq_psychometric_runs_tenant_av_hash_algo",
        ),
        CheckConstraint(
            "status IN ('PENDING','COMPLETED','INSUFFICIENT_SAMPLE','FAILED')",
            name="ck_psychometric_runs_status",
        ),
        Index("ix_psychometric_runs_tenant", "tenant_id"),
        Index(
            "ix_psychometric_runs_tenant_assessment_version",
            "tenant_id",
            "assessment_version_id",
        ),
        Index(
            "ix_psychometric_runs_tenant_completed",
            "tenant_id",
            "completed_at",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    cohort_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    algorithm_version: Mapped[str] = mapped_column(String(64))
    min_cohort_size: Mapped[int] = mapped_column(
        Integer, default=MIN_PSYCHOMETRIC_COHORT_SIZE
    )
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
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class ItemPsychometricMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "item_psychometric_metrics"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_id",
            "question_version_id",
            name="uq_item_psychometric_metrics_tenant_run_qv",
        ),
        CheckConstraint(
            "discrimination_status IN ('OK','UNDEFINED_VARIANCE','INSUFFICIENT_SAMPLE')",
            name="ck_item_psychometric_metrics_discrimination_status",
        ),
        Index("ix_item_psychometric_metrics_tenant_run", "tenant_id", "run_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("psychometric_runs.id", ondelete="CASCADE")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT")
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    question_code: Mapped[str] = mapped_column(String(100))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_mark: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    mean_raw_score: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    std_dev: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    difficulty_index: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    difficulty_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discrimination_index: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    discrimination_method: Mapped[str] = mapped_column(
        String(64), default=DISCRIMINATION_METHOD_V1
    )
    discrimination_status: Mapped[str] = mapped_column(String(32), default="OK")
    discrimination_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    full_credit_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    zero_score_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    blank_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)


class CalibrationSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calibration_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','CLOSED')",
            name="ck_calibration_sessions_status",
        ),
        Index("ix_calibration_sessions_tenant", "tenant_id"),
        Index("ix_calibration_sessions_tenant_status", "tenant_id", "status"),
        Index(
            "ix_calibration_sessions_tenant_assessment_version",
            "tenant_id",
            "assessment_version_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    algorithm_version: Mapped[str] = mapped_column(
        String(64), default=ALGORITHM_CALIBRATION_V1
    )
    score_tolerance_abs: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0.5")
    )
    score_tolerance_pct: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0.05")
    )
    min_cases: Mapped[int] = mapped_column(Integer, default=MIN_CALIBRATION_CASES)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CalibrationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calibration_cases"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "session_id",
            "case_code",
            name="uq_calibration_cases_tenant_session_code",
        ),
        UniqueConstraint(
            "tenant_id",
            "session_id",
            "question_evaluation_id",
            name="uq_calibration_cases_tenant_session_qe",
        ),
        Index("ix_calibration_cases_tenant_session", "tenant_id", "session_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="CASCADE")
    )
    case_code: Mapped[str] = mapped_column(String(64))
    published_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("published_results.id", ondelete="RESTRICT")
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT")
    )
    question_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="RESTRICT")
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    rubric_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubric_versions.id", ondelete="RESTRICT")
    )
    max_mark: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    reference_score: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    criterion_snapshot: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    source_snapshot_hash: Mapped[str] = mapped_column(String(64))


class CalibrationParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calibration_participants"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "session_id",
            "user_id",
            name="uq_calibration_participants_tenant_session_user",
        ),
        Index("ix_calibration_participants_tenant_session", "tenant_id", "session_id"),
        Index("ix_calibration_participants_tenant_user", "tenant_id", "user_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )


class CalibrationResponse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calibration_responses"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "session_id",
            "case_id",
            "user_id",
            name="uq_calibration_responses_tenant_session_case_user",
        ),
        Index("ix_calibration_responses_tenant_session", "tenant_id", "session_id"),
        Index("ix_calibration_responses_tenant_case", "tenant_id", "case_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="CASCADE")
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calibration_cases.id", ondelete="CASCADE")
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calibration_participants.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    score: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    max_mark: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalibrationSessionMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calibration_session_metrics"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "session_id",
            "metric_name",
            "algorithm_version",
            name="uq_calibration_session_metrics_tenant_session_metric_algo",
        ),
        CheckConstraint(
            "status IN ('COMPLETED','INSUFFICIENT_SAMPLE','UNDEFINED')",
            name="ck_calibration_session_metrics_status",
        ),
        CheckConstraint(
            "metric_name IN ('ICC_A1')",
            name="ck_calibration_session_metrics_metric_name",
        ),
        Index("ix_calibration_session_metrics_tenant_session", "tenant_id", "session_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="CASCADE")
    )
    metric_name: Mapped[str] = mapped_column(String(32), default="ICC_A1")
    algorithm_version: Mapped[str] = mapped_column(String(64), default=ICC_METHOD_V1)
    evaluator_count: Mapped[int] = mapped_column(Integer, default=0)
    common_case_count: Mapped[int] = mapped_column(Integer, default=0)
    icc_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(32))


class CalibrationEvaluatorMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calibration_evaluator_metrics"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "session_id",
            "user_id",
            name="uq_calibration_evaluator_metrics_tenant_session_user",
        ),
        Index(
            "ix_calibration_evaluator_metrics_tenant_session",
            "tenant_id",
            "session_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_signed_diff: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    mae: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    nmae: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    exact_match_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    within_tolerance_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6))
