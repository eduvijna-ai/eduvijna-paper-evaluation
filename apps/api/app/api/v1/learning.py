# ruff: noqa: B008
"""B9 learning plan and improvement blueprint API."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.session import get_db_session
from app.services.learning import (
    LearningError,
    approve_blueprint,
    get_improvement_assessment,
    get_learning_workspace,
    get_plan_run,
    prepare_improvement_blueprint,
    prepare_learning_plan,
    reject_blueprint,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["learning"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )


def _map_learning_error(exc: LearningError) -> HTTPException:
    if exc.code == "NOT_FOUND":
        return _http_error(404, exc.code, exc.message)
    if exc.code in {
        "LEARNING_EVIDENCE_NOT_READY",
        "LEARNING_BLUEPRINT_STALE",
        "LEARNING_PLAN_NOT_READY",
        "LEARNING_NO_TARGETS",
        "LEARNING_BLUEPRINT_NOT_PENDING",
        "LEARNING_INPUT_CHANGED",
        "CURRICULUM_PREREQUISITE_CYCLE",
        "LEARNING_BLUEPRINT_TOO_LARGE",
        "LEARNING_BLUEPRINT_COVERAGE",
        "LEARNING_BLUEPRINT_ARTIFACT_MISSING",
        "LEARNING_BLUEPRINT_ARTIFACT_CORRUPT",
        "LEARNING_BLUEPRINT_FOREIGN_NODE",
        "LEARNING_PROVIDER_URL_REJECTED",
    }:
        return _http_error(409, exc.code, exc.message)
    if exc.code in {"INVALID_REJECTION_REASON", "CURRICULUM_PREREQUISITE_INVALID"}:
        return _http_error(422, exc.code, exc.message)
    return _http_error(400, exc.code, exc.message)


class LearningPrepareInput(BaseModel):
    curriculum_id: uuid.UUID


class ImprovementRejectInput(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


@router.get("/learning/students/{student_id}")
async def learning_workspace(
    student_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:read")),
    curriculum_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    try:
        return await get_learning_workspace(
            db,
            tenant_id=auth.tenant_id,
            student_id=student_id,
            curriculum_id=curriculum_id,
        )
    except LearningError as exc:
        raise _map_learning_error(exc) from exc


@router.post("/learning/students/{student_id}/prepare")
async def prepare_student_learning_plan(
    student_id: uuid.UUID,
    body: LearningPrepareInput,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:generate")),
) -> dict[str, Any]:
    try:
        run = await prepare_learning_plan(
            db,
            tenant_id=auth.tenant_id,
            student_id=student_id,
            curriculum_id=body.curriculum_id,
            requested_by=auth.user_id,
        )
    except LearningError as exc:
        raise _map_learning_error(exc) from exc

    await db.commit()

    task_id: str | None = None
    enqueue_error: str | None = None
    if run.status == "QUEUED":
        try:
            from app.tasks.celery_app import enqueue_learning_plan

            task_id = await enqueue_learning_plan(
                tenant_id=auth.tenant_id, run_id=run.id
            )
            if task_id:
                await db.refresh(run)
                run.celery_task_id = task_id
                await db.commit()
                await db.refresh(run)
        except Exception as exc:  # noqa: BLE001
            enqueue_error = str(exc)[:300]
            logger.exception("learning plan enqueue failed run_id=%s", run.id)

    return {
        "run_id": str(run.id),
        "student_id": str(run.student_id),
        "curriculum_id": str(run.curriculum_id),
        "version_number": run.version_number,
        "status": run.status,
        "input_hash": run.input_hash,
        "algorithm_version": run.algorithm_version,
        "celery_task_id": task_id or run.celery_task_id,
        "enqueue_error": enqueue_error,
    }


@router.get("/learning/plan-runs/{run_id}")
async def learning_plan_run(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:read")),
) -> dict[str, Any]:
    try:
        return await get_plan_run(db, tenant_id=auth.tenant_id, run_id=run_id)
    except LearningError as exc:
        raise _map_learning_error(exc) from exc


@router.post("/learning/plan-runs/{run_id}/improvement-blueprints/prepare")
async def prepare_plan_improvement_blueprint(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:generate")),
) -> dict[str, Any]:
    try:
        bp = await prepare_improvement_blueprint(
            db,
            tenant_id=auth.tenant_id,
            run_id=run_id,
            generated_by=auth.user_id,
        )
    except LearningError as exc:
        raise _map_learning_error(exc) from exc

    await db.commit()

    task_id: str | None = None
    enqueue_error: str | None = None
    if bp.status == "DRAFT":
        try:
            from app.tasks.celery_app import enqueue_improvement_blueprint

            task_id = await enqueue_improvement_blueprint(
                tenant_id=auth.tenant_id, blueprint_id=bp.id
            )
            if task_id:
                await db.refresh(bp)
                bp.celery_task_id = task_id
                await db.commit()
                await db.refresh(bp)
        except Exception as exc:  # noqa: BLE001
            enqueue_error = str(exc)[:300]
            logger.exception("blueprint enqueue failed id=%s", bp.id)

    return {
        "improvement_assessment_id": str(bp.id),
        "learning_plan_run_id": str(bp.learning_plan_run_id),
        "version_number": bp.version_number,
        "status": bp.status,
        "input_hash": bp.input_hash,
        "celery_task_id": task_id or bp.celery_task_id,
        "enqueue_error": enqueue_error,
    }


@router.get("/improvement-assessments/{blueprint_id}")
async def improvement_assessment_detail(
    blueprint_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:read")),
) -> dict[str, Any]:
    try:
        return await get_improvement_assessment(
            db, tenant_id=auth.tenant_id, blueprint_id=blueprint_id
        )
    except LearningError as exc:
        raise _map_learning_error(exc) from exc


@router.post("/improvement-assessments/{blueprint_id}/approve")
async def approve_improvement_assessment(
    blueprint_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:approve")),
) -> dict[str, Any]:
    try:
        result = await approve_blueprint(
            db,
            tenant_id=auth.tenant_id,
            blueprint_id=blueprint_id,
            actor_user_id=auth.user_id,
        )
    except LearningError as exc:
        raise _map_learning_error(exc) from exc
    await db.commit()
    return result


@router.post("/improvement-assessments/{blueprint_id}/reject")
async def reject_improvement_assessment(
    blueprint_id: uuid.UUID,
    body: ImprovementRejectInput,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:review")),
) -> dict[str, Any]:
    try:
        result = await reject_blueprint(
            db,
            tenant_id=auth.tenant_id,
            blueprint_id=blueprint_id,
            actor_user_id=auth.user_id,
            reason=body.reason,
        )
    except LearningError as exc:
        raise _map_learning_error(exc) from exc
    await db.commit()
    return result
