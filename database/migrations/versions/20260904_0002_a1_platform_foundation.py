"""A1 tenant platform foundation.

Revision ID: 20260904_0002
Revises: 20260904_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260904_0002"
down_revision: str | None = "20260904_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("roles", sa.Column("code", sa.String(100), nullable=True))
    op.add_column(
        "roles", sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.execute(
        "UPDATE roles SET code = upper(regexp_replace(trim(name), '[^a-zA-Z0-9]+', '_', 'g'))"
    )
    op.alter_column("roles", "code", nullable=False)
    op.drop_index("uq_roles_tenant_name", table_name="roles")
    op.drop_index("uq_roles_system_name", table_name="roles")
    op.create_index(
        "uq_roles_tenant_code",
        "roles",
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_roles_system_code",
        "roles",
        ["code"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "role_id", sa.Uuid(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "permission_id",
            sa.Uuid(),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_pair"),
    )

    op.add_column(
        "academic_years",
        sa.Column("is_current", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("students", sa.Column("student_code", sa.String(100), nullable=True))
    op.add_column("students", sa.Column("admission_number", sa.String(100), nullable=True))
    op.add_column("students", sa.Column("roll_number", sa.String(100), nullable=True))
    op.add_column("students", sa.Column("full_name", sa.String(255), nullable=True))
    op.add_column(
        "students",
        sa.Column(
            "academic_year_id",
            sa.Uuid(),
            sa.ForeignKey("academic_years.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.execute("UPDATE students SET student_code = student_identifier, full_name = display_name")
    op.alter_column("students", "student_code", nullable=False)
    op.alter_column("students", "full_name", nullable=False)
    op.drop_constraint("uq_students_scope_identifier", "students", type_="unique")
    op.drop_column("students", "student_identifier")
    op.drop_column("students", "display_name")
    op.create_unique_constraint(
        "uq_students_code", "students", ["tenant_id", "institution_id", "student_code"]
    )
    op.create_index(
        "uq_students_class_roll",
        "students",
        ["tenant_id", "class_section_id", "roll_number"],
        unique=True,
        postgresql_where=sa.text("roll_number IS NOT NULL"),
    )

    op.create_table(
        "import_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "institution_id",
            sa.Uuid(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("row_results", postgresql.JSONB(), nullable=False),
        sa.Column("valid_row_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_import_sessions_tenant_hash", "import_sessions", ["tenant_id", "content_hash"]
    )


def downgrade() -> None:
    op.drop_table("import_sessions")
    op.drop_index("uq_students_class_roll", table_name="students")
    op.drop_constraint("uq_students_code", "students", type_="unique")
    op.add_column("students", sa.Column("display_name", sa.String(255), nullable=True))
    op.add_column("students", sa.Column("student_identifier", sa.String(100), nullable=True))
    op.execute("UPDATE students SET student_identifier = student_code, display_name = full_name")
    op.alter_column("students", "student_identifier", nullable=False)
    op.alter_column("students", "display_name", nullable=False)
    op.create_unique_constraint(
        "uq_students_scope_identifier",
        "students",
        ["tenant_id", "institution_id", "student_identifier"],
    )
    op.drop_column("students", "academic_year_id")
    op.drop_column("students", "full_name")
    op.drop_column("students", "roll_number")
    op.drop_column("students", "admission_number")
    op.drop_column("students", "student_code")
    op.drop_column("academic_years", "is_current")
    op.drop_table("role_permissions")
    op.drop_index("uq_roles_system_code", table_name="roles")
    op.drop_index("uq_roles_tenant_code", table_name="roles")
    op.create_index(
        "uq_roles_tenant_name",
        "roles",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )
    op.create_index(
        "uq_roles_system_name",
        "roles",
        ["name"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )
    op.drop_column("roles", "is_system")
    op.drop_column("roles", "code")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "password_hash")
