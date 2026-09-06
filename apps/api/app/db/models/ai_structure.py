"""B5 AI structure persistence models."""

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


class SubmissionIdentityCandidate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "submission_identity_candidates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "submission_id",
            "student_id",
            "source_type",
            name="uq_identity_candidates_tenant_sub_student_src",
        ),
        CheckConstraint(
            "source_type IN ('AI','HUMAN')",
            name="ck_identity_candidates_source",
        ),
        Index("ix_identity_candidates_tenant_submission", "tenant_id", "submission_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    source_type: Mapped[str] = mapped_column(String(16))
    ai_execution_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_execution_records.id", ondelete="SET NULL"), nullable=True
    )
    rank_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )


class SubmissionPageAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "submission_page_analyses"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "submission_page_id",
            "analysis_version",
            name="uq_page_analyses_tenant_page_version",
        ),
        CheckConstraint(
            "status IN ('SUCCEEDED','FAILED','UNAVAILABLE')",
            name="ck_page_analyses_status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submission_pages.id", ondelete="CASCADE")
    )
    analysis_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(32))
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    ai_execution_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_execution_records.id", ondelete="SET NULL"), nullable=True
    )


class AnswerRegionTranscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_region_transcriptions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "answer_region_id",
            "version_number",
            name="uq_region_transcriptions_tenant_region_version",
        ),
        CheckConstraint(
            "source_type IN ('AI','HUMAN')",
            name="ck_region_transcriptions_source",
        ),
        CheckConstraint(
            "status IN ('PROPOSED','REVIEW_REQUIRED','CONFIRMED','SUPERSEDED')",
            name="ck_region_transcriptions_status",
        ),
        Index("ix_region_transcriptions_tenant_region", "tenant_id", "answer_region_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    answer_region_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_regions.id", ondelete="CASCADE")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(16))
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    latex: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default="[]")
    transcription_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    unreadable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    visual_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(32))
    ai_execution_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_execution_records.id", ondelete="SET NULL"), nullable=True
    )
    supersedes_transcription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("answer_region_transcriptions.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
