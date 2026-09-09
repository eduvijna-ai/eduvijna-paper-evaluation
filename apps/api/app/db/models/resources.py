"""B13 curriculum resources and student resource assignments (PEV-041)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

RESOURCE_KINDS = (
    "PRACTICE_SET",
    "WORKED_EXAMPLE",
    "CONCEPT_NOTE",
    "INTERNAL_PACKET",
)

RESOURCE_STATUSES = ("DRAFT", "APPROVED", "ACTIVE", "DEACTIVATED")

ASSIGNMENT_STATUSES = ("ASSIGNED", "CANCELLED")


class CurriculumResource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "curriculum_resources"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "curriculum_id",
            "code",
            name="uq_curriculum_resources_tenant_curriculum_code",
        ),
        CheckConstraint(
            "resource_kind IN ("
            "'PRACTICE_SET','WORKED_EXAMPLE','CONCEPT_NOTE','INTERNAL_PACKET')",
            name="ck_curriculum_resources_kind",
        ),
        CheckConstraint(
            "status IN ('DRAFT','APPROVED','ACTIVE','DEACTIVATED')",
            name="ck_curriculum_resources_status",
        ),
        Index(
            "ix_curriculum_resources_tenant_curriculum_status",
            "tenant_id",
            "curriculum_id",
            "status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curricula.id", ondelete="RESTRICT")
    )
    code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(32), default="DRAFT", server_default="DRAFT"
    )
    content_ref: Mapped[str] = mapped_column(String(512))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CurriculumResourceNode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "curriculum_resource_nodes"
    __table_args__ = (
        UniqueConstraint(
            "resource_id",
            "curriculum_node_id",
            name="uq_curriculum_resource_nodes_resource_node",
        ),
        Index(
            "ix_curriculum_resource_nodes_tenant_resource",
            "tenant_id",
            "resource_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_resources.id", ondelete="CASCADE")
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT")
    )


class StudentResourceAssignment(UUIDPrimaryKeyMixin, Base):
    """Student assignment of an ACTIVE catalog resource.

    Idempotency grain (PostgreSQL 16): partial unique index on
    (tenant_id, student_id, resource_id, learning_recommendation_id)
    WHERE status='ASSIGNED' with NULLS NOT DISTINCT. Re-POSTing the same
    grain returns the existing ASSIGNED row without creating a duplicate.
    """

    __tablename__ = "student_resource_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ASSIGNED','CANCELLED')",
            name="ck_student_resource_assignments_status",
        ),
        Index(
            "ix_student_resource_assignments_tenant_student",
            "tenant_id",
            "student_id",
        ),
        Index(
            "ix_student_resource_assignments_tenant_resource",
            "tenant_id",
            "resource_id",
        ),
        # Partial unique grain documented above; DDL uses NULLS NOT DISTINCT.
        Index(
            "uq_student_resource_assignments_assigned_grain",
            "tenant_id",
            "student_id",
            "resource_id",
            "learning_recommendation_id",
            unique=True,
            postgresql_where=text("status = 'ASSIGNED'"),
            postgresql_nulls_not_distinct=True,
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE")
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_resources.id", ondelete="RESTRICT")
    )
    learning_recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="ASSIGNED")
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
