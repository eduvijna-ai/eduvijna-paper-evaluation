"""b20_multisubject_multilingual

Revision ID: 20260918_0022
Revises: 20260917_0021
Create Date: 2026-09-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0022"
down_revision: str | None = "20260917_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("language_code", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "submissions",
        sa.Column("script_code", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "submissions",
        sa.Column("language_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "submissions",
        sa.Column("language_confidence", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "submissions",
        sa.Column(
            "language_state",
            sa.String(length=32),
            server_default="UNKNOWN",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_submissions_language_state",
        "submissions",
        "language_state IN ('UNKNOWN','CONFIRMED','REVIEW_REQUIRED','UNSUPPORTED')",
    )
    op.create_check_constraint(
        "ck_submissions_language_source",
        "submissions",
        "language_source IS NULL OR language_source IN ('UNKNOWN','PROVIDED','DETECTED')",
    )

    op.add_column(
        "answer_region_transcriptions",
        sa.Column("language_code", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "answer_region_transcriptions",
        sa.Column("script_code", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "answer_region_transcriptions",
        sa.Column("language_source", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "transcription_derived_texts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_transcription_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_language_code", sa.String(length=32), nullable=False),
        sa.Column("target_language_code", sa.String(length=32), nullable=False),
        sa.Column("source_script_code", sa.String(length=16), nullable=True),
        sa.Column("target_script_code", sa.String(length=16), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint(
            "kind IN ('TRANSLATION','TRANSLITERATION')",
            name="ck_transcription_derived_texts_kind",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','SUPERSEDED')",
            name="ck_transcription_derived_texts_status",
        ),
        sa.ForeignKeyConstraint(
            ["ai_execution_record_id"],
            ["ai_execution_records.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_transcription_id"],
            ["answer_region_transcriptions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["transcription_derived_texts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transcription_derived_texts_tenant_source",
        "transcription_derived_texts",
        ["tenant_id", "source_transcription_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transcription_derived_texts_tenant_source",
        table_name="transcription_derived_texts",
    )
    op.drop_table("transcription_derived_texts")
    op.drop_column("answer_region_transcriptions", "language_source")
    op.drop_column("answer_region_transcriptions", "script_code")
    op.drop_column("answer_region_transcriptions", "language_code")
    op.drop_constraint("ck_submissions_language_source", "submissions", type_="check")
    op.drop_constraint("ck_submissions_language_state", "submissions", type_="check")
    op.drop_column("submissions", "language_state")
    op.drop_column("submissions", "language_confidence")
    op.drop_column("submissions", "language_source")
    op.drop_column("submissions", "script_code")
    op.drop_column("submissions", "language_code")
