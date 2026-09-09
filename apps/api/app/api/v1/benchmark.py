# ruff: noqa: B008
"""B15 gold benchmark + AI regression quality API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.session import get_db_session
from app.services.benchmark import (
    BenchmarkError,
    add_case,
    create_dataset,
    create_version,
    evaluate_release_gate,
    get_dataset,
    get_run,
    get_version,
    list_case_results,
    list_cases,
    list_datasets,
    list_eligible_sources,
    list_runs,
    list_versions,
    lock_version,
    remove_case,
    start_regression_run,
)

router = APIRouter(tags=["quality-benchmark"])
Db = Annotated[AsyncSession, Depends(get_db_session)]

_CONFLICT_CODES = {
    "BENCHMARK_DATASET_CODE_CONFLICT",
    "BENCHMARK_VERSION_LOCKED",
    "BENCHMARK_VERSION_NOT_LOCKED",
    "BENCHMARK_VERSION_EMPTY",
    "BENCHMARK_CASE_INELIGIBLE",
    "BENCHMARK_CANDIDATE_UNSUPPORTED",
    "BENCHMARK_CANDIDATE_UNCONFIGURED",
    "BENCHMARK_REPLAY_INVALID",
    "BENCHMARK_IDEMPOTENCY_CONFLICT",
}


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )


def _map_benchmark_error(exc: BenchmarkError) -> HTTPException:
    if exc.code == "NOT_FOUND":
        return _http_error(404, exc.code, exc.message)
    if exc.code in _CONFLICT_CODES:
        return _http_error(409, exc.code, exc.message)
    return _http_error(400, exc.code, exc.message)


class BenchmarkThresholdProfileIn(BaseModel):
    """Runtime threshold profile — mirrors benchmark-threshold-profile.schema.json."""

    model_config = ConfigDict(extra="forbid")

    profile_code: str = Field(min_length=1)
    algorithm_version: str = Field(min_length=1)
    max_missing_output_rate: float = Field(ge=0, le=1)
    max_mean_abs_score_error: float = Field(ge=0)
    min_exact_score_agreement_rate: float = Field(ge=0, le=1)
    min_taxonomy_agreement_rate: float = Field(ge=0, le=1)
    max_safety_invariant_failure_rate: float = Field(ge=0, le=1)
    score_tolerance: float = Field(ge=0)


class BenchmarkDatasetCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)


class BenchmarkVersionCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold_profile_snapshot: BenchmarkThresholdProfileIn | None = None


class BenchmarkCaseCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    published_result_id: uuid.UUID
    question_evaluation_id: uuid.UUID


class BenchmarkRegressionRunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_provider: str = Field(min_length=1, max_length=100)
    candidate_model: str = Field(min_length=1, max_length=100)
    candidate_model_version: str = Field(min_length=1, max_length=100)
    candidate_prompt_template_version: str = Field(min_length=1, max_length=100)
    candidate_config: dict[str, Any] | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


@router.get("/quality/benchmark-datasets")
async def get_benchmark_datasets(
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    return await list_datasets(db, tenant_id=auth.tenant_id)


@router.post("/quality/benchmark-datasets")
async def post_benchmark_dataset(
    body: BenchmarkDatasetCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await create_dataset(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            code=body.code,
            title=body.title,
            description=body.description,
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/benchmark-datasets/{dataset_id}")
async def get_benchmark_dataset(
    dataset_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await get_dataset(
            db, tenant_id=auth.tenant_id, dataset_id=dataset_id
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc


@router.get("/quality/benchmark-datasets/{dataset_id}/versions")
async def get_benchmark_dataset_versions(
    dataset_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await list_versions(
            db, tenant_id=auth.tenant_id, dataset_id=dataset_id
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc


@router.post("/quality/benchmark-datasets/{dataset_id}/versions")
async def post_benchmark_dataset_version(
    dataset_id: uuid.UUID,
    body: BenchmarkVersionCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await create_version(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            dataset_id=dataset_id,
            threshold_profile_snapshot=(
                body.threshold_profile_snapshot.model_dump()
                if body.threshold_profile_snapshot is not None
                else None
            ),
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/benchmark-versions/{version_id}")
async def get_benchmark_version(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await get_version(
            db, tenant_id=auth.tenant_id, version_id=version_id
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc


@router.get("/quality/benchmark-versions/{version_id}/eligible-sources")
async def get_benchmark_eligible_sources(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await list_eligible_sources(
            db, tenant_id=auth.tenant_id, version_id=version_id
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc


@router.get("/quality/benchmark-versions/{version_id}/cases")
async def get_benchmark_cases(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await list_cases(
            db, tenant_id=auth.tenant_id, version_id=version_id
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc


@router.post("/quality/benchmark-versions/{version_id}/cases")
async def post_benchmark_case(
    version_id: uuid.UUID,
    body: BenchmarkCaseCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await add_case(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            version_id=version_id,
            published_result_id=body.published_result_id,
            question_evaluation_id=body.question_evaluation_id,
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc
    await db.commit()
    return result


@router.delete("/quality/benchmark-versions/{version_id}/cases/{case_id}")
async def delete_benchmark_case(
    version_id: uuid.UUID,
    case_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await remove_case(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            version_id=version_id,
            case_id=case_id,
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc
    await db.commit()
    return result


@router.post("/quality/benchmark-versions/{version_id}/lock")
async def post_benchmark_version_lock(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await lock_version(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            version_id=version_id,
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/benchmark-versions/{version_id}/regression-runs")
async def get_benchmark_regression_runs(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await list_runs(
            db, tenant_id=auth.tenant_id, version_id=version_id
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc


@router.post("/quality/benchmark-versions/{version_id}/regression-runs")
async def post_benchmark_regression_run(
    version_id: uuid.UUID,
    body: BenchmarkRegressionRunCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:manage")),
) -> dict[str, Any]:
    try:
        result = await start_regression_run(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            version_id=version_id,
            candidate_provider=body.candidate_provider,
            candidate_model=body.candidate_model,
            candidate_model_version=body.candidate_model_version,
            candidate_prompt_template_version=body.candidate_prompt_template_version,
            candidate_config=body.candidate_config,
            idempotency_key=body.idempotency_key,
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc
    await db.commit()
    return result


@router.get("/quality/regression-runs/{run_id}")
async def get_benchmark_regression_run(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await get_run(db, tenant_id=auth.tenant_id, run_id=run_id)
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc


@router.get("/quality/regression-runs/{run_id}/case-results")
async def get_benchmark_regression_case_results(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        return await list_case_results(
            db, tenant_id=auth.tenant_id, run_id=run_id
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc


@router.get("/quality/regression-runs/{run_id}/gate")
async def get_benchmark_release_gate(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("quality:read")),
) -> dict[str, Any]:
    try:
        result = await evaluate_release_gate(
            db,
            tenant_id=auth.tenant_id,
            run_id=run_id,
            actor_user_id=auth.user_id,
        )
    except BenchmarkError as exc:
        raise _map_benchmark_error(exc) from exc
    await db.commit()
    return result
