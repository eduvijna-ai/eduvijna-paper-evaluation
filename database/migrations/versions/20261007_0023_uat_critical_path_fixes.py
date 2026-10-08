"""uat critical path: class-section grade uniqueness + ANY_N selection semantics

Revision ID: 20261007_0023
Revises: 20260918_0022
Create Date: 2026-10-07 08:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0023"
down_revision: str | None = "20260918_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_class_sections_scope_name", "class_sections", type_="unique")
    op.create_unique_constraint(
        "uq_class_sections_scope_grade_name",
        "class_sections",
        ["tenant_id", "academic_year_id", "grade_label", "name"],
    )

    op.add_column(
        "question_versions",
        sa.Column(
            "selection_mode",
            sa.String(length=16),
            nullable=False,
            server_default="ALL",
        ),
    )
    op.add_column(
        "question_versions",
        sa.Column("selection_count", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_question_versions_selection_mode",
        "question_versions",
        "selection_mode IN ('ALL','ANY_N')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_question_versions_selection_mode", "question_versions", type_="check")
    op.drop_column("question_versions", "selection_count")
    op.drop_column("question_versions", "selection_mode")

    op.drop_constraint("uq_class_sections_scope_grade_name", "class_sections", type_="unique")
    op.create_unique_constraint(
        "uq_class_sections_scope_name",
        "class_sections",
        ["tenant_id", "academic_year_id", "name"],
    )
