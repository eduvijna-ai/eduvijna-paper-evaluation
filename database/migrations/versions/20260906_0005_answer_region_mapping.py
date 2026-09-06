"""answer_region_mapping

Revision ID: 20260906_0005
Revises: 20260906_0004
Create Date: 2026-09-06 20:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0005"
down_revision: str | None = "20260906_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "answer_regions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_page_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("bbox_x", sa.Numeric(8, 6), nullable=False),
        sa.Column("bbox_y", sa.Numeric(8, 6), nullable=False),
        sa.Column("bbox_width", sa.Numeric(8, 6), nullable=False),
        sa.Column("bbox_height", sa.Numeric(8, 6), nullable=False),
        sa.Column("region_type", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column(
            "detection_confidence",
            sa.Numeric(5, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("crossed_out", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ignored", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_continuation", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("transcription", sa.Text(), nullable=True),
        sa.Column(
            "transcription_confidence",
            sa.Numeric(5, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
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
            "region_type IN ('ANSWER','SCRATCH','DIAGRAM','IDENTITY')",
            name="ck_answer_regions_region_type",
        ),
        sa.CheckConstraint(
            "source_type IN ('HUMAN','AI')",
            name="ck_answer_regions_source_type",
        ),
        sa.CheckConstraint(
            "bbox_x >= 0 AND bbox_y >= 0 AND bbox_width > 0 AND bbox_height > 0 "
            "AND bbox_x + bbox_width <= 1 AND bbox_y + bbox_height <= 1",
            name="ck_answer_regions_bbox_normalized",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["submission_page_id"], ["submission_pages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_answer_regions_tenant_page",
        "answer_regions",
        ["tenant_id", "submission_page_id"],
    )

    op.create_table(
        "question_answer_mappings",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("question_version_id", sa.Uuid(), nullable=False),
        sa.Column("disposition", sa.String(length=16), nullable=False),
        sa.Column("mapping_state", sa.String(length=32), nullable=False),
        sa.Column(
            "mapping_confidence",
            sa.Numeric(5, 4),
            server_default="0.0000",
            nullable=False,
        ),
        sa.Column("mapped_by", sa.String(length=16), nullable=False),
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
            "disposition IN ('ANSWERED','BLANK')",
            name="ck_question_answer_mappings_disposition",
        ),
        sa.CheckConstraint(
            "mapping_state IN ('PROPOSED','REVIEW_REQUIRED','CONFIRMED')",
            name="ck_question_answer_mappings_state",
        ),
        sa.CheckConstraint(
            "mapped_by IN ('HUMAN','AI')",
            name="ck_question_answer_mappings_mapped_by",
        ),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["question_version_id"], ["question_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "submission_id",
            "question_version_id",
            name="uq_qam_tenant_submission_qv",
        ),
    )
    op.create_index(
        "ix_qam_tenant_submission",
        "question_answer_mappings",
        ["tenant_id", "submission_id"],
    )

    op.create_table(
        "question_answer_mapping_regions",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_id", sa.Uuid(), nullable=False),
        sa.Column("answer_region_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["answer_region_id"], ["answer_regions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["mapping_id"], ["question_answer_mappings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "answer_region_id",
            name="uq_qamr_tenant_region",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "mapping_id",
            "answer_region_id",
            name="uq_qamr_tenant_mapping_region",
        ),
    )
    op.create_index(
        "ix_qamr_tenant_mapping",
        "question_answer_mapping_regions",
        ["tenant_id", "mapping_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_qamr_tenant_mapping", table_name="question_answer_mapping_regions")
    op.drop_table("question_answer_mapping_regions")
    op.drop_index("ix_qam_tenant_submission", table_name="question_answer_mappings")
    op.drop_table("question_answer_mappings")
    op.drop_index("ix_answer_regions_tenant_page", table_name="answer_regions")
    op.drop_table("answer_regions")
