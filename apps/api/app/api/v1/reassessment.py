# ruff: noqa: B008
"""B14 reassessment instantiation and mastery delta API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.session import get_db_session
from app.services.reassessment import (
    ReassessmentError,
    get_reassessment,
    instantiate_reassessment,
    rebuild_b14,
)

router = APIRouter(tags=["reassessment"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )


def _map_reassessment_error(exc: ReassessmentError) -> HTTPException:
    if exc.code == "NOT_FOUND":
        return _http_error(404, exc.code, exc.message)
    if exc.code in {
        "REASSESSMENT_BLUEPRINT_STALE",
        "REASSESSMENT_BLUEPRINT_NOT_APPROVED",
        "REASSESSMENT_ALREADY_INSTANTIATED",
        "REASSESSMENT_STUDENT_MISMATCH",
        "REASSESSMENT_ATTEMPT_BOUND",
        "REASSESSMENT_B14_NOT_READY",
        "REASSESSMENT_B14_SNAPSHOT_MISSING",
        "REASSESSMENT_BASELINE_MUTATED",
        "LEARNING_PLAN_NOT_READY",
    }:
        return _http_error(409, exc.code, exc.message)
    if exc.code in {
        "REASSESSMENT_ITEMS_INVALID",
        "REASSESSMENT_INVALID_PROMPT",
        "REASSESSMENT_INVALID_MARKS",
    }:
        return _http_error(422, exc.code, exc.message)
    return _http_error(400, exc.code, exc.message)


class ReassessmentItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    improvement_assessment_item_id: uuid.UUID
    prompt_text: str = Field(min_length=1, max_length=20000)
    max_marks: str
    question_type: str | None = Field(default=None, max_length=64)
    instructions: str | None = Field(default=None, max_length=8000)


class ReassessmentInstantiateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReassessmentItemIn] = Field(min_length=1)


@router.post("/improvement-assessments/{blueprint_id}/reassessment")
async def create_reassessment(
    blueprint_id: uuid.UUID,
    body: ReassessmentInstantiateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    try:
        result = await instantiate_reassessment(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            blueprint_id=blueprint_id,
            items=[item.model_dump(mode="json") for item in body.items],
        )
    except ReassessmentError as exc:
        raise _map_reassessment_error(exc) from exc
    await db.commit()
    return result


@router.get("/reassessments/{reassessment_id}")
async def reassessment_detail(
    reassessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:read")),
) -> dict[str, Any]:
    try:
        return await get_reassessment(
            db, tenant_id=auth.tenant_id, reassessment_id=reassessment_id
        )
    except ReassessmentError as exc:
        raise _map_reassessment_error(exc) from exc


@router.post("/reassessments/{reassessment_id}/b14/rebuild")
async def rebuild_reassessment_b14(
    reassessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("analytics:materialize")),
) -> dict[str, Any]:
    try:
        result = await rebuild_b14(
            db,
            tenant_id=auth.tenant_id,
            reassessment_id=reassessment_id,
            actor_user_id=auth.user_id,
        )
    except ReassessmentError as exc:
        raise _map_reassessment_error(exc) from exc
    await db.commit()
    return result
