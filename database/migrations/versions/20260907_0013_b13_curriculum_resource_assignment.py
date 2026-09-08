"""b13_curriculum_resource_assignment

Revision ID: 20260907_0013
Revises: 20260907_0012
Create Date: 2026-09-07 24:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0013"
down_revision: str | None = "20260907_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "curriculum_resources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource_kind", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column("content_ref", sa.String(length=512), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resource_kind IN ("
            "'PRACTICE_SET','WORKED_EXAMPLE','CONCEPT_NOTE','INTERNAL_PACKET')",
            name="ck_curriculum_resources_kind",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','APPROVED','ACTIVE','DEACTIVATED')",
            name="ck_curriculum_resources_status",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "curriculum_id",
            "code",
            name="uq_curriculum_resources_tenant_curriculum_code",
        ),
    )
    op.create_index(
        "ix_curriculum_resources_tenant_curriculum_status",
        "curriculum_resources",
        ["tenant_id", "curriculum_id", "status"],
    )

    op.create_table(
        "curriculum_resource_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"],
            ["curriculum_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["curriculum_resources.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resource_id",
            "curriculum_node_id",
            name="uq_curriculum_resource_nodes_resource_node",
        ),
    )
    op.create_index(
        "ix_curriculum_resource_nodes_tenant_resource",
        "curriculum_resource_nodes",
        ["tenant_id", "resource_id"],
    )

    op.create_table(
        "student_resource_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("learning_recommendation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_by", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ASSIGNED','CANCELLED')",
            name="ck_student_resource_assignments_status",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["learning_recommendation_id"],
            ["learning_recommendations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["curriculum_resources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_student_resource_assignments_tenant_student",
        "student_resource_assignments",
        ["tenant_id", "student_id"],
    )
    op.create_index(
        "ix_student_resource_assignments_tenant_resource",
        "student_resource_assignments",
        ["tenant_id", "resource_id"],
    )
    # Idempotency grain: one ASSIGNED row per
    # (tenant, student, resource, learning_recommendation_id) with NULLS NOT DISTINCT.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_student_resource_assignments_assigned_grain
        ON student_resource_assignments (
            tenant_id,
            student_id,
            resource_id,
            learning_recommendation_id
        )
        NULLS NOT DISTINCT
        WHERE status = 'ASSIGNED'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_student_resource_assignments_assigned_grain")
    op.drop_index(
        "ix_student_resource_assignments_tenant_resource",
        table_name="student_resource_assignments",
    )
    op.drop_index(
        "ix_student_resource_assignments_tenant_student",
        table_name="student_resource_assignments",
    )
    op.drop_table("student_resource_assignments")
    op.drop_index(
        "ix_curriculum_resource_nodes_tenant_resource",
        table_name="curriculum_resource_nodes",
    )
    op.drop_table("curriculum_resource_nodes")
    op.drop_index(
        "ix_curriculum_resources_tenant_curriculum_status",
        table_name="curriculum_resources",
    )
    op.drop_table("curriculum_resources")
