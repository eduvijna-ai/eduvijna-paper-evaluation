"""cvb_release_closure

Revision ID: 20260907_0011
Revises: 20260907_0010
Create Date: 2026-09-07 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0011"
down_revision: str | None = "20260907_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessment_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("security_scan_status", sa.String(length=32), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "artifact_type IN ('QUESTION_PAPER')",
            name="ck_assessment_artifacts_artifact_type",
        ),
        sa.CheckConstraint(
            "security_scan_status IN ('NOT_CONFIGURED','CLEAN','REJECTED','ERROR')",
            name="ck_assessment_artifacts_security_scan_status",
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_assessment_artifacts_storage_key"),
    )
    op.create_index(
        "ix_assessment_artifacts_tenant_assessment",
        "assessment_artifacts",
        ["tenant_id", "assessment_id"],
    )
    op.create_index(
        "ix_assessment_artifacts_tenant_uploaded_at",
        "assessment_artifacts",
        ["tenant_id", "uploaded_at"],
    )

    op.create_table(
        "authoring_ai_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=True),
        sa.Column("assessment_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("proposal_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("answer_key_version_id", sa.Uuid(), nullable=True),
        sa.Column("rubric_version_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
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
            "operation IN ("
            "'PARSE_QUESTION_PAPER','PROPOSE_ANSWER_KEY',"
            "'PROPOSE_RUBRIC','SUGGEST_CURRICULUM_MAPPING')",
            name="ck_authoring_ai_runs_operation",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'QUEUED','RUNNING','REVIEW_REQUIRED',"
            "'SUCCEEDED','FAILED','UNAVAILABLE')",
            name="ck_authoring_ai_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["answer_key_version_id"], ["answer_key_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_artifact_id"], ["assessment_artifacts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"], ["assessment_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_version_id"], ["question_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["rubric_version_id"], ["rubric_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_authoring_ai_runs_tenant_assessment_version",
        "authoring_ai_runs",
        ["tenant_id", "assessment_version_id"],
    )
    op.create_index(
        "ix_authoring_ai_runs_tenant_status",
        "authoring_ai_runs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_authoring_ai_runs_tenant_operation_input",
        "authoring_ai_runs",
        ["tenant_id", "operation", "input_hash"],
    )

    # Convert bare UUID to real FK. Column already nullable; no data expected.
    with op.batch_alter_table("assessment_versions") as batch_op:
        batch_op.create_foreign_key(
            "fk_assessment_versions_question_paper_artifact_id",
            "assessment_artifacts",
            ["question_paper_artifact_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.add_column(
        "ai_execution_records",
        sa.Column("authoring_ai_run_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_authoring_ai_run_id",
        "ai_execution_records",
        "authoring_ai_runs",
        ["authoring_ai_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("assessment_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_assessment_version_id",
        "ai_execution_records",
        "assessment_versions",
        ["assessment_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("assessment_artifact_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_assessment_artifact_id",
        "ai_execution_records",
        "assessment_artifacts",
        ["assessment_artifact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("answer_key_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_answer_key_version_id",
        "ai_execution_records",
        "answer_key_versions",
        ["answer_key_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("rubric_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_rubric_version_id",
        "ai_execution_records",
        "rubric_versions",
        ["rubric_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_execution_records_rubric_version_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "rubric_version_id")
    op.drop_constraint(
        "fk_ai_execution_records_answer_key_version_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "answer_key_version_id")
    op.drop_constraint(
        "fk_ai_execution_records_assessment_artifact_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "assessment_artifact_id")
    op.drop_constraint(
        "fk_ai_execution_records_assessment_version_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "assessment_version_id")
    op.drop_constraint(
        "fk_ai_execution_records_authoring_ai_run_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "authoring_ai_run_id")

    with op.batch_alter_table("assessment_versions") as batch_op:
        batch_op.drop_constraint(
            "fk_assessment_versions_question_paper_artifact_id",
            type_="foreignkey",
        )

    op.drop_index(
        "ix_authoring_ai_runs_tenant_operation_input", table_name="authoring_ai_runs"
    )
    op.drop_index("ix_authoring_ai_runs_tenant_status", table_name="authoring_ai_runs")
    op.drop_index(
        "ix_authoring_ai_runs_tenant_assessment_version", table_name="authoring_ai_runs"
    )
    op.drop_table("authoring_ai_runs")

    op.drop_index(
        "ix_assessment_artifacts_tenant_uploaded_at", table_name="assessment_artifacts"
    )
    op.drop_index(
        "ix_assessment_artifacts_tenant_assessment", table_name="assessment_artifacts"
    )
    op.drop_table("assessment_artifacts")
