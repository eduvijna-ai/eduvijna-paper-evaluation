# ruff: noqa: B008, E501
"""LTI 1.3 login initiation, launch, and public tool JWKS."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import LtiPlatform
from app.db.session import get_db_session
from app.services.lti import complete_lti_launch, start_lti_login, tool_jwks_for_platform

router = APIRouter(tags=["enterprise-identity"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/lti/login")
@router.post("/lti/login")
async def lti_login(
    db: Db,
    iss: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    login_hint: str | None = Query(default=None),
    target_link_uri: str | None = Query(default=None),
    lti_message_hint: str | None = Query(default=None),
    lti_deployment_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not iss or not client_id or not target_link_uri:
        raise HTTPException(400, detail={"code": "invalid_login", "message": "Missing LTI login fields"})
    url = await start_lti_login(
        db,
        iss=iss,
        client_id=client_id,
        login_hint=login_hint,
        target_link_uri=target_link_uri,
        lti_message_hint=lti_message_hint,
        lti_deployment_id=lti_deployment_id,
        settings=settings,
    )
    await db.commit()
    return RedirectResponse(url, status_code=302)


@router.post("/lti/launch")
async def lti_launch(
    db: Db,
    id_token: str = Form(...),
    state: str = Form(...),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    result = await complete_lti_launch(db, id_token=id_token, state=state, settings=settings)
    await db.commit()
    return result


@router.get("/lti/jwks/{platform_id}")
async def public_tool_jwks(platform_id: uuid.UUID, db: Db) -> dict[str, Any]:
    platform = await db.scalar(select(LtiPlatform).where(LtiPlatform.id == platform_id))
    if platform is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Platform not found"})
    return tool_jwks_for_platform(platform)
