# ruff: noqa: B008
"""B18 answer clustering + CO/PO outcome reporting API."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.session import get_db_session
from app.services.outcome_intelligence import (
    OutcomeIntelligenceError,
    activate_mapping_set,
    add_cluster_review,
    add_question_mapping,
    create_attainment_report,
    create_cluster_run,
    create_mapping_set,
    create_outcome_definition,
    export_attainment_csv,
    get_attainment_report,
    get_cluster_detail,
    get_cluster_run,
    get_mapping_set,
    get_outcome_definition,
    list_attainment_reports,
    list_cluster_runs,
    list_clusters_for_run,
    list_mapping_sets,
    list_outcome_definitions,
    remove_question_mapping,
    update_outcome_definition,
)

router = APIRouter(tags=["outcome-intelligence"])
Db = Annotated[AsyncSession, Depends(get_db_session)]

_CONFLICT_CODES = {
    "CLUSTER_RUN_CONFLICT",
    "OUTCOME_DEFINITION_CONFLICT",
    "MAPPING_SET_NOT_DRAFT",
    "MAPPING_SET_EMPTY",
    "MAPPING_SET_NOT_ACTIVE",
    "MAPPING_CONFLICT",
    "ATTAINMENT_REPORT_CONFLICT",
    "LEDGER_MUTATION_FORBIDDEN",
}


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )


def _map_error(exc: OutcomeIntelligenceError) -> HTTPException:
    if exc.code == "NOT_FOUND":
        return _http_error(404, exc.code, exc.message)
    if exc.code in _CONFLICT_CODES:
        return _http_error(409, exc.code, exc.message)
    return _http_error(400, exc.code, exc.message)


class ClusterRunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: uuid.UUID
    question_id: uuid.UUID
    similarity_threshold: Decimal | None = Field(default=None, gt=0, le=1)


class ClusterReviewCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: str = Field(min_length=1, max_length=8000)
    suggested_rubric_refinement: str | None = Field(default=None, max_length=8000)


class OutcomeDefinitionCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_type: str = Field(min_length=2, max_length=8)
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=8000)


class OutcomeDefinitionUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    status: str | None = Field(default=None, min_length=1, max_length=32)


class MappingSetCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)


class QuestionMappingCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: uuid.UUID
    outcome_definition_id: uuid.UUID
    weight: Decimal | None = Field(default=None, gt=0)


class AttainmentReportCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: uuid.UUID
    mapping_set_id: uuid.UUID | None = None


# --- Clustering routes ------------------------------------------------------


@router.post("/quality/answer-clusters/runs")
async def post_cluster_run(
    body: ClusterRunCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("clustering:manage")),
) -> dict[str, Any]:
    try:
        result = await create_cluster_run(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            assessment_version_id=body.assessment_version_id,
            question_id=body.question_id,
            similarity_threshold=body.similarity_threshold,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/answer-clusters/runs")
async def get_cluster_runs(
    db: Db,
    assessment_version_id: uuid.UUID | None = Query(default=None),
    question_id: uuid.UUID | None = Query(default=None),
    auth: AuthContext = Depends(require_permissions("clustering:read")),
) -> dict[str, Any]:
    return await list_cluster_runs(
        db,
        tenant_id=auth.tenant_id,
        assessment_version_id=assessment_version_id,
        question_id=question_id,
    )


@router.get("/quality/answer-clusters/runs/{run_id}")
async def get_cluster_run_route(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("clustering:read")),
) -> dict[str, Any]:
    try:
        return await get_cluster_run(db, tenant_id=auth.tenant_id, run_id=run_id)
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc


@router.get("/quality/answer-clusters/runs/{run_id}/clusters")
async def get_clusters_for_run_route(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("clustering:read")),
) -> dict[str, Any]:
    try:
        return await list_clusters_for_run(
            db, tenant_id=auth.tenant_id, run_id=run_id
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc


@router.get("/quality/answer-clusters/clusters/{cluster_id}")
async def get_cluster_route(
    cluster_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("clustering:read")),
) -> dict[str, Any]:
    try:
        return await get_cluster_detail(
            db, tenant_id=auth.tenant_id, cluster_id=cluster_id
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc


@router.post("/quality/answer-clusters/clusters/{cluster_id}/reviews")
async def post_cluster_review(
    cluster_id: uuid.UUID,
    body: ClusterReviewCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("clustering:review")),
) -> dict[str, Any]:
    try:
        result = await add_cluster_review(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            cluster_id=cluster_id,
            observation=body.observation,
            suggested_rubric_refinement=body.suggested_rubric_refinement,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


# --- Outcomes routes --------------------------------------------------------


@router.post("/outcomes/definitions")
async def post_outcome_definition(
    body: OutcomeDefinitionCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:manage")),
) -> dict[str, Any]:
    try:
        result = await create_outcome_definition(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            outcome_type=body.outcome_type,
            code=body.code,
            title=body.title,
            description=body.description,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


@router.get("/outcomes/definitions")
async def get_outcome_definitions(
    db: Db,
    outcome_type: str | None = Query(default=None),
    auth: AuthContext = Depends(require_permissions("outcomes:read")),
) -> dict[str, Any]:
    return await list_outcome_definitions(
        db, tenant_id=auth.tenant_id, outcome_type=outcome_type
    )


@router.get("/outcomes/definitions/{definition_id}")
async def get_outcome_definition_route(
    definition_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:read")),
) -> dict[str, Any]:
    try:
        return await get_outcome_definition(
            db, tenant_id=auth.tenant_id, definition_id=definition_id
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc


@router.patch("/outcomes/definitions/{definition_id}")
async def patch_outcome_definition(
    definition_id: uuid.UUID,
    body: OutcomeDefinitionUpdateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:manage")),
) -> dict[str, Any]:
    try:
        result = await update_outcome_definition(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            definition_id=definition_id,
            title=body.title,
            description=body.description,
            status=body.status,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


@router.post("/outcomes/mapping-sets")
async def post_mapping_set(
    body: MappingSetCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:manage")),
) -> dict[str, Any]:
    try:
        result = await create_mapping_set(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            assessment_version_id=body.assessment_version_id,
            title=body.title,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


@router.get("/outcomes/mapping-sets")
async def get_mapping_sets(
    db: Db,
    assessment_version_id: uuid.UUID | None = Query(default=None),
    auth: AuthContext = Depends(require_permissions("outcomes:read")),
) -> dict[str, Any]:
    return await list_mapping_sets(
        db,
        tenant_id=auth.tenant_id,
        assessment_version_id=assessment_version_id,
    )


@router.get("/outcomes/mapping-sets/{mapping_set_id}")
async def get_mapping_set_route(
    mapping_set_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:read")),
) -> dict[str, Any]:
    try:
        return await get_mapping_set(
            db, tenant_id=auth.tenant_id, mapping_set_id=mapping_set_id
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc


@router.post("/outcomes/mapping-sets/{mapping_set_id}/mappings")
async def post_question_mapping(
    mapping_set_id: uuid.UUID,
    body: QuestionMappingCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:manage")),
) -> dict[str, Any]:
    try:
        result = await add_question_mapping(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            mapping_set_id=mapping_set_id,
            question_id=body.question_id,
            outcome_definition_id=body.outcome_definition_id,
            weight=body.weight,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


@router.delete("/outcomes/mappings/{mapping_id}")
async def delete_question_mapping(
    mapping_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:manage")),
) -> dict[str, Any]:
    try:
        result = await remove_question_mapping(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            mapping_id=mapping_id,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


@router.post("/outcomes/mapping-sets/{mapping_set_id}/activate")
async def post_activate_mapping_set(
    mapping_set_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:manage")),
) -> dict[str, Any]:
    try:
        result = await activate_mapping_set(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            mapping_set_id=mapping_set_id,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


@router.post("/outcomes/attainment-reports")
async def post_attainment_report(
    body: AttainmentReportCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:report")),
) -> dict[str, Any]:
    try:
        result = await create_attainment_report(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            assessment_version_id=body.assessment_version_id,
            mapping_set_id=body.mapping_set_id,
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    await db.commit()
    return result


@router.get("/outcomes/attainment-reports")
async def get_attainment_reports(
    db: Db,
    assessment_version_id: uuid.UUID | None = Query(default=None),
    auth: AuthContext = Depends(require_permissions("outcomes:read")),
) -> dict[str, Any]:
    return await list_attainment_reports(
        db,
        tenant_id=auth.tenant_id,
        assessment_version_id=assessment_version_id,
    )


@router.get("/outcomes/attainment-reports/{report_id}")
async def get_attainment_report_route(
    report_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:read")),
) -> dict[str, Any]:
    try:
        return await get_attainment_report(
            db, tenant_id=auth.tenant_id, report_id=report_id
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc


@router.get("/outcomes/attainment-reports/{report_id}/export.csv")
async def get_attainment_export_csv(
    report_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("outcomes:read")),
) -> Response:
    try:
        csv_text = await export_attainment_csv(
            db, tenant_id=auth.tenant_id, report_id=report_id
        )
    except OutcomeIntelligenceError as exc:
        raise _map_error(exc) from exc
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="attainment-{report_id}.csv"'
        },
    )
