"""Submission ingestion and pipeline job models (B3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Submission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "source_content_sha256",
            name="uq_submissions_tenant_assessment_hash",
        ),
        CheckConstraint(
            "workflow_state IN ("
            "'UPLOADED','PROCESSING','IDENTITY_REVIEW','MAPPING_REVIEW',"
            "'READY_FOR_EVALUATION','EVALUATING','EVALUATION_REVIEW',"
            "'APPROVED','PUBLISHED','FAILED')",
            name="ck_submissions_workflow_state",
        ),
        CheckConstraint(
            "student_match_state IN ("
            "'UNMATCHED','REVIEW_REQUIRED','AUTO_MATCHED','CONFIRMED')",
            name="ck_submissions_student_match_state",
        ),
        CheckConstraint(
            "storage_status IN ('PENDING','AVAILABLE','FAILED')",
            name="ck_submissions_storage_status",
        ),
        Index(
            "ix_submissions_tenant_assessment_workflow",
            "tenant_id",
            "assessment_id",
            "workflow_state",
        ),
        Index("ix_submissions_tenant_uploaded_at", "tenant_id", "uploaded_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )
    workflow_state: Mapped[str] = mapped_column(String(32), default="UPLOADED")
    student_match_state: Mapped[str] = mapped_column(String(32), default="REVIEW_REQUIRED")
    roll_number_detected: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name_detected: Mapped[str | None] = mapped_column(String(255), nullable=True)
    identity_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.0000"), server_default="0.0000"
    )
    mapping_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.0000"), server_default="0.0000"
    )
    source_storage_key: Mapped[str] = mapped_column(String(512))
    source_content_sha256: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    storage_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    page_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bundle_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SubmissionPage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "submission_pages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "submission_id",
            "page_index",
            name="uq_submission_pages_tenant_submission_index",
        ),
        Index("ix_submission_pages_tenant_submission", "tenant_id", "submission_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    page_index: Mapped[int] = mapped_column(Integer)
    image_storage_key: Mapped[str] = mapped_column(String(512))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    is_continuation: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )


class PipelineJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pipeline_jobs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_pipeline_jobs_tenant_idempotency",
        ),
        CheckConstraint(
            "stage IN ('PAGE_NORMALIZATION','IDENTITY','MAPPING','EVALUATION')",
            name="ck_pipeline_jobs_stage",
        ),
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')",
            name="ck_pipeline_jobs_status",
        ),
        Index("ix_pipeline_jobs_tenant_submission_stage", "tenant_id", "submission_id", "stage"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    stage: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(String(255))
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
