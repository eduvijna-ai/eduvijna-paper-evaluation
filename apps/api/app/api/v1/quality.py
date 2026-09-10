# ruff: noqa: B008
"""B17 assessment quality psychometrics + evaluator calibration API."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import (
    AuthContext,
    require_any_permissions,
    require_permissions,
)
from app.db.session import get_db_session
from app.services.quality import (
    QualityError,
    activate_calibration_session,
    add_calibration_case,
    add_calibration_participant,
    close_calibration_session,
    create_calibration_session,
    create_or_get_psychometric_run,
    get_blind_calibration_case,
    get_calibration_evaluator_metrics,
    get_calibration_progress,
    get_calibration_session,
    get_calibration_session_metrics,
    get_latest_psychometric_run,
    get_my_calibration_metrics,
    get_psychometric_run,
    list_calibration_sessions,
    list_my_calibration_sessions,
    list_psychometric_run_items,
    list_psychometric_runs,
    submit_calibration_response,
)

router = APIRouter(tags=["quality-calibration"])
Db = Annotated[AsyncSession, Depends(get_db_session)]

_CONFLICT_CODES = {
    "PSYCHOMETRIC_RUN_CONFLICT",
    "CALIBRATION_SESSION_NOT_DRAFT",
    "CALIBRATION_SESSION_NOT_ACTIVE",
    "CALIBRATION_SESSION_NOT_CLOSED",
    "CALIBRATION_SESSION_CLOSED",
    "CALIBRATION_CASE_INELIGIBLE",
    "CALIBRATION_CASE_CONFLICT",
    "CALIBRATION_PARTICIPANT_CONFLICT",
    "CALIBRATION_INSUFFICIENT_CASES",
    "CALIBRATION_INSUFFICIENT_PARTICIPANTS",
    "CALIBRATION_RESPONSE_IMMUTABLE",
    "CALIBRATION_NOT_PARTICIPANT",
    "CALIBRATION_SCORE_OUT_OF_BOUNDS",
}


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )


def _map_quality_error(exc: QualityError) -> HTTPException:
    if exc.code == "NOT_FOUND":
        return _http_error(404, exc.code, exc.message)
    if exc.code in _CONFLICT_CODES:
        return _http_error(409, exc.code, exc.message)
    return _http_error(400, exc.code, exc.message)


class PsychometricRunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: uuid.UUID


class CalibrationSessionCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    score_tolerance_abs: Decimal | None = Field(default=None, ge=0)
    score_tolerance_pct: Decimal | None = Field(default=None, ge=0, le=1)
    min_cases: int | None = Field(default=None, ge=1)


class CalibrationCaseCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    published_result_id: uuid.UUID
    question_evaluation_id: uuid.UUID


class CalibrationParticipantCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID


class CalibrationResponseCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: Decimal
    comment: str | None = Field(default=None, max_length=4000)


@router.post("/quality/psychometrics/runs")
async def post_psychometric_run(
    body: PsychometricRunCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await create_or_get_psychometric_run(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            assessment_version_id=body.assessment_version_id,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/psychometrics/runs")
async def get_psychometric_runs(
    db: Db,
    assessment_version_id: uuid.UUID | None = Query(default=None),
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    return await list_psychometric_runs(
        db,
        tenant_id=auth.tenant_id,
        assessment_version_id=assessment_version_id,
    )


@router.get("/quality/psychometrics/runs/{run_id}")
async def get_psychometric_run_route(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await get_psychometric_run(
            db, tenant_id=auth.tenant_id, run_id=run_id
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc


@router.get("/quality/psychometrics/runs/{run_id}/items")
async def get_psychometric_run_items_route(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await list_psychometric_run_items(
            db, tenant_id=auth.tenant_id, run_id=run_id
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc


@router.get("/quality/psychometrics/latest")
async def get_psychometric_latest(
    db: Db,
    assessment_version_id: uuid.UUID = Query(...),
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await get_latest_psychometric_run(
            db,
            tenant_id=auth.tenant_id,
            assessment_version_id=assessment_version_id,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc


@router.post("/quality/calibration/sessions")
async def post_calibration_session(
    body: CalibrationSessionCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await create_calibration_session(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            assessment_version_id=body.assessment_version_id,
            title=body.title,
            score_tolerance_abs=body.score_tolerance_abs,
            score_tolerance_pct=body.score_tolerance_pct,
            min_cases=body.min_cases,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/calibration/sessions")
async def get_calibration_sessions(
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    return await list_calibration_sessions(db, tenant_id=auth.tenant_id)


@router.get("/quality/calibration/sessions/{session_id}")
async def get_calibration_session_route(
    session_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await get_calibration_session(
            db, tenant_id=auth.tenant_id, session_id=session_id
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc


@router.post("/quality/calibration/sessions/{session_id}/cases")
async def post_calibration_case(
    session_id: uuid.UUID,
    body: CalibrationCaseCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await add_calibration_case(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            session_id=session_id,
            published_result_id=body.published_result_id,
            question_evaluation_id=body.question_evaluation_id,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc
    await db.commit()
    return result


@router.post("/quality/calibration/sessions/{session_id}/participants")
async def post_calibration_participant(
    session_id: uuid.UUID,
    body: CalibrationParticipantCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await add_calibration_participant(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            session_id=session_id,
            user_id=body.user_id,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc
    await db.commit()
    return result


@router.post("/quality/calibration/sessions/{session_id}/activate")
async def post_calibration_activate(
    session_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await activate_calibration_session(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            session_id=session_id,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc
    await db.commit()
    return result


@router.post("/quality/calibration/sessions/{session_id}/close")
async def post_calibration_close(
    session_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await close_calibration_session(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            session_id=session_id,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/calibration/my-sessions")
async def get_my_calibration_sessions(
    db: Db,
    auth: AuthContext = Depends(require_permissions("calibration:participate")),
) -> dict[str, Any]:
    return await list_my_calibration_sessions(
        db, tenant_id=auth.tenant_id, user_id=auth.user_id
    )


@router.get("/quality/calibration/sessions/{session_id}/cases/{case_id}/blind")
async def get_calibration_case_blind(
    session_id: uuid.UUID,
    case_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("calibration:participate")),
) -> dict[str, Any]:
    try:
        return await get_blind_calibration_case(
            db,
            tenant_id=auth.tenant_id,
            session_id=session_id,
            case_id=case_id,
            user_id=auth.user_id,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc


@router.post("/quality/calibration/sessions/{session_id}/cases/{case_id}/responses")
async def post_calibration_response(
    session_id: uuid.UUID,
    case_id: uuid.UUID,
    body: CalibrationResponseCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("calibration:participate")),
) -> dict[str, Any]:
    try:
        result = await submit_calibration_response(
            db,
            tenant_id=auth.tenant_id,
            session_id=session_id,
            case_id=case_id,
            user_id=auth.user_id,
            score=body.score,
            comment=body.comment,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/calibration/sessions/{session_id}/progress")
async def get_calibration_progress_route(
    session_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(
        require_any_permissions("quality:read", "calibration:participate")
    ),
) -> dict[str, Any]:
    try:
        return await get_calibration_progress(
            db, tenant_id=auth.tenant_id, session_id=session_id
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc


@router.get("/quality/calibration/sessions/{session_id}/metrics")
async def get_calibration_metrics_route(
    session_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(
        require_any_permissions("quality:manage", "quality:read")
    ),
) -> dict[str, Any]:
    try:
        return await get_calibration_session_metrics(
            db, tenant_id=auth.tenant_id, session_id=session_id
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc


@router.get("/quality/calibration/sessions/{session_id}/evaluator-metrics")
async def get_calibration_evaluator_metrics_route(
    session_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        return await get_calibration_evaluator_metrics(
            db, tenant_id=auth.tenant_id, session_id=session_id
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc


@router.get("/quality/calibration/sessions/{session_id}/my-metrics")
async def get_my_calibration_metrics_route(
    session_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("calibration:participate")),
) -> dict[str, Any]:
    try:
        return await get_my_calibration_metrics(
            db,
            tenant_id=auth.tenant_id,
            session_id=session_id,
            user_id=auth.user_id,
        )
    except QualityError as exc:
        raise _map_quality_error(exc) from exc
