"""evaluation_ledger

Revision ID: 20260906_0007
Revises: 20260906_0006
Create Date: 2026-09-06 22:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260906_0007"
down_revision: str | None = "20260906_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("rules_engine_version", sa.String(length=100), nullable=True),
        sa.Column("started_by", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"], ["assessment_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["started_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "submission_id",
            "run_number",
            name="uq_evaluation_runs_tenant_submission_run",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'QUEUED','RUNNING','REVIEW_REQUIRED','COMPLETED','FAILED','SUPERSEDED')",
            name="ck_evaluation_runs_status",
        ),
    )
    op.create_index(
        "ix_evaluation_runs_tenant_submission",
        "evaluation_runs",
        ["tenant_id", "submission_id"],
    )

    op.create_table(
        "question_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_version_id", sa.Uuid(), nullable=False),
        sa.Column("answer_key_version_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_id", sa.Uuid(), nullable=True),
        sa.Column(
            "answer_region_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "transcription_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("max_mark", sa.Numeric(10, 4), nullable=False),
        sa.Column("proposed_ai_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("final_human_approved_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("first_divergence_step", sa.Integer(), nullable=True),
        sa.Column("ecf_applied", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "ecf_chain",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("alternative_method_id", sa.String(length=100), nullable=True),
        sa.Column("alternative_method_label", sa.String(length=255), nullable=True),
        sa.Column(
            "error_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "deduction_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "criterion_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("identity_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("mapping_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("transcription_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("evaluation_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("math_verification_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("workflow_state", sa.String(length=32), nullable=False),
        sa.Column("ledger_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("supersedes_ledger_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_feedback", sa.Text(), nullable=True),
        sa.Column("approved_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("ai_execution_record_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["ai_execution_record_id"], ["ai_execution_records.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["answer_key_version_id"], ["answer_key_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"], ["assessment_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["mapping_id"], ["question_answer_mappings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["question_version_id"], ["question_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["rubric_version_id"], ["rubric_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["supersedes_ledger_id"], ["question_evaluations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "evaluation_run_id",
            "question_version_id",
            name="uq_question_evaluations_tenant_run_qv",
        ),
        sa.CheckConstraint(
            "workflow_state IN ("
            "'PENDING','PROPOSED','REVIEW_REQUIRED','ACCEPTED','OVERRIDDEN','ESCALATED')",
            name="ck_question_evaluations_workflow",
        ),
    )
    op.create_index(
        "ix_question_evaluations_tenant_submission",
        "question_evaluations",
        ["tenant_id", "submission_id"],
    )
    op.create_index(
        "ix_question_evaluations_tenant_run",
        "question_evaluations",
        ["tenant_id", "evaluation_run_id"],
    )

    op.create_table(
        "criterion_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("question_evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_criterion_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_code", sa.String(length=100), nullable=False),
        sa.Column("criterion_label", sa.String(length=255), nullable=False),
        sa.Column("max_marks", sa.Numeric(10, 4), nullable=False),
        sa.Column("proposed_marks", sa.Numeric(10, 4), nullable=True),
        sa.Column("final_marks", sa.Numeric(10, 4), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("deduction_reason", sa.String(length=1000), nullable=True),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column("ecf_source_criterion_id", sa.Uuid(), nullable=True),
        sa.Column("unit_check_status", sa.String(length=32), nullable=True),
        sa.Column("precision_check_status", sa.String(length=32), nullable=True),
        sa.Column("accepted_alternative_id", sa.String(length=100), nullable=True),
        sa.Column("ai_execution_record_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["ai_execution_record_id"], ["ai_execution_records.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["ecf_source_criterion_id"], ["rubric_criteria.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["question_evaluation_id"], ["question_evaluations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rubric_criterion_id"], ["rubric_criteria.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "decision IN ('AWARDED','PARTIAL','DEDUCTED','NOT_APPLICABLE','UNREADABLE')",
            name="ck_criterion_evaluations_decision",
        ),
    )
    op.create_index(
        "ix_criterion_evaluations_tenant_qe",
        "criterion_evaluations",
        ["tenant_id", "question_evaluation_id"],
    )

    op.create_table(
        "review_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("question_evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "before_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "after_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("previous_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("new_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_evaluation_id"], ["question_evaluations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "action_type IN ("
            "'ACCEPT','OVERRIDE','EDIT_FEEDBACK','VALID_ALTERNATIVE','ESCALATE')",
            name="ck_review_actions_type",
        ),
    )
    op.create_index(
        "ix_review_actions_tenant_qe",
        "review_actions",
        ["tenant_id", "question_evaluation_id"],
    )
    op.create_index(
        "ix_review_actions_tenant_submission",
        "review_actions",
        ["tenant_id", "submission_id"],
    )

    op.add_column(
        "ai_execution_records",
        sa.Column(
            "question_evaluation_id",
            sa.Uuid(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_question_evaluation_id",
        "ai_execution_records",
        "question_evaluations",
        ["question_evaluation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # evaluation_run_id already reserved nullable in B5 migration — add FK if column exists
    op.create_foreign_key(
        "fk_ai_execution_records_evaluation_run_id",
        "ai_execution_records",
        "evaluation_runs",
        ["evaluation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_execution_records_evaluation_run_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_execution_records_question_evaluation_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "question_evaluation_id")
    op.drop_table("review_actions")
    op.drop_table("criterion_evaluations")
    op.drop_table("question_evaluations")
    op.drop_table("evaluation_runs")
