"""B16 enterprise grading, moderation, and grievance services."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EvaluationRun,
    GradingPool,
    GradingPoolMember,
    GradingWorkItem,
    GrievanceCase,
    ModerationAction,
    ModerationCase,
    ModerationPolicy,
    ModerationStage,
    PublishedResult,
    QuestionEvaluation,
    ReviewAction,
    Role,
    Submission,
    User,
    UserRole,
)
from app.services.audit import add_audit_event

ALLOWED_GRADING_MEMBER_ROLES = frozenset(
    {"EVALUATOR", "TEACHER", "INSTITUTION_ADMIN"}
)
ACTIVE_WORK_STATUSES = frozenset({"QUEUED", "IN_PROGRESS", "SUBMITTED"})
ACTIVE_GRIEVANCE_STATUSES = frozenset(
    {"SUBMITTED", "UNDER_REVIEW", "ACCEPTED", "RE_EVALUATING", "RESOLVED"}
)
MODERATION_ROLES = frozenset(
    {
        "MODERATOR",
        "HOD",
        "ACADEMIC_COORDINATOR",
        "EXAM_CONTROLLER",
        "INSTITUTION_ADMIN",
    }
)


class EnterpriseOpsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _serialize_pool(pool: GradingPool) -> dict[str, Any]:
    return {
        "id": str(pool.id),
        "tenant_id": str(pool.tenant_id),
        "assessment_id": str(pool.assessment_id),
        "assessment_version_id": str(pool.assessment_version_id),
        "grading_mode": pool.grading_mode,
        "status": pool.status,
        "allocation_strategy": pool.allocation_strategy,
        "created_by": str(pool.created_by) if pool.created_by else None,
        "activated_by": str(pool.activated_by) if pool.activated_by else None,
        "activated_at": pool.activated_at.isoformat() if pool.activated_at else None,
        "closed_by": str(pool.closed_by) if pool.closed_by else None,
        "closed_at": pool.closed_at.isoformat() if pool.closed_at else None,
        "created_at": pool.created_at.isoformat(),
        "updated_at": pool.updated_at.isoformat(),
    }


def _serialize_work(item: GradingWorkItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "tenant_id": str(item.tenant_id),
        "pool_id": str(item.pool_id),
        "submission_id": str(item.submission_id),
        "evaluation_run_id": str(item.evaluation_run_id),
        "question_evaluation_id": str(item.question_evaluation_id),
        "assigned_evaluator_id": str(item.assigned_evaluator_id),
        "status": item.status,
        "assigned_by": str(item.assigned_by) if item.assigned_by else None,
        "assigned_at": item.assigned_at.isoformat() if item.assigned_at else None,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _serialize_policy(policy: ModerationPolicy) -> dict[str, Any]:
    return {
        "id": str(policy.id),
        "tenant_id": str(policy.tenant_id),
        "assessment_id": str(policy.assessment_id),
        "assessment_version_id": str(policy.assessment_version_id),
        "status": policy.status,
        "created_by": str(policy.created_by) if policy.created_by else None,
        "activated_by": str(policy.activated_by) if policy.activated_by else None,
        "activated_at": policy.activated_at.isoformat() if policy.activated_at else None,
        "retired_by": str(policy.retired_by) if policy.retired_by else None,
        "retired_at": policy.retired_at.isoformat() if policy.retired_at else None,
        "created_at": policy.created_at.isoformat(),
        "updated_at": policy.updated_at.isoformat(),
    }


def _serialize_case(case: ModerationCase) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "tenant_id": str(case.tenant_id),
        "policy_id": str(case.policy_id),
        "submission_id": str(case.submission_id),
        "evaluation_run_id": str(case.evaluation_run_id),
        "current_stage_order": case.current_stage_order,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
    }


def _serialize_grievance(case: GrievanceCase) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "tenant_id": str(case.tenant_id),
        "submission_id": str(case.submission_id),
        "original_published_result_id": str(case.original_published_result_id),
        "original_evaluation_run_id": str(case.original_evaluation_run_id),
        "requester_reference": case.requester_reference,
        "submitted_by": str(case.submitted_by),
        "reason": case.reason,
        "status": case.status,
        "decision_by": str(case.decision_by) if case.decision_by else None,
        "decision_at": case.decision_at.isoformat() if case.decision_at else None,
        "decision_reason": case.decision_reason,
        "reevaluation_run_id": (
            str(case.reevaluation_run_id) if case.reevaluation_run_id else None
        ),
        "revised_published_result_id": (
            str(case.revised_published_result_id)
            if case.revised_published_result_id
            else None
        ),
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
    }


async def _user_roles(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> set[str]:
    rows = await db.scalars(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.tenant_id == tenant_id, UserRole.user_id == user_id)
    )
    return set(rows.all())


async def active_moderation_policy(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
) -> ModerationPolicy | None:
    policy = await db.scalar(
        select(ModerationPolicy).where(
            ModerationPolicy.tenant_id == tenant_id,
            ModerationPolicy.assessment_version_id == assessment_version_id,
            ModerationPolicy.status == "ACTIVE",
        )
    )
    return policy if isinstance(policy, ModerationPolicy) else None


async def ensure_moderation_case_for_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    policy: ModerationPolicy,
    submission: Submission,
    run: EvaluationRun,
    actor_user_id: uuid.UUID,
) -> ModerationCase:
    existing = await db.scalar(
        select(ModerationCase).where(
            ModerationCase.tenant_id == tenant_id,
            ModerationCase.evaluation_run_id == run.id,
            ModerationCase.status.in_(["PENDING", "IN_PROGRESS", "RETURNED"]),
        )
    )
    if existing is not None:
        if existing.status == "RETURNED":
            existing.status = "PENDING"
            existing.current_stage_order = 1
        return existing

    first = await db.scalar(
        select(ModerationStage)
        .where(
            ModerationStage.tenant_id == tenant_id,
            ModerationStage.policy_id == policy.id,
        )
        .order_by(ModerationStage.stage_order.asc())
        .limit(1)
    )
    if first is None:
        raise EnterpriseOpsError(
            "MODERATION_POLICY_EMPTY",
            "Active moderation policy has no stages",
        )
    case = ModerationCase(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        policy_id=policy.id,
        submission_id=submission.id,
        evaluation_run_id=run.id,
        current_stage_order=first.stage_order,
        status="PENDING",
    )
    db.add(case)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="ModerationCase",
        entity_id=case.id,
        action="moderation_case_created",
        after=_serialize_case(case),
    )
    await db.flush()
    return case


async def create_grading_pool(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    allocation_strategy: str,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    if allocation_strategy not in {"MANUAL", "ROUND_ROBIN"}:
        raise EnterpriseOpsError("INVALID_ALLOCATION", "Unsupported allocation strategy")
    pool = GradingPool(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        assessment_id=assessment_id,
        assessment_version_id=assessment_version_id,
        grading_mode="HORIZONTAL_QUESTION",
        status="DRAFT",
        allocation_strategy=allocation_strategy,
        created_by=actor_user_id,
    )
    db.add(pool)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GradingPool",
        entity_id=pool.id,
        action="grading_pool_created",
        after=_serialize_pool(pool),
    )
    await db.flush()
    await db.refresh(pool)
    return _serialize_pool(pool)


async def add_pool_member(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    pool_id: uuid.UUID,
    user_id: uuid.UUID,
    capacity: int | None,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    pool = await _get_pool(db, tenant_id=tenant_id, pool_id=pool_id)
    if pool.status == "CLOSED":
        raise EnterpriseOpsError("POOL_CLOSED", "Cannot modify a closed pool")
    user = await db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    if user is None:
        raise EnterpriseOpsError("NOT_FOUND", "User not found")
    roles = await _user_roles(db, tenant_id=tenant_id, user_id=user_id)
    if roles.isdisjoint(ALLOWED_GRADING_MEMBER_ROLES):
        raise EnterpriseOpsError(
            "INVALID_MEMBER_ROLE",
            "User lacks an allowed evaluator/reviewer role",
        )
    existing = await db.scalar(
        select(GradingPoolMember).where(
            GradingPoolMember.tenant_id == tenant_id,
            GradingPoolMember.pool_id == pool_id,
            GradingPoolMember.user_id == user_id,
        )
    )
    if existing is not None:
        existing.is_active = True
        existing.capacity = capacity
        member = existing
    else:
        member = GradingPoolMember(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            pool_id=pool_id,
            user_id=user_id,
            is_active=True,
            capacity=capacity,
        )
        db.add(member)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GradingPoolMember",
        entity_id=member.id,
        action="grading_pool_member_added",
        after={
            "pool_id": str(pool_id),
            "user_id": str(user_id),
            "capacity": capacity,
        },
    )
    await db.flush()
    return {
        "id": str(member.id),
        "pool_id": str(pool_id),
        "user_id": str(user_id),
        "is_active": member.is_active,
        "capacity": member.capacity,
    }


async def activate_pool(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    pool_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    pool = await _get_pool(db, tenant_id=tenant_id, pool_id=pool_id)
    if pool.status != "DRAFT":
        raise EnterpriseOpsError("INVALID_POOL_STATE", "Only DRAFT pools can activate")
    members = list(
        (
            await db.scalars(
                select(GradingPoolMember).where(
                    GradingPoolMember.tenant_id == tenant_id,
                    GradingPoolMember.pool_id == pool_id,
                    GradingPoolMember.is_active.is_(True),
                )
            )
        ).all()
    )
    if not members:
        raise EnterpriseOpsError("POOL_EMPTY", "Activate requires at least one member")
    pool.status = "ACTIVE"
    pool.activated_by = actor_user_id
    pool.activated_at = datetime.now(UTC)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GradingPool",
        entity_id=pool.id,
        action="grading_pool_activated",
        after=_serialize_pool(pool),
    )
    await db.flush()
    await db.refresh(pool)
    return _serialize_pool(pool)


async def close_pool(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    pool_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    pool = await _get_pool(db, tenant_id=tenant_id, pool_id=pool_id)
    pool.status = "CLOSED"
    pool.closed_by = actor_user_id
    pool.closed_at = datetime.now(UTC)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GradingPool",
        entity_id=pool.id,
        action="grading_pool_closed",
        after=_serialize_pool(pool),
    )
    await db.flush()
    await db.refresh(pool)
    return _serialize_pool(pool)


async def allocate_work(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    pool_id: uuid.UUID,
    evaluation_run_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    pool = await _get_pool(db, tenant_id=tenant_id, pool_id=pool_id, for_update=True)
    if pool.status != "ACTIVE":
        raise EnterpriseOpsError("POOL_NOT_ACTIVE", "Pool must be ACTIVE to allocate")
    run = await db.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.id == evaluation_run_id,
            EvaluationRun.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    if run is None:
        raise EnterpriseOpsError("NOT_FOUND", "Evaluation run not found")
    if run.assessment_version_id != pool.assessment_version_id:
        raise EnterpriseOpsError(
            "ASSESSMENT_MISMATCH",
            "Run assessment version does not match pool",
        )
    members = list(
        (
            await db.scalars(
                select(GradingPoolMember)
                .where(
                    GradingPoolMember.tenant_id == tenant_id,
                    GradingPoolMember.pool_id == pool_id,
                    GradingPoolMember.is_active.is_(True),
                )
                .order_by(GradingPoolMember.user_id.asc())
            )
        ).all()
    )
    if not members:
        raise EnterpriseOpsError("POOL_EMPTY", "No active members")

    qes = list(
        (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id == run.id,
                )
            )
        ).all()
    )
    created: list[GradingWorkItem] = []
    rr_index = 0
    for qe in sorted(qes, key=lambda row: str(row.id)):
        active = await db.scalar(
            select(GradingWorkItem).where(
                GradingWorkItem.tenant_id == tenant_id,
                GradingWorkItem.question_evaluation_id == qe.id,
                GradingWorkItem.status.in_(list(ACTIVE_WORK_STATUSES)),
            )
        )
        if active is not None:
            continue
        if pool.allocation_strategy == "MANUAL":
            continue
        member = members[rr_index % len(members)]
        rr_index += 1
        item = GradingWorkItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            pool_id=pool.id,
            submission_id=run.submission_id,
            evaluation_run_id=run.id,
            question_evaluation_id=qe.id,
            assigned_evaluator_id=member.user_id,
            status="QUEUED",
            assigned_by=actor_user_id,
            assigned_at=datetime.now(UTC),
        )
        db.add(item)
        created.append(item)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GradingPool",
        entity_id=pool.id,
        action="grading_work_allocated",
        after={"created_count": len(created), "evaluation_run_id": str(run.id)},
    )
    await db.flush()
    for item in created:
        await db.refresh(item)
    return [_serialize_work(item) for item in created]


async def assign_work_manual(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    pool_id: uuid.UUID,
    question_evaluation_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    pool = await _get_pool(db, tenant_id=tenant_id, pool_id=pool_id, for_update=True)
    if pool.status != "ACTIVE":
        raise EnterpriseOpsError("POOL_NOT_ACTIVE", "Pool must be ACTIVE")
    member = await db.scalar(
        select(GradingPoolMember).where(
            GradingPoolMember.tenant_id == tenant_id,
            GradingPoolMember.pool_id == pool_id,
            GradingPoolMember.user_id == evaluator_user_id,
            GradingPoolMember.is_active.is_(True),
        )
    )
    if member is None:
        raise EnterpriseOpsError("NOT_MEMBER", "Evaluator is not an active pool member")
    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == question_evaluation_id,
            QuestionEvaluation.tenant_id == tenant_id,
        )
    )
    if qe is None:
        raise EnterpriseOpsError("NOT_FOUND", "Question evaluation not found")
    active = await db.scalar(
        select(GradingWorkItem).where(
            GradingWorkItem.tenant_id == tenant_id,
            GradingWorkItem.question_evaluation_id == qe.id,
            GradingWorkItem.status.in_(list(ACTIVE_WORK_STATUSES)),
        )
    )
    if active is not None:
        raise EnterpriseOpsError(
            "ALREADY_ASSIGNED",
            "Question evaluation already has an active work item",
        )
    item = GradingWorkItem(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        pool_id=pool.id,
        submission_id=qe.submission_id,
        evaluation_run_id=qe.evaluation_run_id,
        question_evaluation_id=qe.id,
        assigned_evaluator_id=evaluator_user_id,
        status="QUEUED",
        assigned_by=actor_user_id,
        assigned_at=datetime.now(UTC),
    )
    db.add(item)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GradingWorkItem",
        entity_id=item.id,
        action="grading_work_assigned",
        after=_serialize_work(item),
    )
    await db.flush()
    await db.refresh(item)
    return _serialize_work(item)


async def my_grading_queue(
    db: AsyncSession, *, tenant_id: uuid.UUID, evaluator_user_id: uuid.UUID
) -> list[dict[str, Any]]:
    items = list(
        (
            await db.scalars(
                select(GradingWorkItem)
                .where(
                    GradingWorkItem.tenant_id == tenant_id,
                    GradingWorkItem.assigned_evaluator_id == evaluator_user_id,
                    GradingWorkItem.status.in_(
                        ["QUEUED", "IN_PROGRESS", "RETURNED", "SUBMITTED"]
                    ),
                )
                .order_by(GradingWorkItem.created_at.asc())
            )
        ).all()
    )
    return [_serialize_work(item) for item in items]


async def start_work_item(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    work_item_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    item = await _get_work(db, tenant_id=tenant_id, work_item_id=work_item_id)
    if item.assigned_evaluator_id != actor_user_id:
        raise EnterpriseOpsError("FORBIDDEN", "Not assigned to this work item")
    if item.status not in {"QUEUED", "RETURNED"}:
        raise EnterpriseOpsError("INVALID_WORK_STATE", "Work item cannot be started")
    item.status = "IN_PROGRESS"
    item.started_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(item)
    return _serialize_work(item)


async def submit_work_item(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    work_item_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    item = await _get_work(db, tenant_id=tenant_id, work_item_id=work_item_id)
    if item.assigned_evaluator_id != actor_user_id:
        raise EnterpriseOpsError("FORBIDDEN", "Not assigned to this work item")
    if item.status not in {"IN_PROGRESS", "QUEUED", "RETURNED"}:
        raise EnterpriseOpsError("INVALID_WORK_STATE", "Work item cannot be submitted")
    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == item.question_evaluation_id,
            QuestionEvaluation.tenant_id == tenant_id,
        )
    )
    if qe is None or qe.workflow_state not in {"ACCEPTED", "OVERRIDDEN"}:
        raise EnterpriseOpsError(
            "REVIEW_INCOMPLETE",
            "QuestionEvaluation must be ACCEPTED or OVERRIDDEN before submit",
        )
    item.status = "SUBMITTED"
    item.submitted_at = datetime.now(UTC)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GradingWorkItem",
        entity_id=item.id,
        action="grading_work_submitted",
        after=_serialize_work(item),
    )
    await db.flush()
    await db.refresh(item)
    return _serialize_work(item)


async def pool_progress(
    db: AsyncSession, *, tenant_id: uuid.UUID, pool_id: uuid.UUID
) -> dict[str, Any]:
    await _get_pool(db, tenant_id=tenant_id, pool_id=pool_id)
    rows = list(
        (
            await db.execute(
                select(GradingWorkItem.status, func.count())
                .where(
                    GradingWorkItem.tenant_id == tenant_id,
                    GradingWorkItem.pool_id == pool_id,
                )
                .group_by(GradingWorkItem.status)
            )
        ).all()
    )
    counts = {
        status: 0
        for status in ["QUEUED", "IN_PROGRESS", "SUBMITTED", "RETURNED", "COMPLETED"]
    }
    for status, count in rows:
        counts[str(status)] = int(count)
    by_evaluator = list(
        (
            await db.execute(
                select(
                    GradingWorkItem.assigned_evaluator_id,
                    GradingWorkItem.status,
                    func.count(),
                )
                .where(
                    GradingWorkItem.tenant_id == tenant_id,
                    GradingWorkItem.pool_id == pool_id,
                )
                .group_by(
                    GradingWorkItem.assigned_evaluator_id,
                    GradingWorkItem.status,
                )
            )
        ).all()
    )
    return {
        "pool_id": str(pool_id),
        "total": sum(counts.values()),
        "counts": counts,
        "by_evaluator": [
            {
                "evaluator_user_id": str(uid),
                "status": status,
                "count": int(count),
            }
            for uid, status, count in by_evaluator
        ],
    }


async def create_moderation_policy(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    stages: list[dict[str, Any]],
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    if not stages:
        raise EnterpriseOpsError("MODERATION_POLICY_EMPTY", "At least one stage required")
    policy = ModerationPolicy(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        assessment_id=assessment_id,
        assessment_version_id=assessment_version_id,
        status="DRAFT",
        created_by=actor_user_id,
    )
    db.add(policy)
    await db.flush()
    for idx, stage in enumerate(stages, start=1):
        role = str(stage["required_role"])
        if role not in MODERATION_ROLES:
            raise EnterpriseOpsError("INVALID_STAGE_ROLE", f"Unsupported role {role}")
        db.add(
            ModerationStage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                policy_id=policy.id,
                stage_order=int(stage.get("stage_order", idx)),
                required_role=role,
                label=str(stage.get("label") or f"Stage {idx}"),
            )
        )
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="ModerationPolicy",
        entity_id=policy.id,
        action="moderation_policy_created",
        after=_serialize_policy(policy),
    )
    await db.flush()
    await db.refresh(policy)
    return _serialize_policy(policy)


async def activate_moderation_policy(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    policy_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    policy = await _get_policy(db, tenant_id=tenant_id, policy_id=policy_id)
    if policy.status != "DRAFT":
        raise EnterpriseOpsError("INVALID_POLICY_STATE", "Only DRAFT policies activate")
    other = await active_moderation_policy(
        db,
        tenant_id=tenant_id,
        assessment_version_id=policy.assessment_version_id,
    )
    if other is not None:
        raise EnterpriseOpsError(
            "POLICY_ACTIVE_EXISTS",
            "Another ACTIVE policy already exists for this assessment version",
        )
    stages = list(
        (
            await db.scalars(
                select(ModerationStage).where(
                    ModerationStage.tenant_id == tenant_id,
                    ModerationStage.policy_id == policy.id,
                )
            )
        ).all()
    )
    if not stages:
        raise EnterpriseOpsError("MODERATION_POLICY_EMPTY", "Policy has no stages")
    policy.status = "ACTIVE"
    policy.activated_by = actor_user_id
    policy.activated_at = datetime.now(UTC)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="ModerationPolicy",
        entity_id=policy.id,
        action="moderation_policy_activated",
        after=_serialize_policy(policy),
    )
    await db.flush()
    await db.refresh(policy)
    return _serialize_policy(policy)


async def retire_moderation_policy(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    policy_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    policy = await _get_policy(db, tenant_id=tenant_id, policy_id=policy_id)
    if policy.status != "ACTIVE":
        raise EnterpriseOpsError("INVALID_POLICY_STATE", "Only ACTIVE policies retire")
    policy.status = "RETIRED"
    policy.retired_by = actor_user_id
    policy.retired_at = datetime.now(UTC)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="ModerationPolicy",
        entity_id=policy.id,
        action="moderation_policy_retired",
        after=_serialize_policy(policy),
    )
    await db.flush()
    await db.refresh(policy)
    return _serialize_policy(policy)


async def decide_moderation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    case_id: uuid.UUID,
    decision: str,
    reason: str | None,
    actor_user_id: uuid.UUID,
    actor_roles: frozenset[str],
) -> dict[str, Any]:
    if decision not in {"APPROVE", "RETURN", "REJECT"}:
        raise EnterpriseOpsError("INVALID_DECISION", "Unsupported decision")
    if decision in {"RETURN", "REJECT"} and not (reason or "").strip():
        raise EnterpriseOpsError("REASON_REQUIRED", "RETURN/REJECT require a reason")

    case = await db.scalar(
        select(ModerationCase)
        .where(ModerationCase.id == case_id, ModerationCase.tenant_id == tenant_id)
        .with_for_update()
    )
    if case is None:
        raise EnterpriseOpsError("NOT_FOUND", "Moderation case not found")
    if case.status not in {"PENDING", "IN_PROGRESS", "RETURNED"}:
        raise EnterpriseOpsError("INVALID_CASE_STATE", "Case is not actionable")

    stage = await db.scalar(
        select(ModerationStage).where(
            ModerationStage.tenant_id == tenant_id,
            ModerationStage.policy_id == case.policy_id,
            ModerationStage.stage_order == case.current_stage_order,
        )
    )
    if stage is None:
        raise EnterpriseOpsError("STAGE_MISSING", "Current stage not found")
    if stage.required_role not in actor_roles and "INSTITUTION_ADMIN" not in actor_roles:
        raise EnterpriseOpsError(
            "FORBIDDEN_ROLE",
            f"Stage requires role {stage.required_role}",
        )

    prior_review = await db.scalar(
        select(ReviewAction.id).where(
            ReviewAction.tenant_id == tenant_id,
            ReviewAction.actor_user_id == actor_user_id,
            ReviewAction.question_evaluation_id.in_(
                select(QuestionEvaluation.id).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id == case.evaluation_run_id,
                )
            ),
        )
    )
    if prior_review is not None and decision == "APPROVE":
        raise EnterpriseOpsError(
            "SEPARATION_OF_DUTIES",
            "Evaluator who reviewed this run cannot approve moderation",
        )

    action = ModerationAction(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        case_id=case.id,
        stage_order=case.current_stage_order,
        actor_user_id=actor_user_id,
        decision=decision,
        reason=reason,
    )
    db.add(action)
    case.status = "IN_PROGRESS"

    submission = await db.scalar(
        select(Submission).where(
            Submission.id == case.submission_id, Submission.tenant_id == tenant_id
        )
    )
    run = await db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == case.evaluation_run_id,
            EvaluationRun.tenant_id == tenant_id,
        )
    )
    if submission is None or run is None:
        raise EnterpriseOpsError("NOT_FOUND", "Submission or run missing")

    if decision == "RETURN":
        case.status = "RETURNED"
        submission.workflow_state = "EVALUATION_REVIEW"
        work_items = list(
            (
                await db.scalars(
                    select(GradingWorkItem).where(
                        GradingWorkItem.tenant_id == tenant_id,
                        GradingWorkItem.evaluation_run_id == run.id,
                        GradingWorkItem.status.in_(["SUBMITTED", "COMPLETED"]),
                    )
                )
            ).all()
        )
        for item in work_items:
            item.status = "RETURNED"
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="ModerationCase",
            entity_id=case.id,
            action="moderation_returned",
            after={"reason": reason},
        )
    elif decision == "REJECT":
        case.status = "REJECTED"
        submission.workflow_state = "FAILED"
        run.status = "FAILED"
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="ModerationCase",
            entity_id=case.id,
            action="moderation_rejected",
            after={"reason": reason},
        )
    else:
        next_stage = await db.scalar(
            select(ModerationStage)
            .where(
                ModerationStage.tenant_id == tenant_id,
                ModerationStage.policy_id == case.policy_id,
                ModerationStage.stage_order > case.current_stage_order,
            )
            .order_by(ModerationStage.stage_order.asc())
            .limit(1)
        )
        if next_stage is None:
            case.status = "APPROVED"
            submission.workflow_state = "APPROVED"
            run.status = "COMPLETED"
            run.finished_at = datetime.now(UTC)
            work_items = list(
                (
                    await db.scalars(
                        select(GradingWorkItem).where(
                            GradingWorkItem.tenant_id == tenant_id,
                            GradingWorkItem.evaluation_run_id == run.id,
                            GradingWorkItem.status == "SUBMITTED",
                        )
                    )
                ).all()
            )
            for item in work_items:
                item.status = "COMPLETED"
            await add_audit_event(
                db,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                entity_type="ModerationCase",
                entity_id=case.id,
                action="moderation_final_approved",
                after=_serialize_case(case),
            )
        else:
            case.current_stage_order = next_stage.stage_order
            case.status = "PENDING"
            await add_audit_event(
                db,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                entity_type="ModerationCase",
                entity_id=case.id,
                action="moderation_stage_approved",
                after={"next_stage_order": next_stage.stage_order},
            )

    await db.flush()
    await db.refresh(case)
    return _serialize_case(case)


async def create_grievance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
    requester_reference: str,
    reason: str,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None or published.status != "PUBLISHED":
        raise EnterpriseOpsError(
            "NOT_ELIGIBLE",
            "Formal grievance requires a current PUBLISHED result",
        )
    dup = await db.scalar(
        select(GrievanceCase).where(
            GrievanceCase.tenant_id == tenant_id,
            GrievanceCase.original_published_result_id == published.id,
            GrievanceCase.status.in_(list(ACTIVE_GRIEVANCE_STATUSES)),
        )
    )
    if dup is not None:
        raise EnterpriseOpsError(
            "DUPLICATE_GRIEVANCE",
            "An active grievance already exists for this result",
        )
    case = GrievanceCase(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        submission_id=published.submission_id,
        original_published_result_id=published.id,
        original_evaluation_run_id=published.evaluation_run_id,
        requester_reference=requester_reference.strip(),
        submitted_by=actor_user_id,
        reason=reason.strip(),
        status="SUBMITTED",
    )
    db.add(case)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GrievanceCase",
        entity_id=case.id,
        action="grievance_created",
        after=_serialize_grievance(case),
    )
    await db.flush()
    await db.refresh(case)
    return _serialize_grievance(case)


async def accept_grievance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    grievance_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    decision_reason: str | None,
) -> dict[str, Any]:
    case = await _get_grievance(db, tenant_id=tenant_id, grievance_id=grievance_id)
    if case.status not in {"SUBMITTED", "UNDER_REVIEW"}:
        raise EnterpriseOpsError("INVALID_GRIEVANCE_STATE", "Cannot accept grievance")
    original = await db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == case.original_evaluation_run_id,
            EvaluationRun.tenant_id == tenant_id,
        )
    )
    if original is None:
        raise EnterpriseOpsError("NOT_FOUND", "Original evaluation run missing")
    max_num = await db.scalar(
        select(func.max(EvaluationRun.run_number)).where(
            EvaluationRun.tenant_id == tenant_id,
            EvaluationRun.submission_id == case.submission_id,
        )
    )
    new_run = EvaluationRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        submission_id=case.submission_id,
        assessment_id=original.assessment_id,
        assessment_version_id=original.assessment_version_id,
        run_number=int(max_num or 0) + 1,
        run_kind="RE_EVALUATION",
        supersedes_run_id=original.id,
        grievance_case_id=case.id,
        status="REVIEW_REQUIRED",
        provider=original.provider,
        model=original.model,
        rules_engine_version=original.rules_engine_version,
        started_by=actor_user_id,
        started_at=datetime.now(UTC),
    )
    db.add(new_run)
    await db.flush()

    originals = list(
        (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id == original.id,
                )
            )
        ).all()
    )
    for src in originals:
        db.add(
            QuestionEvaluation(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                evaluation_run_id=new_run.id,
                submission_id=src.submission_id,
                student_id=src.student_id,
                assessment_id=src.assessment_id,
                assessment_version_id=src.assessment_version_id,
                question_id=src.question_id,
                question_version_id=src.question_version_id,
                rubric_version_id=src.rubric_version_id,
                answer_key_version_id=src.answer_key_version_id,
                mapping_id=src.mapping_id,
                answer_region_ids=list(src.answer_region_ids or []),
                transcription_refs=list(src.transcription_refs or []),
                evidence_metadata=dict(src.evidence_metadata or {}),
                max_mark=src.max_mark,
                proposed_ai_score=src.proposed_ai_score,
                final_human_approved_score=None,
                first_divergence_step=src.first_divergence_step,
                ecf_applied=src.ecf_applied,
                ecf_chain=dict(src.ecf_chain or {}),
                alternative_method_id=src.alternative_method_id,
                alternative_method_label=src.alternative_method_label,
                error_codes=list(src.error_codes or []),
                deduction_reasons=list(src.deduction_reasons or []),
                criterion_snapshot=list(src.criterion_snapshot or []),
                identity_confidence=src.identity_confidence,
                mapping_confidence=src.mapping_confidence,
                transcription_confidence=src.transcription_confidence,
                evaluation_confidence=src.evaluation_confidence,
                math_verification_confidence=src.math_verification_confidence,
                workflow_state="REVIEW_REQUIRED",
                ledger_version=1,
                supersedes_ledger_id=src.id,
                reviewed_by=None,
                reviewed_at=None,
                reviewer_feedback=None,
                approved_snapshot_hash=None,
                ai_execution_record_id=src.ai_execution_record_id,
            )
        )

    original.status = "SUPERSEDED"
    case.status = "RE_EVALUATING"
    case.decision_by = actor_user_id
    case.decision_at = datetime.now(UTC)
    case.decision_reason = decision_reason
    case.reevaluation_run_id = new_run.id

    submission = await db.scalar(
        select(Submission).where(
            Submission.id == case.submission_id, Submission.tenant_id == tenant_id
        )
    )
    if submission is not None:
        submission.workflow_state = "EVALUATION_REVIEW"

    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GrievanceCase",
        entity_id=case.id,
        action="grievance_accepted_reevaluation_created",
        after={
            "reevaluation_run_id": str(new_run.id),
            "run_number": new_run.run_number,
            "supersedes_run_id": str(original.id),
        },
    )
    await db.flush()
    await db.refresh(case)
    return _serialize_grievance(case)


async def reject_grievance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    grievance_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    decision_reason: str,
) -> dict[str, Any]:
    case = await _get_grievance(db, tenant_id=tenant_id, grievance_id=grievance_id)
    if case.status not in {"SUBMITTED", "UNDER_REVIEW"}:
        raise EnterpriseOpsError("INVALID_GRIEVANCE_STATE", "Cannot reject grievance")
    case.status = "REJECTED"
    case.decision_by = actor_user_id
    case.decision_at = datetime.now(UTC)
    case.decision_reason = decision_reason
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GrievanceCase",
        entity_id=case.id,
        action="grievance_rejected",
        after={"reason": decision_reason},
    )
    await db.flush()
    await db.refresh(case)
    return _serialize_grievance(case)


async def resolve_grievance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    grievance_id: uuid.UUID,
    revised_published_result_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    case = await _get_grievance(db, tenant_id=tenant_id, grievance_id=grievance_id)
    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == revised_published_result_id,
            PublishedResult.tenant_id == tenant_id,
            PublishedResult.status == "PUBLISHED",
        )
    )
    if published is None:
        raise EnterpriseOpsError("NOT_FOUND", "Revised published result not found")
    case.status = "RESOLVED"
    case.revised_published_result_id = published.id
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="GrievanceCase",
        entity_id=case.id,
        action="grievance_resolved",
        after={"revised_published_result_id": str(published.id)},
    )
    await db.flush()
    await db.refresh(case)
    return _serialize_grievance(case)


async def _get_pool(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    pool_id: uuid.UUID,
    for_update: bool = False,
) -> GradingPool:
    stmt: Select[tuple[GradingPool]] = select(GradingPool).where(
        GradingPool.id == pool_id, GradingPool.tenant_id == tenant_id
    )
    if for_update:
        stmt = stmt.with_for_update()
    pool = await db.scalar(stmt)
    if pool is None:
        raise EnterpriseOpsError("NOT_FOUND", "Grading pool not found")
    return pool


async def _get_work(
    db: AsyncSession, *, tenant_id: uuid.UUID, work_item_id: uuid.UUID
) -> GradingWorkItem:
    item = await db.scalar(
        select(GradingWorkItem).where(
            GradingWorkItem.id == work_item_id,
            GradingWorkItem.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise EnterpriseOpsError("NOT_FOUND", "Work item not found")
    return item


async def _get_policy(
    db: AsyncSession, *, tenant_id: uuid.UUID, policy_id: uuid.UUID
) -> ModerationPolicy:
    policy = await db.scalar(
        select(ModerationPolicy).where(
            ModerationPolicy.id == policy_id,
            ModerationPolicy.tenant_id == tenant_id,
        )
    )
    if policy is None:
        raise EnterpriseOpsError("NOT_FOUND", "Moderation policy not found")
    return policy


async def _get_grievance(
    db: AsyncSession, *, tenant_id: uuid.UUID, grievance_id: uuid.UUID
) -> GrievanceCase:
    case = await db.scalar(
        select(GrievanceCase).where(
            GrievanceCase.id == grievance_id,
            GrievanceCase.tenant_id == tenant_id,
        )
    )
    if case is None:
        raise EnterpriseOpsError("NOT_FOUND", "Grievance not found")
    return case
