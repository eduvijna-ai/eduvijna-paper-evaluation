"""b12_longitudinal_mastery_mistake_intelligence

Revision ID: 20260907_0012
Revises: 20260907_0011
Create Date: 2026-09-07 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0012"
down_revision: str | None = "20260907_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mastery_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.Column("concept_mastery", sa.Numeric(10, 6), nullable=True),
        sa.Column("execution_accuracy", sa.Numeric(10, 6), nullable=True),
        sa.Column("concept_decisive_count", sa.Integer(), nullable=False),
        sa.Column("execution_decisive_count", sa.Integer(), nullable=False),
        sa.Column("concept_inconclusive_count", sa.Integer(), nullable=False),
        sa.Column("execution_inconclusive_count", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("source_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "algorithm_version",
            sa.String(length=32),
            server_default="B12_V1",
            nullable=False,
        ),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_node_id",
            "algorithm_version",
            name="uq_mastery_states_student_node_algo",
        ),
        sa.CheckConstraint(
            "concept_mastery IS NULL OR (concept_mastery >= 0 AND concept_mastery <= 1)",
            name="ck_mastery_states_concept_mastery",
        ),
        sa.CheckConstraint(
            "execution_accuracy IS NULL OR "
            "(execution_accuracy >= 0 AND execution_accuracy <= 1)",
            name="ck_mastery_states_execution_accuracy",
        ),
        sa.CheckConstraint(
            "concept_decisive_count >= 0 AND execution_decisive_count >= 0 "
            "AND concept_inconclusive_count >= 0 AND execution_inconclusive_count >= 0 "
            "AND evidence_count >= 0",
            name="ck_mastery_states_counts",
        ),
    )
    op.create_index(
        "ix_mastery_states_tenant_student",
        "mastery_states",
        ["tenant_id", "student_id"],
    )
    op.create_index(
        "ix_mastery_states_tenant_node",
        "mastery_states",
        ["tenant_id", "curriculum_node_id"],
    )

    op.create_table(
        "mastery_state_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.Column("published_result_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("concept_mastery", sa.Numeric(10, 6), nullable=True),
        sa.Column("execution_accuracy", sa.Numeric(10, 6), nullable=True),
        sa.Column("concept_decisive_count", sa.Integer(), nullable=False),
        sa.Column("execution_decisive_count", sa.Integer(), nullable=False),
        sa.Column("concept_inconclusive_count", sa.Integer(), nullable=False),
        sa.Column("execution_inconclusive_count", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("source_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "algorithm_version",
            sa.String(length=32),
            server_default="B12_V1",
            nullable=False,
        ),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["published_result_id"],
            ["published_results.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_node_id",
            "published_result_id",
            "algorithm_version",
            name="uq_mastery_state_snapshots_grain",
        ),
        sa.CheckConstraint(
            "concept_mastery IS NULL OR (concept_mastery >= 0 AND concept_mastery <= 1)",
            name="ck_mastery_state_snapshots_concept_mastery",
        ),
        sa.CheckConstraint(
            "execution_accuracy IS NULL OR "
            "(execution_accuracy >= 0 AND execution_accuracy <= 1)",
            name="ck_mastery_state_snapshots_execution_accuracy",
        ),
        sa.CheckConstraint(
            "concept_decisive_count >= 0 AND execution_decisive_count >= 0 "
            "AND concept_inconclusive_count >= 0 AND execution_inconclusive_count >= 0 "
            "AND evidence_count >= 0",
            name="ck_mastery_state_snapshots_counts",
        ),
    )
    op.create_index(
        "ix_mastery_state_snapshots_tenant_student_effective",
        "mastery_state_snapshots",
        ["tenant_id", "student_id", "effective_at"],
    )

    op.create_table(
        "mistake_notebook_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("published_result_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("question_evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=False),
        sa.Column("academic_error_code", sa.String(length=64), nullable=False),
        sa.Column("final_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("max_mark", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "deduction_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("first_divergence_step", sa.Text(), nullable=True),
        sa.Column(
            "curriculum_node_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("recommended_practice_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "linked_learning_recommendation_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_ledger_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "source_mastery_evidence_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "algorithm_version",
            sa.String(length=32),
            server_default="B12_V1",
            nullable=False,
        ),
        sa.Column("materialized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["published_result_id"],
            ["published_results.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_evaluation_id"],
            ["question_evaluations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_version_id"],
            ["question_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "student_id",
            "published_result_id",
            "question_evaluation_id",
            "academic_error_code",
            "algorithm_version",
            name="uq_mistake_notebook_entries_grain",
        ),
        sa.CheckConstraint(
            "recommended_practice_kind IN ("
            "'CONCEPT_CHECK','EXECUTION_PRACTICE','PROCEDURE_PRACTICE')",
            name="ck_mistake_notebook_practice_kind",
        ),
        sa.CheckConstraint(
            "final_score >= 0 AND max_mark > 0 AND final_score <= max_mark",
            name="ck_mistake_notebook_scores",
        ),
    )
    op.create_index(
        "ix_mistake_notebook_tenant_student_effective",
        "mistake_notebook_entries",
        ["tenant_id", "student_id", "effective_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mistake_notebook_tenant_student_effective",
        table_name="mistake_notebook_entries",
    )
    op.drop_table("mistake_notebook_entries")
    op.drop_index(
        "ix_mastery_state_snapshots_tenant_student_effective",
        table_name="mastery_state_snapshots",
    )
    op.drop_table("mastery_state_snapshots")
    op.drop_index("ix_mastery_states_tenant_node", table_name="mastery_states")
    op.drop_index("ix_mastery_states_tenant_student", table_name="mastery_states")
    op.drop_table("mastery_states")
