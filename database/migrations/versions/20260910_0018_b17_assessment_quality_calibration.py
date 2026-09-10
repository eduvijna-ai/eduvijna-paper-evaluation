"""b17_assessment_quality_calibration

Revision ID: 20260910_0018
Revises: 20260909_0017
Create Date: 2026-09-10 05:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260910_0018"
down_revision: str | None = "20260909_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "psychometric_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "cohort_definition",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("min_cohort_size", sa.Integer(), server_default="20", nullable=False),
        sa.Column("source_set_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "source_result_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "source_published_result_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('PENDING','COMPLETED','INSUFFICIENT_SAMPLE','FAILED')",
            name="ck_psychometric_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["assessment_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "assessment_version_id",
            "source_set_hash",
            "algorithm_version",
            name="uq_psychometric_runs_tenant_av_hash_algo",
        ),
    )
    op.create_index("ix_psychometric_runs_tenant", "psychometric_runs", ["tenant_id"])
    op.create_index(
        "ix_psychometric_runs_tenant_assessment_version",
        "psychometric_runs",
        ["tenant_id", "assessment_version_id"],
    )
    op.create_index(
        "ix_psychometric_runs_tenant_completed",
        "psychometric_runs",
        ["tenant_id", "completed_at"],
    )

    op.create_table(
        "item_psychometric_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=False),
        sa.Column("question_code", sa.String(length=100), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_mark", sa.Numeric(10, 4), nullable=False),
        sa.Column("mean_raw_score", sa.Numeric(12, 6), nullable=False),
        sa.Column("std_dev", sa.Numeric(12, 6), nullable=False),
        sa.Column("difficulty_index", sa.Numeric(12, 6), nullable=False),
        sa.Column("discrimination_index", sa.Numeric(12, 6), nullable=True),
        sa.Column("discrimination_method", sa.String(length=64), nullable=False),
        sa.Column("discrimination_status", sa.String(length=32), nullable=False),
        sa.Column("full_credit_rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("zero_score_rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("blank_rate", sa.Numeric(12, 6), nullable=True),
        sa.Column("difficulty_band", sa.String(length=32), nullable=True),
        sa.Column("discrimination_band", sa.String(length=32), nullable=True),
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
            "discrimination_status IN ('OK','UNDEFINED_VARIANCE','INSUFFICIENT_SAMPLE')",
            name="ck_item_psychometric_metrics_discrimination_status",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["question_version_id"],
            ["question_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["psychometric_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "question_version_id",
            name="uq_item_psychometric_metrics_tenant_run_qv",
        ),
    )
    op.create_index(
        "ix_item_psychometric_metrics_tenant_run",
        "item_psychometric_metrics",
        ["tenant_id", "run_id"],
    )

    op.create_table(
        "calibration_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column(
            "score_tolerance_abs",
            sa.Numeric(10, 4),
            server_default="0.5",
            nullable=False,
        ),
        sa.Column(
            "score_tolerance_pct",
            sa.Numeric(10, 4),
            server_default="0.05",
            nullable=False,
        ),
        sa.Column("min_cases", sa.Integer(), server_default="10", nullable=False),
        sa.Column("activated_by", sa.Uuid(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('DRAFT','ACTIVE','CLOSED')",
            name="ck_calibration_sessions_status",
        ),
        sa.ForeignKeyConstraint(
            ["activated_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["assessment_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_calibration_sessions_tenant", "calibration_sessions", ["tenant_id"]
    )
    op.create_index(
        "ix_calibration_sessions_tenant_assessment_version",
        "calibration_sessions",
        ["tenant_id", "assessment_version_id"],
    )
    op.create_index(
        "ix_calibration_sessions_tenant_status",
        "calibration_sessions",
        ["tenant_id", "status"],
    )

    op.create_table(
        "calibration_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("case_code", sa.String(length=64), nullable=False),
        sa.Column("published_result_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("question_evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_version_id", sa.Uuid(), nullable=False),
        sa.Column("max_mark", sa.Numeric(10, 4), nullable=False),
        sa.Column("reference_score", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "criterion_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "evidence_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("source_snapshot_hash", sa.String(length=64), nullable=False),
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
            ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["published_result_id"],
            ["published_results.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_evaluation_id"],
            ["question_evaluations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_version_id"],
            ["question_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rubric_version_id"], ["rubric_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["calibration_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "session_id",
            "case_code",
            name="uq_calibration_cases_tenant_session_code",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "session_id",
            "question_evaluation_id",
            name="uq_calibration_cases_tenant_session_qe",
        ),
    )
    op.create_index(
        "ix_calibration_cases_tenant_session",
        "calibration_cases",
        ["tenant_id", "session_id"],
    )

    op.create_table(
        "calibration_participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
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
            ["session_id"], ["calibration_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "session_id",
            "user_id",
            name="uq_calibration_participants_tenant_session_user",
        ),
    )
    op.create_index(
        "ix_calibration_participants_tenant_session",
        "calibration_participants",
        ["tenant_id", "session_id"],
    )
    op.create_index(
        "ix_calibration_participants_tenant_user",
        "calibration_participants",
        ["tenant_id", "user_id"],
    )

    op.create_table(
        "calibration_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Numeric(10, 4), nullable=False),
        sa.Column("max_mark", sa.Numeric(10, 4), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
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
            ["case_id"], ["calibration_cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["calibration_participants.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["calibration_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "session_id",
            "case_id",
            "user_id",
            name="uq_calibration_responses_tenant_session_case_user",
        ),
    )
    op.create_index(
        "ix_calibration_responses_tenant_session",
        "calibration_responses",
        ["tenant_id", "session_id"],
    )
    op.create_index(
        "ix_calibration_responses_tenant_case",
        "calibration_responses",
        ["tenant_id", "case_id"],
    )

    op.create_table(
        "calibration_session_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("metric_name", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("evaluator_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "common_case_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("icc_value", sa.Numeric(12, 6), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
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
            "status IN ('COMPLETED','INSUFFICIENT_SAMPLE','UNDEFINED')",
            name="ck_calibration_session_metrics_status",
        ),
        sa.CheckConstraint(
            "metric_name IN ('ICC_A1')",
            name="ck_calibration_session_metrics_metric_name",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["calibration_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "session_id",
            "metric_name",
            "algorithm_version",
            name="uq_calibration_session_metrics_tenant_session_metric_algo",
        ),
    )
    op.create_index(
        "ix_calibration_session_metrics_tenant_session",
        "calibration_session_metrics",
        ["tenant_id", "session_id"],
    )

    op.create_table(
        "calibration_evaluator_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("case_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mean_signed_diff", sa.Numeric(12, 6), nullable=False),
        sa.Column("mae", sa.Numeric(12, 6), nullable=False),
        sa.Column("nmae", sa.Numeric(12, 6), nullable=False),
        sa.Column("exact_match_rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("within_tolerance_rate", sa.Numeric(12, 6), nullable=False),
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
            ["session_id"], ["calibration_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "session_id",
            "user_id",
            name="uq_calibration_evaluator_metrics_tenant_session_user",
        ),
    )
    op.create_index(
        "ix_calibration_evaluator_metrics_tenant_session",
        "calibration_evaluator_metrics",
        ["tenant_id", "session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_calibration_evaluator_metrics_tenant_session",
        table_name="calibration_evaluator_metrics",
    )
    op.drop_table("calibration_evaluator_metrics")

    op.drop_index(
        "ix_calibration_session_metrics_tenant_session",
        table_name="calibration_session_metrics",
    )
    op.drop_table("calibration_session_metrics")

    op.drop_index(
        "ix_calibration_responses_tenant_case", table_name="calibration_responses"
    )
    op.drop_index(
        "ix_calibration_responses_tenant_session",
        table_name="calibration_responses",
    )
    op.drop_table("calibration_responses")

    op.drop_index(
        "ix_calibration_participants_tenant_user",
        table_name="calibration_participants",
    )
    op.drop_index(
        "ix_calibration_participants_tenant_session",
        table_name="calibration_participants",
    )
    op.drop_table("calibration_participants")

    op.drop_index(
        "ix_calibration_cases_tenant_session", table_name="calibration_cases"
    )
    op.drop_table("calibration_cases")

    op.drop_index(
        "ix_calibration_sessions_tenant_status", table_name="calibration_sessions"
    )
    op.drop_index(
        "ix_calibration_sessions_tenant_assessment_version",
        table_name="calibration_sessions",
    )
    op.drop_index("ix_calibration_sessions_tenant", table_name="calibration_sessions")
    op.drop_table("calibration_sessions")

    op.drop_index(
        "ix_item_psychometric_metrics_tenant_run",
        table_name="item_psychometric_metrics",
    )
    op.drop_table("item_psychometric_metrics")

    op.drop_index(
        "ix_psychometric_runs_tenant_completed", table_name="psychometric_runs"
    )
    op.drop_index(
        "ix_psychometric_runs_tenant_assessment_version",
        table_name="psychometric_runs",
    )
    op.drop_index("ix_psychometric_runs_tenant", table_name="psychometric_runs")
    op.drop_table("psychometric_runs")
