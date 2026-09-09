"""b14_assessment_type_compatibility

Revision ID: 20260908_0015
Revises: 20260908_0014
Create Date: 2026-09-08 15:25:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260908_0015"
down_revision: str | None = "20260908_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove the legacy B14 assessment-type constraint when already applied.

    The corrected 0014 migration no longer creates this constraint. `IF EXISTS`
    keeps this cleanup safe for both fresh upgrades and databases that applied
    the original B14 migration before the compatibility remediation.
    """
    op.execute(
        "ALTER TABLE assessments DROP CONSTRAINT IF EXISTS "
        "ck_assessments_assessment_type"
    )


def downgrade() -> None:
    # Intentionally do not recreate the removed global restriction. The corrected
    # 0014 migration does not own such a constraint, and reintroducing it could
    # make otherwise-valid institution assessment types fail on rollback.
    pass
