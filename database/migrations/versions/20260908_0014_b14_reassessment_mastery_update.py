"""b14_reassessment_mastery_update

Revision ID: 20260908_0014
Revises: 20260907_0013
Create Date: 2026-09-08 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0014"
down_revision: str | None = "20260907_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing assessments must be EXAM-only before introducing the type CK.
    conn = op.get_bind()
    non_exam = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM assessments "
            "WHERE assessment_type IS DISTINCT FROM 'EXAM'"
        )
    ).scalar()
    if int(non_exam or 0) > 0:
        raise RuntimeError(
            "Cannot add ck_assessments_assessment_type: "
            "non-EXAM assessment_type rows exist"
        )

    op.create_check_constraint(
        "ck_assessments_assessment_type",
        "assessments",
        "assessment_type IN ('EXAM','IMPROVEMENT_REASSESSMENT')",
    )

    op.create_table(
        "reassessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("improvement_assessment_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=True),
        sa.Column("published_result_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("instantiation_hash", sa.String(length=64), nullable=False),
        sa.Column("baseline_captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "algorithm_version",
            sa.String(length=32),
            server_default="B14_V1",
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
            "status IN ('CREATED','SUBMITTED','PUBLISHED')",
            name="ck_reassessments_status",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["assessment_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["improvement_assessment_id"],
            ["improvement_assessments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_result_id"],
            ["published_results.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "improvement_assessment_id",
            name="uq_reassessments_tenant_blueprint",
        ),
        sa.UniqueConstraint(
            "assessment_id",
            name="uq_reassessments_assessment",
        ),
    )
    op.create_index(
        "ix_reassessments_tenant_student",
        "reassessments",
        ["tenant_id", "student_id"],
    )
    op.create_index(
        "ix_reassessments_tenant_blueprint",
        "reassessments",
        ["tenant_id", "improvement_assessment_id"],
    )
    op.create_index(
        "ix_reassessments_tenant_assessment",
        "reassessments",
        ["tenant_id", "assessment_id"],
    )
    op.create_index(
        "ix_reassessments_tenant_submission",
        "reassessments",
        ["tenant_id", "submission_id"],
    )
    op.create_index(
        "ix_reassessments_tenant_published_result",
        "reassessments",
        ["tenant_id", "published_result_id"],
    )

    op.create_table(
        "reassessment_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reassessment_id", sa.Uuid(), nullable=False),
        sa.Column("improvement_assessment_item_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.Column("item_code_snapshot", sa.String(length=100), nullable=False),
        sa.Column("template_kind_snapshot", sa.String(length=64), nullable=False),
        sa.Column(
            "question_template_ref_snapshot", sa.String(length=255), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"],
            ["curriculum_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["improvement_assessment_item_id"],
            ["improvement_assessment_items.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_version_id"],
            ["question_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reassessment_id"],
            ["reassessments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reassessment_id",
            "improvement_assessment_item_id",
            name="uq_reassessment_items_blueprint_item",
        ),
        sa.UniqueConstraint(
            "question_version_id",
            name="uq_reassessment_items_question_version",
        ),
    )
    op.create_index(
        "ix_reassessment_items_tenant_reassessment",
        "reassessment_items",
        ["tenant_id", "reassessment_id"],
    )

    op.create_table(
        "reassessment_mastery_deltas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reassessment_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_concept_mastery", sa.Numeric(10, 6), nullable=True),
        sa.Column("baseline_execution_accuracy", sa.Numeric(10, 6), nullable=True),
        sa.Column("baseline_concept_decisive_count", sa.Integer(), nullable=False),
        sa.Column("baseline_execution_decisive_count", sa.Integer(), nullable=False),
        sa.Column(
            "baseline_concept_inconclusive_count", sa.Integer(), nullable=False
        ),
        sa.Column(
            "baseline_execution_inconclusive_count", sa.Integer(), nullable=False
        ),
        sa.Column("baseline_evidence_count", sa.Integer(), nullable=False),
        sa.Column(
            "baseline_source_evidence_hash", sa.String(length=64), nullable=False
        ),
        sa.Column("post_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("post_published_result_id", sa.Uuid(), nullable=True),
        sa.Column("post_concept_mastery", sa.Numeric(10, 6), nullable=True),
        sa.Column("post_execution_accuracy", sa.Numeric(10, 6), nullable=True),
        sa.Column("post_concept_decisive_count", sa.Integer(), nullable=True),
        sa.Column("post_execution_decisive_count", sa.Integer(), nullable=True),
        sa.Column("post_concept_inconclusive_count", sa.Integer(), nullable=True),
        sa.Column("post_execution_inconclusive_count", sa.Integer(), nullable=True),
        sa.Column("post_evidence_count", sa.Integer(), nullable=True),
        sa.Column("post_source_evidence_hash", sa.String(length=64), nullable=True),
        sa.Column("concept_delta", sa.Numeric(10, 6), nullable=True),
        sa.Column("execution_delta", sa.Numeric(10, 6), nullable=True),
        sa.Column("materialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "algorithm_version",
            sa.String(length=32),
            server_default="B14_V1",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"],
            ["curriculum_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["post_published_result_id"],
            ["published_results.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["post_snapshot_id"],
            ["mastery_state_snapshots.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reassessment_id"],
            ["reassessments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "reassessment_id",
            "curriculum_node_id",
            "algorithm_version",
            name="uq_reassessment_mastery_deltas_grain",
        ),
    )
    op.create_index(
        "ix_reassessment_mastery_deltas_tenant_reassessment",
        "reassessment_mastery_deltas",
        ["tenant_id", "reassessment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reassessment_mastery_deltas_tenant_reassessment",
        table_name="reassessment_mastery_deltas",
    )
    op.drop_table("reassessment_mastery_deltas")
    op.drop_index(
        "ix_reassessment_items_tenant_reassessment",
        table_name="reassessment_items",
    )
    op.drop_table("reassessment_items")
    op.drop_index(
        "ix_reassessments_tenant_published_result", table_name="reassessments"
    )
    op.drop_index("ix_reassessments_tenant_submission", table_name="reassessments")
    op.drop_index("ix_reassessments_tenant_assessment", table_name="reassessments")
    op.drop_index("ix_reassessments_tenant_blueprint", table_name="reassessments")
    op.drop_index("ix_reassessments_tenant_student", table_name="reassessments")
    op.drop_table("reassessments")
    op.drop_constraint(
        "ck_assessments_assessment_type", "assessments", type_="check"
    )
