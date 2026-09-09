# ruff: noqa: B008
"""B16 enterprise grading, moderation, and grievance API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.models import (
    GradingPool,
    GrievanceCase,
    ModerationAction,
    ModerationCase,
    ModerationPolicy,
    ModerationStage,
)
from app.db.session import get_db_session
from app.services.enterprise_ops import (
    EnterpriseOpsError,
    accept_grievance,
    activate_moderation_policy,
    activate_pool,
    add_pool_member,
    allocate_work,
    assign_work_manual,
    close_pool,
    create_grading_pool,
    create_grievance,
    create_moderation_policy,
    decide_moderation,
    my_grading_queue,
    pool_progress,
    reject_grievance,
    resolve_grievance,
    start_work_item,
    submit_work_item,
    _serialize_case,
    _serialize_grievance,
    _serialize_policy,
    _serialize_pool,
)

router = APIRouter(tags=["enterprise-operations"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _map_error(exc: EnterpriseOpsError) -> HTTPException:
    if exc.code in {"NOT_FOUND"}:
        return _http_error(404, exc.code, exc.message)
    if exc.code in {
        "ALREADY_ASSIGNED",
        "DUPLICATE_GRIEVANCE",
        "POOL_CLOSED",
        "POLICY_ACTIVE_EXISTS",
        "SEPARATION_OF_DUTIES",
        "INVALID_MEMBER_ROLE",
        "FORBIDDEN",
        "FORBIDDEN_ROLE",
    }:
        return _http_error(409, exc.code, exc.message)
    return _http_error(400, exc.code, exc.message)


class CreatePoolIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: uuid.UUID
    assessment_version_id: uuid.UUID
    allocation_strategy: str = Field(pattern="^(MANUAL|ROUND_ROBIN)$")


class AddMemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID
    capacity: int | None = Field(default=None, ge=1)


class AllocateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_run_id: uuid.UUID


class AssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_evaluation_id: uuid.UUID
    evaluator_user_id: uuid.UUID


class ModerationStageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage_order: int = Field(ge=1)
    required_role: str
    label: str = Field(min_length=1)


class CreatePolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: uuid.UUID
    assessment_version_id: uuid.UUID
    stages: list[ModerationStageIn] = Field(min_length=1)


class DecideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(APPROVE|RETURN|REJECT)$")
    reason: str | None = None


class CreateGrievanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published_result_id: uuid.UUID
    requester_reference: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1)


class DecideGrievanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_reason: str | None = None


class ResolveGrievanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revised_published_result_id: uuid.UUID


@router.post("/operations/grading-pools")
async def api_create_pool(
    body: CreatePoolIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:manage")),
) -> dict[str, Any]:
    try:
        return await create_grading_pool(
            db,
            tenant_id=auth.tenant_id,
            assessment_id=body.assessment_id,
            assessment_version_id=body.assessment_version_id,
            allocation_strategy=body.allocation_strategy,
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.get("/operations/grading-pools")
async def api_list_pools(
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:read")),
) -> dict[str, Any]:
    rows = list(
        (
            await db.scalars(
                select(GradingPool)
                .where(GradingPool.tenant_id == auth.tenant_id)
                .order_by(GradingPool.created_at.desc())
            )
        ).all()
    )
    return {"items": [_serialize_pool(row) for row in rows]}


@router.get("/operations/grading-pools/{pool_id}")
async def api_get_pool(
    pool_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:read")),
) -> dict[str, Any]:
    pool = await db.scalar(
        select(GradingPool).where(
            GradingPool.id == pool_id, GradingPool.tenant_id == auth.tenant_id
        )
    )
    if pool is None:
        raise _http_error(404, "NOT_FOUND", "Grading pool not found")
    return _serialize_pool(pool)


@router.post("/operations/grading-pools/{pool_id}/members")
async def api_add_member(
    pool_id: uuid.UUID,
    body: AddMemberIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:manage")),
) -> dict[str, Any]:
    try:
        return await add_pool_member(
            db,
            tenant_id=auth.tenant_id,
            pool_id=pool_id,
            user_id=body.user_id,
            capacity=body.capacity,
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/grading-pools/{pool_id}/activate")
async def api_activate_pool(
    pool_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:manage")),
) -> dict[str, Any]:
    try:
        return await activate_pool(
            db, tenant_id=auth.tenant_id, pool_id=pool_id, actor_user_id=auth.user_id
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/grading-pools/{pool_id}/close")
async def api_close_pool(
    pool_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:manage")),
) -> dict[str, Any]:
    try:
        return await close_pool(
            db, tenant_id=auth.tenant_id, pool_id=pool_id, actor_user_id=auth.user_id
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/grading-pools/{pool_id}/allocate")
async def api_allocate(
    pool_id: uuid.UUID,
    body: AllocateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:manage")),
) -> dict[str, Any]:
    try:
        items = await allocate_work(
            db,
            tenant_id=auth.tenant_id,
            pool_id=pool_id,
            evaluation_run_id=body.evaluation_run_id,
            actor_user_id=auth.user_id,
        )
        return {"items": items}
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/grading-pools/{pool_id}/assign")
async def api_assign(
    pool_id: uuid.UUID,
    body: AssignIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:manage")),
) -> dict[str, Any]:
    try:
        return await assign_work_manual(
            db,
            tenant_id=auth.tenant_id,
            pool_id=pool_id,
            question_evaluation_id=body.question_evaluation_id,
            evaluator_user_id=body.evaluator_user_id,
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.get("/operations/grading-pools/{pool_id}/progress")
async def api_progress(
    pool_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:read")),
) -> dict[str, Any]:
    try:
        return await pool_progress(db, tenant_id=auth.tenant_id, pool_id=pool_id)
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.get("/operations/grading/my-queue")
async def api_my_queue(
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:work")),
) -> dict[str, Any]:
    items = await my_grading_queue(
        db, tenant_id=auth.tenant_id, evaluator_user_id=auth.user_id
    )
    return {"items": items}


@router.post("/operations/grading/work-items/{work_item_id}/start")
async def api_start_work(
    work_item_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:work")),
) -> dict[str, Any]:
    try:
        return await start_work_item(
            db,
            tenant_id=auth.tenant_id,
            work_item_id=work_item_id,
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/grading/work-items/{work_item_id}/submit")
async def api_submit_work(
    work_item_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grading:work")),
) -> dict[str, Any]:
    try:
        return await submit_work_item(
            db,
            tenant_id=auth.tenant_id,
            work_item_id=work_item_id,
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/moderation-policies")
async def api_create_policy(
    body: CreatePolicyIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("moderation:manage")),
) -> dict[str, Any]:
    try:
        return await create_moderation_policy(
            db,
            tenant_id=auth.tenant_id,
            assessment_id=body.assessment_id,
            assessment_version_id=body.assessment_version_id,
            stages=[s.model_dump() for s in body.stages],
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.get("/operations/moderation-policies")
async def api_list_policies(
    db: Db,
    auth: AuthContext = Depends(require_permissions("moderation:read")),
) -> dict[str, Any]:
    rows = list(
        (
            await db.scalars(
                select(ModerationPolicy)
                .where(ModerationPolicy.tenant_id == auth.tenant_id)
                .order_by(ModerationPolicy.created_at.desc())
            )
        ).all()
    )
    return {"items": [_serialize_policy(row) for row in rows]}


@router.post("/operations/moderation-policies/{policy_id}/activate")
async def api_activate_policy(
    policy_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("moderation:manage")),
) -> dict[str, Any]:
    try:
        return await activate_moderation_policy(
            db,
            tenant_id=auth.tenant_id,
            policy_id=policy_id,
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.get("/operations/moderation-cases")
async def api_list_cases(
    db: Db,
    auth: AuthContext = Depends(require_permissions("moderation:read")),
) -> dict[str, Any]:
    rows = list(
        (
            await db.scalars(
                select(ModerationCase)
                .where(ModerationCase.tenant_id == auth.tenant_id)
                .order_by(ModerationCase.created_at.desc())
            )
        ).all()
    )
    return {"items": [_serialize_case(row) for row in rows]}


@router.get("/operations/moderation-cases/{case_id}")
async def api_get_case(
    case_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("moderation:read")),
) -> dict[str, Any]:
    case = await db.scalar(
        select(ModerationCase).where(
            ModerationCase.id == case_id, ModerationCase.tenant_id == auth.tenant_id
        )
    )
    if case is None:
        raise _http_error(404, "NOT_FOUND", "Moderation case not found")
    actions = list(
        (
            await db.scalars(
                select(ModerationAction)
                .where(
                    ModerationAction.tenant_id == auth.tenant_id,
                    ModerationAction.case_id == case.id,
                )
                .order_by(ModerationAction.created_at.asc())
            )
        ).all()
    )
    stages = list(
        (
            await db.scalars(
                select(ModerationStage)
                .where(
                    ModerationStage.tenant_id == auth.tenant_id,
                    ModerationStage.policy_id == case.policy_id,
                )
                .order_by(ModerationStage.stage_order.asc())
            )
        ).all()
    )
    return {
        **_serialize_case(case),
        "stages": [
            {
                "stage_order": s.stage_order,
                "required_role": s.required_role,
                "label": s.label,
            }
            for s in stages
        ],
        "actions": [
            {
                "id": str(a.id),
                "stage_order": a.stage_order,
                "actor_user_id": str(a.actor_user_id),
                "decision": a.decision,
                "reason": a.reason,
                "created_at": a.created_at.isoformat(),
            }
            for a in actions
        ],
    }


@router.post("/operations/moderation-cases/{case_id}/decide")
async def api_decide(
    case_id: uuid.UUID,
    body: DecideIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("moderation:review")),
) -> dict[str, Any]:
    try:
        return await decide_moderation(
            db,
            tenant_id=auth.tenant_id,
            case_id=case_id,
            decision=body.decision,
            reason=body.reason,
            actor_user_id=auth.user_id,
            actor_roles=auth.roles,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/grievances")
async def api_create_grievance(
    body: CreateGrievanceIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grievance:create")),
) -> dict[str, Any]:
    try:
        return await create_grievance(
            db,
            tenant_id=auth.tenant_id,
            published_result_id=body.published_result_id,
            requester_reference=body.requester_reference,
            reason=body.reason,
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.get("/operations/grievances")
async def api_list_grievances(
    db: Db,
    auth: AuthContext = Depends(require_permissions("grievance:read")),
) -> dict[str, Any]:
    rows = list(
        (
            await db.scalars(
                select(GrievanceCase)
                .where(GrievanceCase.tenant_id == auth.tenant_id)
                .order_by(GrievanceCase.created_at.desc())
            )
        ).all()
    )
    return {"items": [_serialize_grievance(row) for row in rows]}


@router.get("/operations/grievances/{grievance_id}")
async def api_get_grievance(
    grievance_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grievance:read")),
) -> dict[str, Any]:
    case = await db.scalar(
        select(GrievanceCase).where(
            GrievanceCase.id == grievance_id,
            GrievanceCase.tenant_id == auth.tenant_id,
        )
    )
    if case is None:
        raise _http_error(404, "NOT_FOUND", "Grievance not found")
    return _serialize_grievance(case)


@router.post("/operations/grievances/{grievance_id}/accept")
async def api_accept_grievance(
    grievance_id: uuid.UUID,
    body: DecideGrievanceIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grievance:manage")),
) -> dict[str, Any]:
    try:
        return await accept_grievance(
            db,
            tenant_id=auth.tenant_id,
            grievance_id=grievance_id,
            actor_user_id=auth.user_id,
            decision_reason=body.decision_reason,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/grievances/{grievance_id}/reject")
async def api_reject_grievance(
    grievance_id: uuid.UUID,
    body: DecideGrievanceIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grievance:manage")),
) -> dict[str, Any]:
    if not (body.decision_reason or "").strip():
        raise _http_error(400, "REASON_REQUIRED", "Reject requires a reason")
    try:
        return await reject_grievance(
            db,
            tenant_id=auth.tenant_id,
            grievance_id=grievance_id,
            actor_user_id=auth.user_id,
            decision_reason=body.decision_reason or "",
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc


@router.post("/operations/grievances/{grievance_id}/resolve")
async def api_resolve_grievance(
    grievance_id: uuid.UUID,
    body: ResolveGrievanceIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("grievance:manage")),
) -> dict[str, Any]:
    try:
        return await resolve_grievance(
            db,
            tenant_id=auth.tenant_id,
            grievance_id=grievance_id,
            revised_published_result_id=body.revised_published_result_id,
            actor_user_id=auth.user_id,
        )
    except EnterpriseOpsError as exc:
        raise _map_error(exc) from exc
