"""B16 enterprise grading, moderation, and grievance models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GradingPool(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "grading_pools"
    __table_args__ = (
        CheckConstraint(
            "grading_mode IN ('HORIZONTAL_QUESTION')",
            name="ck_grading_pools_mode",
        ),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','CLOSED')",
            name="ck_grading_pools_status",
        ),
        CheckConstraint(
            "allocation_strategy IN ('MANUAL','ROUND_ROBIN')",
            name="ck_grading_pools_allocation",
        ),
        Index("ix_grading_pools_tenant", "tenant_id"),
        Index(
            "ix_grading_pools_tenant_assessment_version",
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
    grading_mode: Mapped[str] = mapped_column(String(32), default="HORIZONTAL_QUESTION")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    allocation_strategy: Mapped[str] = mapped_column(String(32), default="MANUAL")
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


class GradingPoolMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "grading_pool_members"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "pool_id",
            "user_id",
            name="uq_grading_pool_members_tenant_pool_user",
        ),
        Index("ix_grading_pool_members_tenant_pool", "tenant_id", "pool_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    pool_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("grading_pools.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GradingWorkItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "grading_work_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','IN_PROGRESS','SUBMITTED','RETURNED','COMPLETED')",
            name="ck_grading_work_items_status",
        ),
        Index("ix_grading_work_items_tenant_pool", "tenant_id", "pool_id"),
        Index(
            "ix_grading_work_items_tenant_evaluator",
            "tenant_id",
            "assigned_evaluator_id",
        ),
        Index(
            "ix_grading_work_items_tenant_submission",
            "tenant_id",
            "submission_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    pool_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("grading_pools.id", ondelete="CASCADE")
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE")
    )
    question_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="CASCADE")
    )
    assigned_evaluator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ModerationPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "moderation_policies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','RETIRED')",
            name="ck_moderation_policies_status",
        ),
        Index("ix_moderation_policies_tenant", "tenant_id"),
        Index(
            "ix_moderation_policies_tenant_av",
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
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retired_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ModerationStage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "moderation_stages"
    __table_args__ = (
        UniqueConstraint(
            "policy_id", "stage_order", name="uq_moderation_stages_policy_order"
        ),
        CheckConstraint(
            "required_role IN ("
            "'MODERATOR','HOD','ACADEMIC_COORDINATOR','EXAM_CONTROLLER','INSTITUTION_ADMIN')",
            name="ck_moderation_stages_role",
        ),
        Index("ix_moderation_stages_tenant_policy", "tenant_id", "policy_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("moderation_policies.id", ondelete="CASCADE")
    )
    stage_order: Mapped[int] = mapped_column(Integer)
    required_role: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(255))


class ModerationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "moderation_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','IN_PROGRESS','APPROVED','RETURNED','REJECTED')",
            name="ck_moderation_cases_status",
        ),
        Index("ix_moderation_cases_tenant_status", "tenant_id", "status"),
        Index("ix_moderation_cases_tenant_submission", "tenant_id", "submission_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("moderation_policies.id", ondelete="RESTRICT")
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE")
    )
    current_stage_order: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")


class ModerationAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "moderation_actions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('APPROVE','RETURN','REJECT')",
            name="ck_moderation_actions_decision",
        ),
        Index("ix_moderation_actions_tenant_case", "tenant_id", "case_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("moderation_cases.id", ondelete="CASCADE")
    )
    stage_order: Mapped[int] = mapped_column(Integer)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GrievanceCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "grievance_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'SUBMITTED','UNDER_REVIEW','ACCEPTED','REJECTED',"
            "'RE_EVALUATING','RESOLVED','CLOSED')",
            name="ck_grievance_cases_status",
        ),
        Index("ix_grievance_cases_tenant", "tenant_id"),
        Index("ix_grievance_cases_tenant_submission", "tenant_id", "submission_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE")
    )
    original_published_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("published_results.id", ondelete="RESTRICT")
    )
    original_evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT")
    )
    requester_reference: Mapped[str] = mapped_column(String(255))
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="SUBMITTED")
    decision_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reevaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    revised_published_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("published_results.id", ondelete="SET NULL"), nullable=True
    )
