"""B7 publication package and annotation models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
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


class PublishedResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "published_results"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "submission_id",
            "version_number",
            name="uq_published_results_tenant_submission_version",
        ),
        CheckConstraint(
            "status IN ('READY','GENERATING','GENERATED','PUBLISHED','FAILED')",
            name="ck_published_results_status",
        ),
        Index("ix_published_results_tenant_submission", "tenant_id", "submission_id"),
        Index("ix_published_results_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
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
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="READY")
    ledger_snapshot_hash: Mapped[str] = mapped_column(String(64))
    total_score: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    max_total_score: Mapped[Decimal] = mapped_column(Numeric(10, 4))

    annotated_pdf_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    annotated_pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    annotated_pdf_byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    student_report_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    student_report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    student_report_byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    student_report_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    parent_report_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parent_report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_report_byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    parent_report_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    teacher_report_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    teacher_report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    teacher_report_byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    teacher_report_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    narrative_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("published_results.id", ondelete="SET NULL"), nullable=True
    )


class Annotation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint(
            "annotation_type IN ('TICK','CROSS','PARTIAL','MARK','COMMENT','HIGHLIGHT')",
            name="ck_annotations_type",
        ),
        CheckConstraint(
            "source_type IN ('LEDGER','HUMAN')",
            name="ck_annotations_source_type",
        ),
        CheckConstraint(
            "x >= 0 AND y >= 0 AND width > 0 AND height > 0 "
            "AND x + width <= 1.000001 AND y + height <= 1.000001",
            name="ck_annotations_normalized_geometry",
        ),
        Index("ix_annotations_tenant_published_result", "tenant_id", "published_result_id"),
        Index("ix_annotations_tenant_submission", "tenant_id", "submission_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    submission_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submission_pages.id", ondelete="CASCADE")
    )
    question_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="SET NULL"), nullable=True
    )
    answer_region_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("answer_regions.id", ondelete="SET NULL"), nullable=True
    )
    published_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("published_results.id", ondelete="CASCADE")
    )
    annotation_type: Mapped[str] = mapped_column(String(32))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    source_type: Mapped[str] = mapped_column(String(32), default="LEDGER")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
