"""B10 assessment authoring artifacts and AI run aggregates."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentArtifact(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "assessment_artifacts"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_assessment_artifacts_storage_key"),
        CheckConstraint(
            "artifact_type IN ('QUESTION_PAPER')",
            name="ck_assessment_artifacts_artifact_type",
        ),
        CheckConstraint(
            "security_scan_status IN ('NOT_CONFIGURED','CLEAN','REJECTED','ERROR')",
            name="ck_assessment_artifacts_security_scan_status",
        ),
        Index(
            "ix_assessment_artifacts_tenant_assessment",
            "tenant_id",
            "assessment_id",
        ),
        Index(
            "ix_assessment_artifacts_tenant_uploaded_at",
            "tenant_id",
            "uploaded_at",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE")
    )
    artifact_type: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    content_sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(Text)
    security_scan_status: Mapped[str] = mapped_column(String(32))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuthoringAiRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "authoring_ai_runs"
    __table_args__ = (
        CheckConstraint(
            "operation IN ("
            "'PARSE_QUESTION_PAPER','PROPOSE_ANSWER_KEY',"
            "'PROPOSE_RUBRIC','SUGGEST_CURRICULUM_MAPPING')",
            name="ck_authoring_ai_runs_operation",
        ),
        CheckConstraint(
            "status IN ("
            "'QUEUED','RUNNING','REVIEW_REQUIRED',"
            "'SUCCEEDED','FAILED','UNAVAILABLE')",
            name="ck_authoring_ai_runs_status",
        ),
        Index(
            "ix_authoring_ai_runs_tenant_assessment_version",
            "tenant_id",
            "assessment_version_id",
        ),
        Index("ix_authoring_ai_runs_tenant_status", "tenant_id", "status"),
        Index(
            "ix_authoring_ai_runs_tenant_operation_input",
            "tenant_id",
            "operation",
            "input_hash",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="CASCADE")
    )
    question_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_versions.id", ondelete="SET NULL"), nullable=True
    )
    assessment_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_artifacts.id", ondelete="SET NULL"), nullable=True
    )
    operation: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    input_hash: Mapped[str] = mapped_column(String(64))
    proposal_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answer_key_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("answer_key_versions.id", ondelete="SET NULL"), nullable=True
    )
    rubric_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rubric_versions.id", ondelete="SET NULL"), nullable=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
