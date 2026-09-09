# ruff: noqa: B008
"""B6 evaluation ledger review API."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.models import EvaluationRun, QuestionEvaluation, Submission
from app.db.session import get_db_session
from app.services.evaluation import (
    EvaluationError,
    accept_question_evaluation,
    build_evaluation_workspace,
    escalate_question_evaluation,
    feedback_question_evaluation,
    finalize_evaluation,
    get_evaluation_run,
    get_question_evaluation,
    override_question_evaluation,
    prepare_evaluation,
)
from app.tasks.celery_app import enqueue_evaluation

router = APIRouter(tags=["evaluation"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _http_error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message, **extra},
    )


async def _scoped_submission(
    db: AsyncSession, submission_id: uuid.UUID, tenant_id: uuid.UUID
) -> Submission:
    item = await db.scalar(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    return item


class CriterionFinalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_criterion_id: uuid.UUID
    final_marks: Decimal = Field(ge=0)


class OverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: Decimal = Field(ge=0)
    reason: str = Field(min_length=1, max_length=4000)
    feedback: str | None = Field(default=None, max_length=5000)
    criterion_finals: list[CriterionFinalIn] = Field(default_factory=list, max_length=50)
    valid_alternative: bool = False


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: str = Field(min_length=1, max_length=4000)


class EscalateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=4000)


@router.post("/submissions/{submission_id}/evaluation/prepare")
async def prepare_submission_evaluation(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:run")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    try:
        run, job = await prepare_evaluation(
            db,
            tenant_id=auth.tenant_id,
            submission=item,
            actor_user_id=auth.user_id,
        )
    except EvaluationError as exc:
        raise _http_error(409, exc.code, exc.message) from exc
    await db.commit()

    if job is not None and job.status == "QUEUED":
        task_id = await enqueue_evaluation(
            tenant_id=auth.tenant_id,
            submission_id=item.id,
            job_id=job.id,
        )
        if task_id:
            job.celery_task_id = task_id
            await db.commit()

    await db.refresh(item)
    await db.refresh(run)
    return {
        "submission_id": str(item.id),
        "workflow_state": item.workflow_state,
        "evaluation_run_id": str(run.id),
        "run_status": run.status,
        "job_id": str(job.id) if job else None,
    }


@router.get("/submissions/{submission_id}/evaluation")
async def get_submission_evaluation(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:read")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    return await build_evaluation_workspace(
        db, tenant_id=auth.tenant_id, submission=item
    )


@router.get("/evaluation-runs/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:read")),
) -> dict[str, Any]:
    try:
        return await get_evaluation_run(db, tenant_id=auth.tenant_id, run_id=run_id)
    except EvaluationError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 409
        raise _http_error(status, exc.code, exc.message) from exc


@router.get("/question-evaluations/{qe_id}")
async def get_qe(
    qe_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:read")),
) -> dict[str, Any]:
    try:
        return await get_question_evaluation(db, tenant_id=auth.tenant_id, qe_id=qe_id)
    except EvaluationError as exc:
        status = 404 if exc.code == "NOT_FOUND" else 409
        raise _http_error(status, exc.code, exc.message) from exc


@router.post("/question-evaluations/{qe_id}/accept")
async def accept_qe(
    qe_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:review")),
) -> dict[str, Any]:
    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == qe_id,
            QuestionEvaluation.tenant_id == auth.tenant_id,
        )
    )
    if qe is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    try:
        qe = await accept_question_evaluation(
            db,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            qe=qe,
            actor_roles=auth.roles,
            actor_permissions=auth.permissions,
        )
    except EvaluationError as exc:
        status = 403 if exc.code == "GRADING_ASSIGNMENT_FORBIDDEN" else 409
        raise _http_error(status, exc.code, exc.message) from exc
    await db.commit()
    return await get_question_evaluation(db, tenant_id=auth.tenant_id, qe_id=qe.id)


@router.post("/question-evaluations/{qe_id}/override")
async def override_qe(
    qe_id: uuid.UUID,
    payload: OverrideIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:review")),
) -> dict[str, Any]:
    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == qe_id,
            QuestionEvaluation.tenant_id == auth.tenant_id,
        )
    )
    if qe is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    try:
        qe = await override_question_evaluation(
            db,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            qe=qe,
            score=payload.score,
            reason=payload.reason,
            feedback=payload.feedback,
            criterion_finals=[
                {"rubric_criterion_id": c.rubric_criterion_id, "final_marks": c.final_marks}
                for c in payload.criterion_finals
            ],
            valid_alternative=payload.valid_alternative,
            actor_roles=auth.roles,
            actor_permissions=auth.permissions,
        )
    except EvaluationError as exc:
        status = 403 if exc.code == "GRADING_ASSIGNMENT_FORBIDDEN" else 409
        raise _http_error(status, exc.code, exc.message) from exc
    await db.commit()
    return await get_question_evaluation(db, tenant_id=auth.tenant_id, qe_id=qe.id)


@router.post("/question-evaluations/{qe_id}/feedback")
async def feedback_qe(
    qe_id: uuid.UUID,
    payload: FeedbackIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:review")),
) -> dict[str, Any]:
    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == qe_id,
            QuestionEvaluation.tenant_id == auth.tenant_id,
        )
    )
    if qe is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    try:
        qe = await feedback_question_evaluation(
            db,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            qe=qe,
            feedback=payload.feedback,
            actor_roles=auth.roles,
            actor_permissions=auth.permissions,
        )
    except EvaluationError as exc:
        status = 403 if exc.code == "GRADING_ASSIGNMENT_FORBIDDEN" else 409
        raise _http_error(status, exc.code, exc.message) from exc
    await db.commit()
    return await get_question_evaluation(db, tenant_id=auth.tenant_id, qe_id=qe.id)


@router.post("/question-evaluations/{qe_id}/escalate")
async def escalate_qe(
    qe_id: uuid.UUID,
    payload: EscalateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:review")),
) -> dict[str, Any]:
    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == qe_id,
            QuestionEvaluation.tenant_id == auth.tenant_id,
        )
    )
    if qe is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    try:
        qe = await escalate_question_evaluation(
            db,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            qe=qe,
            reason=payload.reason,
            actor_roles=auth.roles,
            actor_permissions=auth.permissions,
        )
    except EvaluationError as exc:
        status = 403 if exc.code == "GRADING_ASSIGNMENT_FORBIDDEN" else 409
        raise _http_error(status, exc.code, exc.message) from exc
    await db.commit()
    return await get_question_evaluation(db, tenant_id=auth.tenant_id, qe_id=qe.id)


@router.post("/submissions/{submission_id}/evaluation/finalize")
async def finalize_submission_evaluation(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("evaluation:approve")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    try:
        item = await finalize_evaluation(
            db,
            tenant_id=auth.tenant_id,
            submission=item,
            actor_user_id=auth.user_id,
        )
    except EvaluationError as exc:
        raise _http_error(409, exc.code, exc.message) from exc
    await db.commit()
    await db.refresh(item)
    run = await db.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.tenant_id == auth.tenant_id,
            EvaluationRun.submission_id == item.id,
        )
        .order_by(EvaluationRun.run_number.desc())
        .limit(1)
    )
    return {
        "submission_id": str(item.id),
        "workflow_state": item.workflow_state,
        "evaluation_run_id": str(run.id) if run else None,
        "run_status": run.status if run else None,
    }
