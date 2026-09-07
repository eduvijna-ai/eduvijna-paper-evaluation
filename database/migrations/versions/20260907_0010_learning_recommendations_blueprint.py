"""learning_recommendations_blueprint

Revision ID: 20260907_0010
Revises: 20260907_0009
Create Date: 2026-09-07 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0010"
down_revision: str | None = "20260907_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_plan_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("curriculum_graph_hash", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "algorithm_version",
            sa.String(length=32),
            server_default="B9_V1",
            nullable=False,
        ),
        sa.Column("generation_source", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_id",
            "version_number",
            name="uq_learning_plan_runs_version",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_id",
            "input_hash",
            "algorithm_version",
            name="uq_learning_plan_runs_input_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','READY','FAILED','SUPERSEDED')",
            name="ck_learning_plan_runs_status",
        ),
        sa.CheckConstraint(
            "generation_source IS NULL OR generation_source IN "
            "('AI','FIXED','RULES_FALLBACK')",
            name="ck_learning_plan_runs_generation_source",
        ),
    )
    op.create_index(
        "ix_learning_plan_runs_tenant_student_curriculum",
        "learning_plan_runs",
        ["tenant_id", "student_id", "curriculum_id"],
    )
    op.create_index(
        "ix_learning_plan_runs_tenant_status",
        "learning_plan_runs",
        ["tenant_id", "status"],
    )

    op.create_table(
        "learning_recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("learning_plan_run_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_kind", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("concept_signal", sa.String(length=32), nullable=False),
        sa.Column("execution_signal", sa.String(length=32), nullable=False),
        sa.Column("procedure_signal", sa.String(length=32), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("mean_evidence_score_ratio", sa.Numeric(10, 6), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("target_node_code_snapshot", sa.String(length=100), nullable=False),
        sa.Column("target_node_title_snapshot", sa.String(length=255), nullable=False),
        sa.Column("target_node_type_snapshot", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["learning_plan_run_id"],
            ["learning_plan_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["target_node_id"], ["curriculum_nodes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "recommendation_kind IN ("
            "'PREREQUISITE_REPAIR','TARGET_CONCEPT',"
            "'PROCEDURE_PRACTICE','EXECUTION_PRACTICE')",
            name="ck_learning_recommendations_kind",
        ),
        sa.CheckConstraint(
            "priority IN (1, 2, 3)",
            name="ck_learning_recommendations_priority",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','DISMISSED','COMPLETED')",
            name="ck_learning_recommendations_status",
        ),
        sa.CheckConstraint(
            "concept_signal IN ('STRONG','WEAK','INCONCLUSIVE')",
            name="ck_learning_recommendations_concept_signal",
        ),
        sa.CheckConstraint(
            "execution_signal IN ('STRONG','WEAK','INCONCLUSIVE')",
            name="ck_learning_recommendations_execution_signal",
        ),
        sa.CheckConstraint(
            "procedure_signal IN ('STRONG','WEAK','INCONCLUSIVE')",
            name="ck_learning_recommendations_procedure_signal",
        ),
    )
    op.create_index(
        "ix_learning_recommendations_tenant_run",
        "learning_recommendations",
        ["tenant_id", "learning_plan_run_id"],
    )
    op.create_index(
        "ix_learning_recommendations_tenant_student_curriculum",
        "learning_recommendations",
        ["tenant_id", "student_id", "curriculum_id"],
    )
    op.create_index(
        "ix_learning_recommendations_tenant_target_node",
        "learning_recommendations",
        ["tenant_id", "target_node_id"],
    )

    op.create_table(
        "learning_recommendation_prerequisites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("learning_recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"],
            ["curriculum_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learning_recommendation_id"],
            ["learning_recommendations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_recommendation_id",
            "curriculum_node_id",
            "relationship_type",
            name="uq_learning_recommendation_prerequisites_edge",
        ),
        sa.CheckConstraint(
            "relationship_type IN ('REQUIRED','RECOMMENDED')",
            name="ck_learning_recommendation_prerequisites_type",
        ),
    )
    op.create_index(
        "ix_learning_rec_prereq_tenant_rec",
        "learning_recommendation_prerequisites",
        ["tenant_id", "learning_recommendation_id"],
    )

    op.create_table(
        "learning_recommendation_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("learning_recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("mastery_evidence_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["learning_recommendation_id"],
            ["learning_recommendations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mastery_evidence_id"],
            ["mastery_evidence.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_recommendation_id",
            "mastery_evidence_id",
            name="uq_learning_recommendation_evidence",
        ),
    )
    op.create_index(
        "ix_learning_rec_evidence_tenant_rec",
        "learning_recommendation_evidence",
        ["tenant_id", "learning_recommendation_id"],
    )
    op.create_index(
        "ix_learning_rec_evidence_tenant_mastery",
        "learning_recommendation_evidence",
        ["tenant_id", "mastery_evidence_id"],
    )

    op.create_table(
        "learning_path_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("learning_plan_run_id", sa.Uuid(), nullable=False),
        sa.Column("learning_recommendation_id", sa.Uuid(), nullable=True),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence_basis", sa.String(length=64), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"],
            ["curriculum_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learning_plan_run_id"],
            ["learning_plan_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learning_recommendation_id"],
            ["learning_recommendations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learning_plan_run_id",
            "sequence",
            name="uq_learning_path_steps_sequence",
        ),
        sa.CheckConstraint(
            "kind IN ("
            "'PREREQUISITE','LEARN','GUIDED','INDEPENDENT','MASTERY_CHECK')",
            name="ck_learning_path_steps_kind",
        ),
        sa.CheckConstraint(
            "relationship_type IS NULL OR relationship_type IN "
            "('REQUIRED','RECOMMENDED')",
            name="ck_learning_path_steps_relationship",
        ),
    )
    op.create_index(
        "ix_learning_path_steps_tenant_run",
        "learning_path_steps",
        ["tenant_id", "learning_plan_run_id"],
    )

    op.create_table(
        "improvement_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("learning_plan_run_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("curriculum_graph_hash", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("generation_source", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("blueprint_storage_key", sa.String(length=512), nullable=True),
        sa.Column("blueprint_sha256", sa.String(length=64), nullable=True),
        sa.Column("blueprint_byte_size", sa.BigInteger(), nullable=True),
        sa.Column("generated_by", sa.Uuid(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.Uuid(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["learning_plan_run_id"],
            ["learning_plan_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "learning_plan_run_id",
            "version_number",
            name="uq_improvement_assessments_version",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'DRAFT','GENERATING','PENDING_APPROVAL',"
            "'APPROVED','REJECTED','FAILED')",
            name="ck_improvement_assessments_status",
        ),
        sa.CheckConstraint(
            "generation_source IS NULL OR generation_source IN "
            "('AI','FIXED','RULES_FALLBACK')",
            name="ck_improvement_assessments_generation_source",
        ),
    )
    op.create_index(
        "ix_improvement_assessments_tenant_run",
        "improvement_assessments",
        ["tenant_id", "learning_plan_run_id"],
    )
    op.create_index(
        "ix_improvement_assessments_tenant_student_curriculum",
        "improvement_assessments",
        ["tenant_id", "student_id", "curriculum_id"],
    )
    op.create_index(
        "ix_improvement_assessments_tenant_status",
        "improvement_assessments",
        ["tenant_id", "status"],
    )

    op.create_table(
        "improvement_assessment_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("improvement_assessment_id", sa.Uuid(), nullable=False),
        sa.Column("learning_recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_node_id", sa.Uuid(), nullable=False),
        sa.Column("item_code", sa.String(length=100), nullable=False),
        sa.Column("template_kind", sa.String(length=64), nullable=False),
        sa.Column("question_template_ref", sa.String(length=255), nullable=False),
        sa.Column("focus", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("suggested_marks", sa.Numeric(10, 4), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_node_id"],
            ["curriculum_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["improvement_assessment_id"],
            ["improvement_assessments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learning_recommendation_id"],
            ["learning_recommendations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "improvement_assessment_id",
            "item_code",
            name="uq_improvement_assessment_items_code",
        ),
        sa.CheckConstraint(
            "template_kind IN ("
            "'CONCEPT_CHECK','PREREQUISITE_CHECK',"
            "'PROCEDURE_PRACTICE','EXECUTION_PRACTICE','TRANSFER_CHECK')",
            name="ck_improvement_assessment_items_template_kind",
        ),
        sa.CheckConstraint(
            "difficulty IN ('EASY','MEDIUM','HARD')",
            name="ck_improvement_assessment_items_difficulty",
        ),
        sa.CheckConstraint(
            "suggested_marks IS NULL OR suggested_marks > 0",
            name="ck_improvement_assessment_items_suggested_marks",
        ),
    )
    op.create_index(
        "ix_improvement_assessment_items_tenant_assessment",
        "improvement_assessment_items",
        ["tenant_id", "improvement_assessment_id"],
    )

    op.add_column(
        "ai_execution_records",
        sa.Column("learning_plan_run_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_learning_plan_run_id",
        "ai_execution_records",
        "learning_plan_runs",
        ["learning_plan_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "ai_execution_records",
        sa.Column("improvement_assessment_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_execution_records_improvement_assessment_id",
        "ai_execution_records",
        "improvement_assessments",
        ["improvement_assessment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_execution_records_improvement_assessment_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "improvement_assessment_id")
    op.drop_constraint(
        "fk_ai_execution_records_learning_plan_run_id",
        "ai_execution_records",
        type_="foreignkey",
    )
    op.drop_column("ai_execution_records", "learning_plan_run_id")

    op.drop_index(
        "ix_improvement_assessment_items_tenant_assessment",
        table_name="improvement_assessment_items",
    )
    op.drop_table("improvement_assessment_items")

    op.drop_index(
        "ix_improvement_assessments_tenant_status",
        table_name="improvement_assessments",
    )
    op.drop_index(
        "ix_improvement_assessments_tenant_student_curriculum",
        table_name="improvement_assessments",
    )
    op.drop_index(
        "ix_improvement_assessments_tenant_run",
        table_name="improvement_assessments",
    )
    op.drop_table("improvement_assessments")

    op.drop_index(
        "ix_learning_path_steps_tenant_run", table_name="learning_path_steps"
    )
    op.drop_table("learning_path_steps")

    op.drop_index(
        "ix_learning_rec_evidence_tenant_mastery",
        table_name="learning_recommendation_evidence",
    )
    op.drop_index(
        "ix_learning_rec_evidence_tenant_rec",
        table_name="learning_recommendation_evidence",
    )
    op.drop_table("learning_recommendation_evidence")

    op.drop_index(
        "ix_learning_rec_prereq_tenant_rec",
        table_name="learning_recommendation_prerequisites",
    )
    op.drop_table("learning_recommendation_prerequisites")

    op.drop_index(
        "ix_learning_recommendations_tenant_target_node",
        table_name="learning_recommendations",
    )
    op.drop_index(
        "ix_learning_recommendations_tenant_student_curriculum",
        table_name="learning_recommendations",
    )
    op.drop_index(
        "ix_learning_recommendations_tenant_run",
        table_name="learning_recommendations",
    )
    op.drop_table("learning_recommendations")

    op.drop_index(
        "ix_learning_plan_runs_tenant_status", table_name="learning_plan_runs"
    )
    op.drop_index(
        "ix_learning_plan_runs_tenant_student_curriculum",
        table_name="learning_plan_runs",
    )
    op.drop_table("learning_plan_runs")
