import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Student(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("tenant_id", "institution_id", "student_code", name="uq_students_code"),
        Index(
            "uq_students_class_roll",
            "tenant_id",
            "class_section_id",
            "roll_number",
            unique=True,
            postgresql_where=text("roll_number IS NOT NULL"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE")
    )
    class_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("academic_years.id", ondelete="RESTRICT"), nullable=True
    )
    student_code: Mapped[str] = mapped_column(String(100))
    admission_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    roll_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")


class Guardian(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "guardians"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    display_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)


class StudentGuardian(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "student_guardians"
    __table_args__ = (
        UniqueConstraint("student_id", "guardian_id", name="uq_student_guardians_pair"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    guardian_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guardians.id", ondelete="CASCADE"))
    relationship_type: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ImportSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_sessions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE")
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(32))
    row_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    valid_row_count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
