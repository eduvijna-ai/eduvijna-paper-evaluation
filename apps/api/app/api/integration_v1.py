# ruff: noqa: B008
"""Versioned machine-facing integration API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PublishedResult, RosterSyncRun
from app.db.session import get_db_session
from app.services.integration_auth import IntegrationAuthContext, require_integration_scopes
from app.services.roster import serialize_sync_run, upsert_roster_members

router = APIRouter(prefix="/api/integration/v1", tags=["integration-api"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


class RosterUpsertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_key: str
    members: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/health")
async def health(
    auth: IntegrationAuthContext = Depends(require_integration_scopes()),
) -> dict[str, Any]:
    return {
        "status": "ok",
        "tenant_id": str(auth.tenant_id),
        "scopes": sorted(auth.scopes),
    }


@router.post("/roster/upsert")
async def roster_upsert(
    payload: RosterUpsertIn,
    db: Db,
    auth: IntegrationAuthContext = Depends(require_integration_scopes("roster:write")),
) -> dict[str, Any]:
    run = await upsert_roster_members(
        db,
        tenant_id=auth.tenant_id,
        provider_key=payload.provider_key,
        members=payload.members,
        source="SIS",
    )
    await db.commit()
    return serialize_sync_run(run)


@router.get("/roster/syncs/{run_id}")
async def roster_sync_status(
    run_id: uuid.UUID,
    db: Db,
    auth: IntegrationAuthContext = Depends(require_integration_scopes("roster:read")),
) -> dict[str, Any]:
    from fastapi import HTTPException

    run = await db.scalar(
        select(RosterSyncRun).where(
            RosterSyncRun.id == run_id, RosterSyncRun.tenant_id == auth.tenant_id
        )
    )
    if run is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Sync run not found"})
    return serialize_sync_run(run)


@router.get("/results/published")
async def published_results(
    db: Db,
    auth: IntegrationAuthContext = Depends(require_integration_scopes("results:read")),
) -> dict[str, Any]:
    rows = list(
        await db.scalars(
            select(PublishedResult).where(
                PublishedResult.tenant_id == auth.tenant_id,
                PublishedResult.status == "PUBLISHED",
            )
        )
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "version_number": row.version_number,
                "status": row.status,
                "total_score": str(row.total_score),
                "max_total_score": str(row.max_total_score),
                "student_id": str(row.student_id) if row.student_id else None,
                "assessment_id": str(row.assessment_id),
            }
            for row in rows
        ]
    }
