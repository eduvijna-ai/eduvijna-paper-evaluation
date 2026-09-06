"""submission_ingestion

Revision ID: 20260906_0004
Revises: 20260905_0003
Create Date: 2026-09-06 19:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0004"
down_revision: str | None = "20260905_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_state", sa.String(length=32), nullable=False),
        sa.Column("student_match_state", sa.String(length=32), nullable=False),
        sa.Column("roll_number_detected", sa.String(length=64), nullable=True),
        sa.Column("name_detected", sa.String(length=255), nullable=True),
        sa.Column(
            "identity_confidence",
            sa.Numeric(5, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column(
            "mapping_confidence",
            sa.Numeric(5, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("source_storage_key", sa.String(length=512), nullable=False),
        sa.Column("source_content_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_status", sa.String(length=32), nullable=False),
        sa.Column("page_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bundle_name", sa.String(length=255), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
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
            "workflow_state IN ("
            "'UPLOADED','PROCESSING','IDENTITY_REVIEW','MAPPING_REVIEW',"
            "'READY_FOR_EVALUATION','EVALUATING','EVALUATION_REVIEW',"
            "'APPROVED','PUBLISHED','FAILED')",
            name="ck_submissions_workflow_state",
        ),
        sa.CheckConstraint(
            "student_match_state IN ("
            "'UNMATCHED','REVIEW_REQUIRED','AUTO_MATCHED','CONFIRMED')",
            name="ck_submissions_student_match_state",
        ),
        sa.CheckConstraint(
            "storage_status IN ('PENDING','AVAILABLE','FAILED')",
            name="ck_submissions_storage_status",
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"], ["assessment_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "source_content_sha256",
            name="uq_submissions_tenant_assessment_hash",
        ),
    )
    op.create_index(
        "ix_submissions_tenant_assessment_workflow",
        "submissions",
        ["tenant_id", "assessment_id", "workflow_state"],
    )
    op.create_index(
        "ix_submissions_tenant_uploaded_at",
        "submissions",
        ["tenant_id", "uploaded_at"],
    )

    op.create_table(
        "submission_pages",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("image_storage_key", sa.String(length=512), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("is_continuation", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "submission_id",
            "page_index",
            name="uq_submission_pages_tenant_submission_index",
        ),
    )
    op.create_index(
        "ix_submission_pages_tenant_submission",
        "submission_pages",
        ["tenant_id", "submission_id"],
    )

    op.create_table(
        "pipeline_jobs",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            "stage IN ('PAGE_NORMALIZATION','IDENTITY','MAPPING','EVALUATION')",
            name="ck_pipeline_jobs_stage",
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')",
            name="ck_pipeline_jobs_status",
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_pipeline_jobs_tenant_idempotency",
        ),
    )
    op.create_index(
        "ix_pipeline_jobs_tenant_submission_stage",
        "pipeline_jobs",
        ["tenant_id", "submission_id", "stage"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_jobs_tenant_submission_stage", table_name="pipeline_jobs")
    op.drop_table("pipeline_jobs")
    op.drop_index("ix_submission_pages_tenant_submission", table_name="submission_pages")
    op.drop_table("submission_pages")
    op.drop_index("ix_submissions_tenant_uploaded_at", table_name="submissions")
    op.drop_index("ix_submissions_tenant_assessment_workflow", table_name="submissions")
    op.drop_table("submissions")
