"""B14 reassessment instantiation and mastery delta projection (PEV-043)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ALGORITHM_VERSION_B14_V1 = "B14_V1"


class Reassessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reassessments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "improvement_assessment_id",
            name="uq_reassessments_tenant_blueprint",
        ),
        UniqueConstraint("assessment_id", name="uq_reassessments_assessment"),
        CheckConstraint(
            "status IN ('CREATED','SUBMITTED','PUBLISHED')",
            name="ck_reassessments_status",
        ),
        Index("ix_reassessments_tenant_student", "tenant_id", "student_id"),
        Index(
            "ix_reassessments_tenant_blueprint",
            "tenant_id",
            "improvement_assessment_id",
        ),
        Index("ix_reassessments_tenant_assessment", "tenant_id", "assessment_id"),
        Index("ix_reassessments_tenant_submission", "tenant_id", "submission_id"),
        Index(
            "ix_reassessments_tenant_published_result",
            "tenant_id",
            "published_result_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    improvement_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("improvement_assessments.id", ondelete="RESTRICT")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT")
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curricula.id", ondelete="RESTRICT")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="RESTRICT")
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    published_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("published_results.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32))
    instantiation_hash: Mapped[str] = mapped_column(String(64))
    baseline_captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    algorithm_version: Mapped[str] = mapped_column(
        String(32),
        default=ALGORITHM_VERSION_B14_V1,
        server_default=ALGORITHM_VERSION_B14_V1,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ReassessmentItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reassessment_items"
    __table_args__ = (
        UniqueConstraint(
            "reassessment_id",
            "improvement_assessment_item_id",
            name="uq_reassessment_items_blueprint_item",
        ),
        UniqueConstraint(
            "question_version_id",
            name="uq_reassessment_items_question_version",
        ),
        Index(
            "ix_reassessment_items_tenant_reassessment",
            "tenant_id",
            "reassessment_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    reassessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reassessments.id", ondelete="CASCADE")
    )
    improvement_assessment_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("improvement_assessment_items.id", ondelete="RESTRICT")
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT")
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT")
    )
    item_code_snapshot: Mapped[str] = mapped_column(String(100))
    template_kind_snapshot: Mapped[str] = mapped_column(String(64))
    question_template_ref_snapshot: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReassessmentMasteryDelta(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reassessment_mastery_deltas"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "reassessment_id",
            "curriculum_node_id",
            "algorithm_version",
            name="uq_reassessment_mastery_deltas_grain",
        ),
        Index(
            "ix_reassessment_mastery_deltas_tenant_reassessment",
            "tenant_id",
            "reassessment_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    reassessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reassessments.id", ondelete="CASCADE")
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT")
    )
    baseline_concept_mastery: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    baseline_execution_accuracy: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    baseline_concept_decisive_count: Mapped[int] = mapped_column(Integer, default=0)
    baseline_execution_decisive_count: Mapped[int] = mapped_column(Integer, default=0)
    baseline_concept_inconclusive_count: Mapped[int] = mapped_column(
        Integer, default=0
    )
    baseline_execution_inconclusive_count: Mapped[int] = mapped_column(
        Integer, default=0
    )
    baseline_evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    baseline_source_evidence_hash: Mapped[str] = mapped_column(String(64))
    post_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mastery_state_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    post_published_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("published_results.id", ondelete="SET NULL"), nullable=True
    )
    post_concept_mastery: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    post_execution_accuracy: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    post_concept_decisive_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    post_execution_decisive_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    post_concept_inconclusive_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    post_execution_inconclusive_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    post_evidence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_source_evidence_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    concept_delta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    execution_delta: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    materialized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(32),
        default=ALGORITHM_VERSION_B14_V1,
        server_default=ALGORITHM_VERSION_B14_V1,
    )
