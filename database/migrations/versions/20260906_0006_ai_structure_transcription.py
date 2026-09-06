"""ai_structure_transcription

Revision ID: 20260906_0006
Revises: 20260906_0005
Create Date: 2026-09-06 21:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260906_0006"
down_revision: str | None = "20260906_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column(
            "transcription_state",
            sa.String(length=32),
            server_default="NOT_STARTED",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_submissions_transcription_state",
        "submissions",
        "transcription_state IN ("
        "'NOT_STARTED','QUEUED','RUNNING','REVIEW_REQUIRED',"
        "'READY','FAILED','UNAVAILABLE')",
    )

    op.drop_constraint("ck_pipeline_jobs_stage", "pipeline_jobs", type_="check")
    op.create_check_constraint(
        "ck_pipeline_jobs_stage",
        "pipeline_jobs",
        "stage IN ("
        "'PAGE_NORMALIZATION','IDENTITY','MAPPING','TRANSCRIPTION','EVALUATION')",
    )

    op.add_column(
        "answer_regions",
        sa.Column("crop_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "answer_regions",
        sa.Column("crop_content_sha256", sa.String(length=64), nullable=True),
    )

    op.add_column(
        "ai_execution_records",
        sa.Column("submission_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("answer_region_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("model_version", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("prompt_template_version", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column(
            "input_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("input_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column(
            "token_usage",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("error_class", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_exec_submission",
        "ai_execution_records",
        "submissions",
        ["submission_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ai_exec_answer_region",
        "ai_execution_records",
        "answer_regions",
        ["answer_region_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_ai_exec_tenant_submission",
        "ai_execution_records",
        ["tenant_id", "submission_id"],
    )

    op.create_table(
        "submission_identity_candidates",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("ai_execution_record_id", sa.Uuid(), nullable=True),
        sa.Column("rank_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('AI','HUMAN')",
            name="ck_identity_candidates_source",
        ),
        sa.ForeignKeyConstraint(
            ["ai_execution_record_id"], ["ai_execution_records.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "submission_id",
            "student_id",
            "source_type",
            name="uq_identity_candidates_tenant_sub_student_src",
        ),
    )
    op.create_index(
        "ix_identity_candidates_tenant_submission",
        "submission_identity_candidates",
        ["tenant_id", "submission_id"],
    )

    op.create_table(
        "submission_page_analyses",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_page_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "result_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ai_execution_record_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
            "status IN ('SUCCEEDED','FAILED','UNAVAILABLE')",
            name="ck_page_analyses_status",
        ),
        sa.ForeignKeyConstraint(
            ["ai_execution_record_id"], ["ai_execution_records.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["submission_page_id"], ["submission_pages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "submission_page_id",
            "analysis_version",
            name="uq_page_analyses_tenant_page_version",
        ),
    )

    op.create_table(
        "answer_region_transcriptions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("answer_region_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("latex", sa.Text(), nullable=True),
        sa.Column(
            "segments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("transcription_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("unreadable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("visual_only", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ai_execution_record_id", sa.Uuid(), nullable=True),
        sa.Column("supersedes_transcription_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
            "source_type IN ('AI','HUMAN')",
            name="ck_region_transcriptions_source",
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED','REVIEW_REQUIRED','CONFIRMED','SUPERSEDED')",
            name="ck_region_transcriptions_status",
        ),
        sa.ForeignKeyConstraint(
            ["ai_execution_record_id"], ["ai_execution_records.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["answer_region_id"], ["answer_regions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["supersedes_transcription_id"],
            ["answer_region_transcriptions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "answer_region_id",
            "version_number",
            name="uq_region_transcriptions_tenant_region_version",
        ),
    )
    op.create_index(
        "ix_region_transcriptions_tenant_region",
        "answer_region_transcriptions",
        ["tenant_id", "answer_region_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_region_transcriptions_tenant_region",
        table_name="answer_region_transcriptions",
    )
    op.drop_table("answer_region_transcriptions")
    op.drop_table("submission_page_analyses")
    op.drop_index(
        "ix_identity_candidates_tenant_submission",
        table_name="submission_identity_candidates",
    )
    op.drop_table("submission_identity_candidates")
    op.drop_index("ix_ai_exec_tenant_submission", table_name="ai_execution_records")
    op.drop_constraint("fk_ai_exec_answer_region", "ai_execution_records", type_="foreignkey")
    op.drop_constraint("fk_ai_exec_submission", "ai_execution_records", type_="foreignkey")
    for col in (
        "finished_at",
        "started_at",
        "error_class",
        "token_usage",
        "latency_ms",
        "input_hash",
        "input_refs",
        "prompt_template_version",
        "model_version",
        "model",
        "evaluation_run_id",
        "answer_region_id",
        "submission_id",
    ):
        op.drop_column("ai_execution_records", col)
    op.drop_column("answer_regions", "crop_content_sha256")
    op.drop_column("answer_regions", "crop_storage_key")
    op.drop_constraint("ck_pipeline_jobs_stage", "pipeline_jobs", type_="check")
    op.create_check_constraint(
        "ck_pipeline_jobs_stage",
        "pipeline_jobs",
        "stage IN ('PAGE_NORMALIZATION','IDENTITY','MAPPING','EVALUATION')",
    )
    op.drop_constraint("ck_submissions_transcription_state", "submissions", type_="check")
    op.drop_column("submissions", "transcription_state")
