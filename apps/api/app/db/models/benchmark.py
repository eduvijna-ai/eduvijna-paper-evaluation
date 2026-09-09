"""B15 gold benchmark datasets and isolated AI regression runs (PEV-058/059)."""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ALGORITHM_VERSION_B15_V1 = "B15_V1"


class BenchmarkDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_datasets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_benchmark_datasets_tenant_code",
        ),
        Index("ix_benchmark_datasets_tenant", "tenant_id"),
        Index("ix_benchmark_datasets_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class BenchmarkDatasetVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_dataset_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "dataset_id",
            "version_number",
            name="uq_benchmark_dataset_versions_tenant_dataset_number",
        ),
        CheckConstraint(
            "status IN ('DRAFT','LOCKED')",
            name="ck_benchmark_dataset_versions_status",
        ),
        Index(
            "ix_benchmark_dataset_versions_tenant_dataset",
            "tenant_id",
            "dataset_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_datasets.id", ondelete="CASCADE")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    threshold_profile_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    case_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class BenchmarkCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_cases"
    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "question_evaluation_id",
            name="uq_benchmark_cases_version_qe",
        ),
        Index(
            "ix_benchmark_cases_tenant_version",
            "tenant_id",
            "dataset_version_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_dataset_versions.id", ondelete="CASCADE")
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
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    rubric_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubric_versions.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    expected_final_marks: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    expected_max_marks: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    expected_error_codes: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    source_ledger_hash: Mapped[str] = mapped_column(String(64))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    adjudicated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    adjudicated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    replay_fixture: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )


class BenchmarkRegressionRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_regression_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','PASSED','FAILED','ERROR')",
            name="ck_benchmark_regression_runs_status",
        ),
        CheckConstraint(
            "verdict IN ('PASS','FAIL','PENDING')",
            name="ck_benchmark_regression_runs_verdict",
        ),
        Index(
            "ix_benchmark_regression_runs_tenant_version",
            "tenant_id",
            "dataset_version_id",
        ),
        Index(
            "uq_benchmark_regression_runs_tenant_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_dataset_versions.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    verdict: Mapped[str] = mapped_column(String(32), default="PENDING")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    candidate_provider: Mapped[str] = mapped_column(String(100))
    candidate_model: Mapped[str] = mapped_column(String(100))
    candidate_model_version: Mapped[str] = mapped_column(String(100))
    candidate_prompt_template_version: Mapped[str] = mapped_column(String(100))
    candidate_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    threshold_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    aggregate_metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class BenchmarkRegressionCaseResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_regression_case_results"
    __table_args__ = (
        UniqueConstraint(
            "regression_run_id",
            "benchmark_case_id",
            name="uq_benchmark_regression_case_results_run_case",
        ),
        Index(
            "ix_benchmark_regression_case_results_tenant_run",
            "tenant_id",
            "regression_run_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    regression_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_regression_runs.id", ondelete="CASCADE")
    )
    benchmark_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("benchmark_cases.id", ondelete="RESTRICT")
    )
    missing_output: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    actual_marks: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    actual_error_codes: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    score_abs_error: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    exact_score_match: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    taxonomy_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    safety_invariant_failed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    diff: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    ai_execution_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_execution_records.id", ondelete="SET NULL"), nullable=True
    )
