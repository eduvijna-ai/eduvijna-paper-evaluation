# ruff: noqa: B008
"""B10 authoring AI run APIs and durable proposal endpoints."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import get_authoring_provider
from app.ai.types import ProposedQuestionNode
from app.core.authorization import AuthContext, require_permissions
from app.db.session import get_db_session
from app.middleware.correlation import get_correlation_id
from app.services.ai_proposals import (
    AnswerKeyProposalRequest,
    CurriculumMappingProposalRequest,
    RubricProposalRequest,
    unavailable,
)
from app.services.authoring_ai import (
    AuthoringAiError,
    apply_question_tree,
    dump_authoring_run,
    get_authoring_run,
    get_latest_authoring_run_for_version,
    prepare_parse_question_paper,
    prepare_propose_answer_key,
    prepare_propose_rubric,
    prepare_suggest_curriculum_mapping,
    update_question_tree_proposal,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["authoring-ai"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _map_authoring_error(exc: AuthoringAiError) -> HTTPException:
    if exc.code == "NOT_FOUND":
        return _http_error(404, exc.code, exc.message)
    if exc.code in {
        "QUESTION_TREE_MARKS_MISMATCH",
        "QUESTION_TREE_DUPLICATE_CODE",
        "QUESTION_TREE_INVALID_HIERARCHY",
        "QUESTION_TREE_DEPTH_EXCEEDED",
        "QUESTION_TREE_TOO_LARGE",
        "QUESTION_TREE_EMPTY",
        "QUESTION_TREE_INVALID_CODE",
        "QUESTION_TREE_INVALID_SCORING_MODE",
        "RUBRIC_MARKS_MISMATCH",
        "INVALID_REJECTION_REASON",
    }:
        return _http_error(422, exc.code, exc.message)
    if exc.code in {
        "AUTHORING_MATERIAL_ALREADY_EXISTS",
        "QUESTION_PAPER_STRUCTURE_EXISTS",
        "ASSESSMENT_NOT_DRAFT",
        "AUTHORING_RUN_NOT_EDITABLE",
        "AUTHORING_RUN_NOT_APPLICABLE",
        "ASSESSMENT_ACADEMIC_CONFIG_FROZEN",
        "INVALID_OPERATION",
    }:
        return _http_error(409, exc.code, exc.message)
    return _http_error(400, exc.code, exc.message)


class QuestionTreeProposalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roots: list[ProposedQuestionNode] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=2000)


async def _enqueue_and_refresh(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    enqueue: Callable[..., Awaitable[str | None]],
) -> dict[str, Any]:
    await db.commit()
    enqueue_error: str | None = None
    task_id: str | None = None
    try:
        task_id = await enqueue(tenant_id=tenant_id, run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        enqueue_error = str(exc)[:300]
        logger.exception("authoring enqueue failed run_id=%s", run_id)
    # Eager workers use a separate session; drop identity-map stale QUEUED rows.
    db.expire_all()
    if task_id:
        run = await get_authoring_run(db, tenant_id=tenant_id, run_id=run_id)
        run.celery_task_id = task_id
        await db.commit()
        db.expire_all()
    run = await get_authoring_run(db, tenant_id=tenant_id, run_id=run_id)
    body = dump_authoring_run(run)
    body["enqueue_error"] = enqueue_error
    return body


@router.get("/authoring-ai-runs/{run_id}")
async def get_authoring_ai_run(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:read")),
) -> dict[str, Any]:
    try:
        run = await get_authoring_run(db, tenant_id=auth.tenant_id, run_id=run_id)
    except AuthoringAiError as exc:
        raise _map_authoring_error(exc) from exc
    return dump_authoring_run(run)


@router.get("/assessment-versions/{version_id}/authoring-ai-runs/latest")
async def get_latest_authoring_ai_run(
    version_id: uuid.UUID,
    db: Db,
    operation: str | None = None,
    auth: AuthContext = Depends(require_permissions("assessment:read")),
) -> dict[str, Any]:
    try:
        run = await get_latest_authoring_run_for_version(
            db,
            tenant_id=auth.tenant_id,
            assessment_version_id=version_id,
            operation=operation,
        )
    except AuthoringAiError as exc:
        raise _map_authoring_error(exc) from exc
    if run is None:
        raise _http_error(404, "NOT_FOUND", "No authoring AI run found")
    return dump_authoring_run(run)


@router.put("/authoring-ai-runs/{run_id}/question-tree-proposal")
async def put_question_tree_proposal(
    run_id: uuid.UUID,
    payload: QuestionTreeProposalIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    try:
        run = await update_question_tree_proposal(
            db,
            tenant_id=auth.tenant_id,
            run_id=run_id,
            roots=list(payload.roots),
            notes=payload.notes,
        )
        await db.commit()
        run = await get_authoring_run(db, tenant_id=auth.tenant_id, run_id=run.id)
    except AuthoringAiError as exc:
        raise _map_authoring_error(exc) from exc
    return dump_authoring_run(run)


@router.post("/authoring-ai-runs/{run_id}/apply-question-tree")
async def post_apply_question_tree(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    try:
        run = await apply_question_tree(
            db,
            tenant_id=auth.tenant_id,
            run_id=run_id,
            applied_by=auth.user_id,
        )
        await db.commit()
        run = await get_authoring_run(db, tenant_id=auth.tenant_id, run_id=run.id)
    except AuthoringAiError as exc:
        raise _map_authoring_error(exc) from exc
    return dump_authoring_run(run)


@router.post("/assessment-versions/{version_id}/question-paper/parse")
async def parse_question_paper(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    provider = get_authoring_provider()
    try:
        run = await prepare_parse_question_paper(
            db,
            tenant_id=auth.tenant_id,
            assessment_version_id=version_id,
            requested_by=auth.user_id,
            correlation_id=get_correlation_id(),
        )
        if provider is None:
            from app.services.authoring_ai import mark_unavailable

            await mark_unavailable(
                db,
                tenant_id=auth.tenant_id,
                run=run,
                operation="parse_question_paper",
            )
            await db.commit()
            raise _http_error(
                503,
                "AI_PROVIDER_UNAVAILABLE",
                "No authoring AI provider is configured",
            )
        await db.flush()
    except AuthoringAiError as exc:
        raise _map_authoring_error(exc) from exc

    from app.tasks.celery_app import enqueue_authoring_parse

    return await _enqueue_and_refresh(
        db,
        run_id=run.id,
        tenant_id=auth.tenant_id,
        enqueue=enqueue_authoring_parse,
    )


@router.post("/ai/proposals/answer-key")
async def propose_answer_key(
    payload: AnswerKeyProposalRequest,
    db: Db,
    request: Request,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    provider = get_authoring_provider()
    if provider is None:
        await unavailable(
            db,
            tenant_id=auth.tenant_id,
            operation="propose_answer_key",
            request=payload,
            requested_by=auth.user_id,
        )
        raise AssertionError("unreachable")

    try:
        run = await prepare_propose_answer_key(
            db,
            tenant_id=auth.tenant_id,
            question_version_id=payload.question_version_id,
            assessment_version_id=payload.assessment_version_id,
            requested_by=auth.user_id,
            instructions=payload.instructions,
            correlation_id=getattr(request.state, "correlation_id", None),
        )
    except AuthoringAiError as exc:
        raise _map_authoring_error(exc) from exc

    from app.tasks.celery_app import enqueue_authoring_answer_key

    return await _enqueue_and_refresh(
        db,
        run_id=run.id,
        tenant_id=auth.tenant_id,
        enqueue=enqueue_authoring_answer_key,
    )


@router.post("/ai/proposals/rubric")
async def propose_rubric(
    payload: RubricProposalRequest,
    db: Db,
    request: Request,
    auth: AuthContext = Depends(require_permissions("rubric:manage")),
) -> dict[str, Any]:
    provider = get_authoring_provider()
    if provider is None:
        await unavailable(
            db,
            tenant_id=auth.tenant_id,
            operation="propose_rubric",
            request=payload,
            requested_by=auth.user_id,
        )
        raise AssertionError("unreachable")

    try:
        run = await prepare_propose_rubric(
            db,
            tenant_id=auth.tenant_id,
            question_version_id=payload.question_version_id,
            assessment_version_id=payload.assessment_version_id,
            requested_by=auth.user_id,
            instructions=payload.instructions,
            correlation_id=getattr(request.state, "correlation_id", None),
        )
    except AuthoringAiError as exc:
        raise _map_authoring_error(exc) from exc

    from app.tasks.celery_app import enqueue_authoring_rubric

    return await _enqueue_and_refresh(
        db,
        run_id=run.id,
        tenant_id=auth.tenant_id,
        enqueue=enqueue_authoring_rubric,
    )


@router.post("/ai/proposals/curriculum-mapping")
async def suggest_curriculum_mapping(
    payload: CurriculumMappingProposalRequest,
    db: Db,
    request: Request,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    provider = get_authoring_provider()
    if provider is None:
        await unavailable(
            db,
            tenant_id=auth.tenant_id,
            operation="suggest_curriculum_mapping",
            request=payload,
            requested_by=auth.user_id,
        )
        raise AssertionError("unreachable")

    try:
        run = await prepare_suggest_curriculum_mapping(
            db,
            tenant_id=auth.tenant_id,
            question_version_id=payload.question_version_id,
            curriculum_id=payload.curriculum_id,
            requested_by=auth.user_id,
            instructions=payload.instructions,
            correlation_id=getattr(request.state, "correlation_id", None),
        )
    except AuthoringAiError as exc:
        raise _map_authoring_error(exc) from exc

    from app.tasks.celery_app import enqueue_authoring_curriculum_mapping

    return await _enqueue_and_refresh(
        db,
        run_id=run.id,
        tenant_id=auth.tenant_id,
        enqueue=enqueue_authoring_curriculum_mapping,
    )
