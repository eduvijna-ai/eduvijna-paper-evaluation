"""publication_reports

Revision ID: 20260907_0008
Revises: 20260906_0007
Create Date: 2026-09-07 06:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0008"
down_revision: str | None = "20260906_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_pipeline_jobs_stage", "pipeline_jobs", type_="check")
    op.create_check_constraint(
        "ck_pipeline_jobs_stage",
        "pipeline_jobs",
        "stage IN ("
        "'PAGE_NORMALIZATION','IDENTITY','MAPPING','TRANSCRIPTION',"
        "'EVALUATION','PUBLICATION')",
    )

    op.create_table(
        "published_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ledger_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("total_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("max_total_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("annotated_pdf_s3_key", sa.String(length=512), nullable=True),
        sa.Column("annotated_pdf_sha256", sa.String(length=64), nullable=True),
        sa.Column("annotated_pdf_byte_size", sa.BigInteger(), nullable=True),
        sa.Column("student_report_s3_key", sa.String(length=512), nullable=True),
        sa.Column("student_report_sha256", sa.String(length=64), nullable=True),
        sa.Column("student_report_byte_size", sa.BigInteger(), nullable=True),
        sa.Column(
            "student_report_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("parent_report_s3_key", sa.String(length=512), nullable=True),
        sa.Column("parent_report_sha256", sa.String(length=64), nullable=True),
        sa.Column("parent_report_byte_size", sa.BigInteger(), nullable=True),
        sa.Column(
            "parent_report_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("teacher_report_s3_key", sa.String(length=512), nullable=True),
        sa.Column("teacher_report_sha256", sa.String(length=64), nullable=True),
        sa.Column("teacher_report_byte_size", sa.BigInteger(), nullable=True),
        sa.Column(
            "teacher_report_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("narrative_source", sa.String(length=32), nullable=True),
        sa.Column("generated_by", sa.Uuid(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("supersedes_result_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["supersedes_result_id"], ["published_results.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "submission_id",
            "version_number",
            name="uq_published_results_tenant_submission_version",
        ),
        sa.CheckConstraint(
            "status IN ('READY','GENERATING','GENERATED','PUBLISHED','FAILED')",
            name="ck_published_results_status",
        ),
    )
    op.create_index(
        "ix_published_results_tenant_submission",
        "published_results",
        ["tenant_id", "submission_id"],
    )
    op.create_index(
        "ix_published_results_tenant_status",
        "published_results",
        ["tenant_id", "status"],
    )

    op.create_table(
        "annotations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("submission_page_id", sa.Uuid(), nullable=False),
        sa.Column("question_evaluation_id", sa.Uuid(), nullable=True),
        sa.Column("answer_region_id", sa.Uuid(), nullable=True),
        sa.Column("published_result_id", sa.Uuid(), nullable=False),
        sa.Column("annotation_type", sa.String(length=32), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["answer_region_id"], ["answer_regions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["published_result_id"], ["published_results.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_evaluation_id"],
            ["question_evaluations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["submission_page_id"], ["submission_pages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "annotation_type IN ('TICK','CROSS','PARTIAL','MARK','COMMENT','HIGHLIGHT')",
            name="ck_annotations_type",
        ),
        sa.CheckConstraint(
            "source_type IN ('LEDGER','HUMAN')",
            name="ck_annotations_source_type",
        ),
        sa.CheckConstraint(
            "x >= 0 AND y >= 0 AND width > 0 AND height > 0 "
            "AND x + width <= 1.000001 AND y + height <= 1.000001",
            name="ck_annotations_normalized_geometry",
        ),
    )
    op.create_index(
        "ix_annotations_tenant_published_result",
        "annotations",
        ["tenant_id", "published_result_id"],
    )
    op.create_index(
        "ix_annotations_tenant_submission",
        "annotations",
        ["tenant_id", "submission_id"],
    )

    op.add_column(
        "ai_execution_records",
        sa.Column("published_result_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_published_result_id",
        "ai_execution_records",
        "published_results",
        ["published_result_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_execution_records_published_result_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "published_result_id")
    op.drop_table("annotations")
    op.drop_table("published_results")
    op.drop_constraint("ck_pipeline_jobs_stage", "pipeline_jobs", type_="check")
    op.create_check_constraint(
        "ck_pipeline_jobs_stage",
        "pipeline_jobs",
        "stage IN ("
        "'PAGE_NORMALIZATION','IDENTITY','MAPPING','TRANSCRIPTION','EVALUATION')",
    )
