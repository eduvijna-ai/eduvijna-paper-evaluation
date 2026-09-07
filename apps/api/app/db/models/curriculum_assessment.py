import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Curriculum(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "curricula"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_curricula_tenant_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    academic_framework: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version_label: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")


class CurriculumNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "curriculum_nodes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "curriculum_id", "code", name="uq_curriculum_nodes_scope_code"
        ),
        Index("ix_curriculum_nodes_tree", "tenant_id", "curriculum_id", "parent_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    curriculum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("curricula.id", ondelete="CASCADE"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT"), nullable=True
    )
    node_type: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")


class CurriculumPrerequisite(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "curriculum_prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_id",
            "prerequisite_node_id",
            "dependent_node_id",
            name="uq_curriculum_prerequisites_edge",
        ),
        CheckConstraint(
            "prerequisite_node_id <> dependent_node_id",
            name="ck_curriculum_prerequisites_not_self",
        ),
        CheckConstraint(
            "relationship_type IN ('REQUIRED', 'RECOMMENDED')",
            name="ck_curriculum_prerequisites_type",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    curriculum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("curricula.id", ondelete="CASCADE"))
    prerequisite_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="CASCADE")
    )
    dependent_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="CASCADE")
    )
    relationship_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_assessments_tenant_code"),
        CheckConstraint(
            "status IN ('DRAFT','RUBRIC_REVIEW','READY','ACTIVE','CLOSED','ARCHIVED')",
            name="ck_assessments_status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True
    )
    class_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curricula.id", ondelete="RESTRICT")
    )
    subject_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_type: Mapped[str] = mapped_column(String(64))
    max_marks: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", server_default="DRAFT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class AssessmentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_versions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "version_number", name="uq_assessment_versions_number"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    question_paper_artifact_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", server_default="DRAFT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "assessment_id", "stable_code", name="uq_questions_stable_code"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE")
    )
    stable_code: Mapped[str] = mapped_column(String(100))


class QuestionVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_versions"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id", "question_id", name="uq_question_versions_identity"
        ),
        Index(
            "ix_question_versions_tree",
            "tenant_id",
            "assessment_version_id",
            "parent_question_version_id",
        ),
        CheckConstraint(
            "scoring_mode IN ('LEAF_SCORABLE','CONTAINER_DERIVED')",
            name="ck_question_versions_scoring_mode",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="CASCADE")
    )
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    parent_question_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=True
    )
    display_label: Mapped[str] = mapped_column(String(100))
    sequence: Mapped[int] = mapped_column(Integer)
    prompt_text: Mapped[str] = mapped_column(Text)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    question_type: Mapped[str] = mapped_column(String(64))
    scoring_mode: Mapped[str] = mapped_column(String(32))
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuestionCurriculumMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_curriculum_mappings"
    __table_args__ = (
        UniqueConstraint(
            "question_version_id",
            "curriculum_node_id",
            "mapping_type",
            name="uq_question_curriculum_mappings_identity",
        ),
        CheckConstraint(
            "mapping_type IN ('PRIMARY','SECONDARY','LEARNING_OUTCOME','SKILL')",
            name="ck_question_curriculum_mappings_type",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="CASCADE")
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_nodes.id", ondelete="CASCADE")
    )
    mapping_type: Mapped[str] = mapped_column(String(32))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)


class AnswerKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_keys"
    __table_args__ = (UniqueConstraint("assessment_id", name="uq_answer_keys_assessment"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE")
    )


class AnswerKeyVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answer_key_versions"
    __table_args__ = (
        UniqueConstraint("answer_key_id", "version_number", name="uq_answer_key_versions_number"),
        Index(
            "uq_answer_key_versions_active_question",
            "answer_key_id",
            "question_version_id",
            unique=True,
            postgresql_where="status IN ('DRAFT', 'REVIEW_REQUIRED', 'APPROVED')",
        ),
        CheckConstraint(
            "source_type IN ('TEACHER','AI_PROPOSED','IMPORTED')",
            name="ck_answer_key_versions_source",
        ),
        CheckConstraint(
            "status IN ('DRAFT','REVIEW_REQUIRED','APPROVED','SUPERSEDED')",
            name="ck_answer_key_versions_status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    answer_key_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answer_keys.id", ondelete="CASCADE")
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_versions.id", ondelete="CASCADE")
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="CASCADE")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    answer_text: Mapped[str] = mapped_column(Text)
    structured_answer: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", server_default="DRAFT")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Rubric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rubrics"
    __table_args__ = (
        UniqueConstraint("assessment_id", "question_version_id", name="uq_rubrics_question"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE")
    )
    question_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255))
    provenance: Mapped[str] = mapped_column(String(64))


class RubricVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rubric_versions"
    __table_args__ = (
        UniqueConstraint("rubric_id", "version_number", name="uq_rubric_versions_number"),
        Index(
            "uq_rubric_versions_active_question",
            "rubric_id",
            "question_version_id",
            unique=True,
            postgresql_where="status IN ('DRAFT', 'REVIEW_REQUIRED', 'APPROVED')",
        ),
        CheckConstraint(
            "status IN ('DRAFT','REVIEW_REQUIRED','APPROVED','SUPERSEDED')",
            name="ck_rubric_versions_status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    rubric_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rubrics.id", ondelete="CASCADE"))
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="CASCADE")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", server_default="DRAFT")
    source_type: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RubricCriterion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rubric_criteria"
    __table_args__ = (
        UniqueConstraint("rubric_version_id", "criterion_code", name="uq_rubric_criteria_code"),
        CheckConstraint(
            "scoring_mode IN ('ADDITIVE','DEDUCTIVE','ALL_OR_NOTHING')",
            name="ck_rubric_criteria_scoring_mode",
        ),
        CheckConstraint(
            "ecf_policy IN ('NONE','ALLOW_METHOD_CREDIT','CUSTOM_REVIEW')",
            name="ck_rubric_criteria_ecf_policy",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    rubric_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rubric_versions.id", ondelete="CASCADE")
    )
    criterion_code: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    sequence: Mapped[int] = mapped_column(Integer)
    scoring_mode: Mapped[str] = mapped_column(String(32))
    partial_credit_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    dependency_rule: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ecf_policy: Mapped[str] = mapped_column(String(32), default="NONE")
    unit_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    precision_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_equivalents: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    teacher_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class AiExecutionRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_execution_records"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    operation: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32))
    request_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    response_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    answer_region_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("answer_regions.id", ondelete="SET NULL"), nullable=True
    )
    evaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    question_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_evaluations.id", ondelete="SET NULL"), nullable=True
    )
    published_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("published_results.id", ondelete="SET NULL"), nullable=True
    )
    learning_plan_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_plan_runs.id", ondelete="SET NULL"), nullable=True
    )
    improvement_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("improvement_assessments.id", ondelete="SET NULL"), nullable=True
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    error_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
