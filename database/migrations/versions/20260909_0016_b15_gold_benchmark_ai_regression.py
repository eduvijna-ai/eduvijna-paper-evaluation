"""b15_gold_benchmark_ai_regression

Revision ID: 20260909_0016
Revises: 20260908_0015
Create Date: 2026-09-09 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260909_0016"
down_revision: str | None = "20260908_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "benchmark_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "code", name="uq_benchmark_datasets_tenant_code"
        ),
    )
    op.create_index(
        "ix_benchmark_datasets_tenant", "benchmark_datasets", ["tenant_id"]
    )
    op.create_index(
        "ix_benchmark_datasets_tenant_created",
        "benchmark_datasets",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "benchmark_dataset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "threshold_profile_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("case_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("locked_by", sa.Uuid(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('DRAFT','LOCKED')",
            name="ck_benchmark_dataset_versions_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["benchmark_datasets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["locked_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "dataset_id",
            "version_number",
            name="uq_benchmark_dataset_versions_tenant_dataset_number",
        ),
    )
    op.create_index(
        "ix_benchmark_dataset_versions_tenant_dataset",
        "benchmark_dataset_versions",
        ["tenant_id", "dataset_id"],
    )

    op.create_table(
        "benchmark_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("published_result_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("question_evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=False),
        sa.Column("rubric_version_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("expected_final_marks", sa.Numeric(10, 4), nullable=False),
        sa.Column("expected_max_marks", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "expected_error_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("source_ledger_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("adjudicated_by", sa.Uuid(), nullable=True),
        sa.Column("adjudicated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "replay_fixture",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
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
            ["adjudicated_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["assessment_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["benchmark_dataset_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation_runs.id"],
            ondelete="RESTRICT",
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
            ["rubric_version_id"],
            ["rubric_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_version_id",
            "question_evaluation_id",
            name="uq_benchmark_cases_version_qe",
        ),
    )
    op.create_index(
        "ix_benchmark_cases_tenant_version",
        "benchmark_cases",
        ["tenant_id", "dataset_version_id"],
    )

    op.create_table(
        "benchmark_regression_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("candidate_provider", sa.String(length=100), nullable=False),
        sa.Column("candidate_model", sa.String(length=100), nullable=False),
        sa.Column("candidate_model_version", sa.String(length=100), nullable=False),
        sa.Column(
            "candidate_prompt_template_version",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "candidate_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "threshold_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "aggregate_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("initiated_by", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','PASSED','FAILED','ERROR')",
            name="ck_benchmark_regression_runs_status",
        ),
        sa.CheckConstraint(
            "verdict IN ('PASS','FAIL','PENDING')",
            name="ck_benchmark_regression_runs_verdict",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["benchmark_dataset_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["initiated_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_benchmark_regression_runs_tenant_version",
        "benchmark_regression_runs",
        ["tenant_id", "dataset_version_id"],
    )
    op.create_index(
        "uq_benchmark_regression_runs_tenant_idempotency",
        "benchmark_regression_runs",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "benchmark_regression_case_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("regression_run_id", sa.Uuid(), nullable=False),
        sa.Column("benchmark_case_id", sa.Uuid(), nullable=False),
        sa.Column(
            "missing_output",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("actual_marks", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "actual_error_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("score_abs_error", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "exact_score_match",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("taxonomy_match", sa.Boolean(), nullable=True),
        sa.Column(
            "safety_invariant_failed",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "diff",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
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
            ["ai_execution_record_id"],
            ["ai_execution_records.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["benchmark_case_id"],
            ["benchmark_cases.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["regression_run_id"],
            ["benchmark_regression_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "regression_run_id",
            "benchmark_case_id",
            name="uq_benchmark_regression_case_results_run_case",
        ),
    )
    op.create_index(
        "ix_benchmark_regression_case_results_tenant_run",
        "benchmark_regression_case_results",
        ["tenant_id", "regression_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_benchmark_regression_case_results_tenant_run",
        table_name="benchmark_regression_case_results",
    )
    op.drop_table("benchmark_regression_case_results")
    op.drop_index(
        "uq_benchmark_regression_runs_tenant_idempotency",
        table_name="benchmark_regression_runs",
    )
    op.drop_index(
        "ix_benchmark_regression_runs_tenant_version",
        table_name="benchmark_regression_runs",
    )
    op.drop_table("benchmark_regression_runs")
    op.drop_index(
        "ix_benchmark_cases_tenant_version", table_name="benchmark_cases"
    )
    op.drop_table("benchmark_cases")
    op.drop_index(
        "ix_benchmark_dataset_versions_tenant_dataset",
        table_name="benchmark_dataset_versions",
    )
    op.drop_table("benchmark_dataset_versions")
    op.drop_index(
        "ix_benchmark_datasets_tenant_created", table_name="benchmark_datasets"
    )
    op.drop_index("ix_benchmark_datasets_tenant", table_name="benchmark_datasets")
    op.drop_table("benchmark_datasets")
