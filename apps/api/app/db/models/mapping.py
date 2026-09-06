"""Answer-region and question-mapping models (B4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnswerRegion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_regions"
    __table_args__ = (
        CheckConstraint(
            "region_type IN ('ANSWER','SCRATCH','DIAGRAM','IDENTITY')",
            name="ck_answer_regions_region_type",
        ),
        CheckConstraint(
            "source_type IN ('HUMAN','AI')",
            name="ck_answer_regions_source_type",
        ),
        CheckConstraint(
            "bbox_x >= 0 AND bbox_y >= 0 AND bbox_width > 0 AND bbox_height > 0 "
            "AND bbox_x + bbox_width <= 1 AND bbox_y + bbox_height <= 1",
            name="ck_answer_regions_bbox_normalized",
        ),
        Index("ix_answer_regions_tenant_page", "tenant_id", "submission_page_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submission_pages.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(String(255))
    bbox_x: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    bbox_y: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    bbox_width: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    bbox_height: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    region_type: Mapped[str] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(16), default="HUMAN")
    detection_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.0000"), server_default="0.0000"
    )
    crossed_out: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    ignored: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_continuation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.0000"), server_default="0.0000"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class QuestionAnswerMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_answer_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "submission_id",
            "question_version_id",
            name="uq_qam_tenant_submission_qv",
        ),
        CheckConstraint(
            "disposition IN ('ANSWERED','BLANK')",
            name="ck_question_answer_mappings_disposition",
        ),
        CheckConstraint(
            "mapping_state IN ('PROPOSED','REVIEW_REQUIRED','CONFIRMED')",
            name="ck_question_answer_mappings_state",
        ),
        CheckConstraint(
            "mapped_by IN ('HUMAN','AI')",
            name="ck_question_answer_mappings_mapped_by",
        ),
        Index("ix_qam_tenant_submission", "tenant_id", "submission_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT")
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    disposition: Mapped[str] = mapped_column(String(16))
    mapping_state: Mapped[str] = mapped_column(String(32), default="REVIEW_REQUIRED")
    mapping_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.0000"), server_default="0.0000"
    )
    mapped_by: Mapped[str] = mapped_column(String(16), default="HUMAN")
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QuestionAnswerMappingRegion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "question_answer_mapping_regions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "answer_region_id",
            name="uq_qamr_tenant_region",
        ),
        UniqueConstraint(
            "tenant_id",
            "mapping_id",
            "answer_region_id",
            name="uq_qamr_tenant_mapping_region",
        ),
        Index("ix_qamr_tenant_mapping", "tenant_id", "mapping_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    mapping_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_answer_mappings.id", ondelete="CASCADE")
    )
    answer_region_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_regions.id", ondelete="RESTRICT")
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
