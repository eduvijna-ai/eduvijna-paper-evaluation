"""b16_enterprise_grading_moderation_grievance

Revision ID: 20260909_0017
Revises: 20260909_0016
Create Date: 2026-09-09 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0017"
down_revision: str | None = "20260909_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_submissions_workflow_state", "submissions", type_="check")
    op.create_check_constraint(
        "ck_submissions_workflow_state",
        "submissions",
        "workflow_state IN ("
        "'UPLOADED','PROCESSING','IDENTITY_REVIEW','MAPPING_REVIEW',"
        "'READY_FOR_EVALUATION','EVALUATING','EVALUATION_REVIEW',"
        "'MODERATION_REVIEW',"
        "'APPROVED','PUBLISHED','FAILED')",
    )

    op.drop_constraint("ck_published_results_status", "published_results", type_="check")
    op.create_check_constraint(
        "ck_published_results_status",
        "published_results",
        "status IN ('READY','GENERATING','GENERATED','PUBLISHED','FAILED','SUPERSEDED')",
    )

    op.create_table(
        "grading_pools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("grading_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("allocation_strategy", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("activated_by", sa.Uuid(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
            "grading_mode IN ('HORIZONTAL_QUESTION')",
            name="ck_grading_pools_mode",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','CLOSED')",
            name="ck_grading_pools_status",
        ),
        sa.CheckConstraint(
            "allocation_strategy IN ('MANUAL','ROUND_ROBIN')",
            name="ck_grading_pools_allocation",
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"], ["assessment_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["activated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grading_pools_tenant", "grading_pools", ["tenant_id"])
    op.create_index(
        "ix_grading_pools_tenant_assessment_version",
        "grading_pools",
        ["tenant_id", "assessment_version_id"],
    )

    op.create_table(
        "grading_pool_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("pool_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["pool_id"], ["grading_pools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "pool_id", "user_id", name="uq_grading_pool_members_tenant_pool_user"
        ),
    )
    op.create_index(
        "ix_grading_pool_members_tenant_pool",
        "grading_pool_members",
        ["tenant_id", "pool_id"],
    )

    op.create_table(
        "grading_work_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("pool_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("question_evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_evaluator_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('QUEUED','IN_PROGRESS','SUBMITTED','RETURNED','COMPLETED')",
            name="ck_grading_work_items_status",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_evaluator_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["pool_id"], ["grading_pools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["question_evaluation_id"],
            ["question_evaluations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grading_work_items_tenant_pool",
        "grading_work_items",
        ["tenant_id", "pool_id"],
    )
    op.create_index(
        "ix_grading_work_items_tenant_evaluator",
        "grading_work_items",
        ["tenant_id", "assigned_evaluator_id"],
    )
    op.create_index(
        "ix_grading_work_items_tenant_submission",
        "grading_work_items",
        ["tenant_id", "submission_id"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_grading_work_items_active_qe
        ON grading_work_items (tenant_id, question_evaluation_id)
        WHERE status IN ('QUEUED', 'IN_PROGRESS', 'SUBMITTED')
        """
    )

    op.create_table(
        "moderation_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("activated_by", sa.Uuid(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('DRAFT','ACTIVE','RETIRED')",
            name="ck_moderation_policies_status",
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"], ["assessment_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["activated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_moderation_policies_tenant", "moderation_policies", ["tenant_id"])
    op.create_index(
        "ix_moderation_policies_tenant_av",
        "moderation_policies",
        ["tenant_id", "assessment_version_id"],
    )

    op.create_table(
        "moderation_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("required_role", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
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
            "required_role IN ("
            "'MODERATOR','HOD','ACADEMIC_COORDINATOR','EXAM_CONTROLLER','INSTITUTION_ADMIN')",
            name="ck_moderation_stages_role",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["moderation_policies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_id", "stage_order", name="uq_moderation_stages_policy_order"
        ),
    )
    op.create_index(
        "ix_moderation_stages_tenant_policy",
        "moderation_stages",
        ["tenant_id", "policy_id"],
    )

    op.create_table(
        "moderation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("current_stage_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
            "status IN ('PENDING','IN_PROGRESS','APPROVED','RETURNED','REJECTED')",
            name="ck_moderation_cases_status",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["moderation_policies.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_moderation_cases_tenant_status",
        "moderation_cases",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_moderation_cases_tenant_submission",
        "moderation_cases",
        ["tenant_id", "submission_id"],
    )

    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVE','RETURN','REJECT')",
            name="ck_moderation_actions_decision",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["case_id"], ["moderation_cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_moderation_actions_tenant_case",
        "moderation_actions",
        ["tenant_id", "case_id"],
    )

    op.create_table(
        "grievance_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("original_published_result_id", sa.Uuid(), nullable=False),
        sa.Column("original_evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("requester_reference", sa.String(length=255), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decision_by", sa.Uuid(), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("reevaluation_run_id", sa.Uuid(), nullable=True),
        sa.Column("revised_published_result_id", sa.Uuid(), nullable=True),
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
            "status IN ("
            "'SUBMITTED','UNDER_REVIEW','ACCEPTED','REJECTED',"
            "'RE_EVALUATING','RESOLVED','CLOSED')",
            name="ck_grievance_cases_status",
        ),
        sa.ForeignKeyConstraint(
            ["decision_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["original_evaluation_run_id"],
            ["evaluation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["original_published_result_id"],
            ["published_results.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revised_published_result_id"],
            ["published_results.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grievance_cases_tenant", "grievance_cases", ["tenant_id"])
    op.create_index(
        "ix_grievance_cases_tenant_submission",
        "grievance_cases",
        ["tenant_id", "submission_id"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_grievance_cases_active_result
        ON grievance_cases (tenant_id, original_published_result_id)
        WHERE status IN ('SUBMITTED', 'UNDER_REVIEW', 'ACCEPTED', 'RE_EVALUATING')
        """
    )

    op.add_column(
        "evaluation_runs",
        sa.Column(
            "run_kind",
            sa.String(length=32),
            server_default="INITIAL",
            nullable=False,
        ),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("supersedes_run_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("grievance_case_id", sa.Uuid(), nullable=True),
    )
    op.create_check_constraint(
        "ck_evaluation_runs_run_kind",
        "evaluation_runs",
        "run_kind IN ('INITIAL','RE_EVALUATION')",
    )
    op.create_foreign_key(
        "fk_evaluation_runs_supersedes_run_id",
        "evaluation_runs",
        "evaluation_runs",
        ["supersedes_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evaluation_runs_grievance_case_id",
        "evaluation_runs",
        "grievance_cases",
        ["grievance_case_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_grievance_cases_reevaluation_run_id",
        "grievance_cases",
        "evaluation_runs",
        ["reevaluation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_grievance_cases_reevaluation_run_id",
        "grievance_cases",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_runs_grievance_case_id",
        "evaluation_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_runs_supersedes_run_id",
        "evaluation_runs",
        type_="foreignkey",
    )
    op.drop_constraint("ck_evaluation_runs_run_kind", "evaluation_runs", type_="check")
    op.drop_column("evaluation_runs", "grievance_case_id")
    op.drop_column("evaluation_runs", "supersedes_run_id")
    op.drop_column("evaluation_runs", "run_kind")

    op.execute("DROP INDEX IF EXISTS uq_grievance_cases_active_result")
    op.drop_table("grievance_cases")
    op.drop_table("moderation_actions")
    op.drop_table("moderation_cases")
    op.drop_table("moderation_stages")
    op.drop_table("moderation_policies")
    op.execute("DROP INDEX IF EXISTS uq_grading_work_items_active_qe")
    op.drop_table("grading_work_items")
    op.drop_table("grading_pool_members")
    op.drop_table("grading_pools")

    op.drop_constraint("ck_published_results_status", "published_results", type_="check")
    op.create_check_constraint(
        "ck_published_results_status",
        "published_results",
        "status IN ('READY','GENERATING','GENERATED','PUBLISHED','FAILED')",
    )

    op.drop_constraint("ck_submissions_workflow_state", "submissions", type_="check")
    op.create_check_constraint(
        "ck_submissions_workflow_state",
        "submissions",
        "workflow_state IN ("
        "'UPLOADED','PROCESSING','IDENTITY_REVIEW','MAPPING_REVIEW',"
        "'READY_FOR_EVALUATION','EVALUATING','EVALUATION_REVIEW',"
        "'APPROVED','PUBLISHED','FAILED')",
    )
