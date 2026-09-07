"""analytics_mastery_evidence

Revision ID: 20260907_0009
Revises: 20260907_0008
Create Date: 2026-09-07 09:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0009"
down_revision: str | None = "20260907_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_pipeline_jobs_stage", "pipeline_jobs", type_="check")
    op.create_check_constraint(
        "ck_pipeline_jobs_stage",
        "pipeline_jobs",
        "stage IN ("
        "'PAGE_NORMALIZATION','IDENTITY','MAPPING','TRANSCRIPTION',"
        "'EVALUATION','PUBLICATION','ANALYTICS')",
    )

    op.create_table(
        "mastery_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.Column("published_result_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("question_evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("strength", sa.String(length=32), nullable=False),
        sa.Column("score_ratio", sa.Numeric(10, 6), nullable=False),
        sa.Column("source_final_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("source_max_mark", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "mapping_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("mapping_weight", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "academic_error_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "review_condition_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "reason_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_ledger_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
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
            ["assessment_version_id"],
            ["assessment_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"], ["curriculum_nodes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="RESTRICT"
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
            "published_result_id",
            "question_evaluation_id",
            "curriculum_node_id",
            "evidence_type",
            "algorithm_version",
            name="uq_mastery_evidence_idempotency",
        ),
        sa.CheckConstraint(
            "evidence_type IN ('CONCEPT','EXECUTION','PROCEDURE')",
            name="ck_mastery_evidence_type",
        ),
        sa.CheckConstraint(
            "strength IN ('STRONG','WEAK','INCONCLUSIVE')",
            name="ck_mastery_evidence_strength",
        ),
        sa.CheckConstraint(
            "score_ratio >= 0 AND score_ratio <= 1",
            name="ck_mastery_evidence_score_ratio",
        ),
        sa.CheckConstraint(
            "source_final_score >= 0 AND source_max_mark > 0 "
            "AND source_final_score <= source_max_mark",
            name="ck_mastery_evidence_scores",
        ),
    )
    op.create_index(
        "ix_mastery_evidence_tenant_student_node",
        "mastery_evidence",
        ["tenant_id", "student_id", "curriculum_node_id"],
    )
    op.create_index(
        "ix_mastery_evidence_tenant_assessment_node",
        "mastery_evidence",
        ["tenant_id", "assessment_id", "curriculum_node_id"],
    )
    op.create_index(
        "ix_mastery_evidence_tenant_published_result",
        "mastery_evidence",
        ["tenant_id", "published_result_id"],
    )
    op.create_index(
        "ix_mastery_evidence_tenant_question_evaluation",
        "mastery_evidence",
        ["tenant_id", "question_evaluation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mastery_evidence_tenant_question_evaluation", table_name="mastery_evidence"
    )
    op.drop_index(
        "ix_mastery_evidence_tenant_published_result", table_name="mastery_evidence"
    )
    op.drop_index(
        "ix_mastery_evidence_tenant_assessment_node", table_name="mastery_evidence"
    )
    op.drop_index(
        "ix_mastery_evidence_tenant_student_node", table_name="mastery_evidence"
    )
    op.drop_table("mastery_evidence")

    op.drop_constraint("ck_pipeline_jobs_stage", "pipeline_jobs", type_="check")
    op.create_check_constraint(
        "ck_pipeline_jobs_stage",
        "pipeline_jobs",
        "stage IN ("
        "'PAGE_NORMALIZATION','IDENTITY','MAPPING','TRANSCRIPTION',"
        "'EVALUATION','PUBLICATION')",
    )
