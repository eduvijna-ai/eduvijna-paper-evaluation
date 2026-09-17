# ruff: noqa: B008, E501
"""Public enterprise SSO start / callback / exchange."""

from __future__ import annotations

import uuid
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import AuthProvider, get_auth_provider
from app.db.models import Tenant
from app.db.session import get_db_session
from app.services.enterprise_identity import exchange_sso_code, list_providers, provider_public_dict
from app.services.oidc_sso import complete_oidc_callback, start_oidc_login
from app.services.saml_sso import process_saml_response, start_saml_login
from app.services.webhooks import deliver_due_webhooks

router = APIRouter(tags=["enterprise-identity"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


class ExchangeIn(BaseModel):
    exchange_code: str


async def _tenant_by_slug(db: AsyncSession, tenant_slug: str) -> Tenant:
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug, Tenant.status == "active"))
    if tenant is None:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Unknown institution"})
    return tenant


def _error_redirect(settings: Settings, code: str) -> RedirectResponse:
    return RedirectResponse(
        f"{settings.frontend_base_url.rstrip('/')}/sso/complete?error={quote(code)}",
        status_code=302,
    )


@router.get("/sso/providers")
async def public_providers(tenant_slug: str, db: Db) -> dict[str, Any]:
    tenant = await _tenant_by_slug(db, tenant_slug)
    rows = await list_providers(db, tenant_id=tenant.id)
    return {
        "items": [
            {
                "id": provider_public_dict(row)["id"],
                "name": row.name,
                "protocol": row.protocol,
                "enabled": row.enabled,
            }
            for row in rows
            if row.enabled
        ]
    }


@router.get("/sso/oidc/start")
async def oidc_start(
    tenant_slug: str,
    provider_id: uuid.UUID,
    db: Db,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    tenant = await _tenant_by_slug(db, tenant_slug)
    started = await start_oidc_login(
        db, tenant_id=tenant.id, provider_id=provider_id, settings=settings
    )
    await db.commit()
    return RedirectResponse(started["authorize_url"], status_code=302)


@router.get("/sso/oidc/callback")
@router.post("/sso/oidc/callback")
async def oidc_callback(
    db: Db,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not code or not state:
        return _error_redirect(settings, "invalid_state")
    try:
        result = await complete_oidc_callback(db, code=code, state=state, settings=settings)
        await db.commit()
        await deliver_due_webhooks(db, settings=settings)
        await db.commit()
        return RedirectResponse(result["redirect_url"], status_code=302)
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        return _error_redirect(settings, str(detail.get("code") or "sso_rejected"))


@router.get("/sso/saml/start")
async def saml_start(
    tenant_slug: str,
    provider_id: uuid.UUID,
    db: Db,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    tenant = await _tenant_by_slug(db, tenant_slug)
    started = await start_saml_login(
        db, tenant_id=tenant.id, provider_id=provider_id, settings=settings
    )
    await db.commit()
    return RedirectResponse(started["redirect_url"], status_code=302)


@router.post("/sso/saml/acs")
async def saml_acs(
    db: Db,
    SAMLResponse: str = Form(...),
    RelayState: str | None = Form(default=None),
    tenant_slug: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    tenant_id = None
    if tenant_slug:
        tenant_id = (await _tenant_by_slug(db, tenant_slug)).id
    try:
        result = await process_saml_response(
            db,
            saml_response_b64=SAMLResponse,
            relay_state=RelayState,
            tenant_id=tenant_id,
            settings=settings,
        )
        await db.commit()
        await deliver_due_webhooks(db, settings=settings)
        await db.commit()
        return RedirectResponse(result["redirect_url"], status_code=302)
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        return _error_redirect(settings, str(detail.get("code") or "sso_rejected"))


@router.post("/sso/exchange")
async def sso_exchange(
    payload: ExchangeIn,
    db: Db,
    provider: AuthProvider = Depends(get_auth_provider),
) -> dict[str, Any]:
    token, ttl, user, context = await exchange_sso_code(
        db, exchange_code=payload.exchange_code, provider=provider
    )
    await db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ttl,
        "user": {
            "id": str(user.id),
            "tenant_id": str(user.tenant_id),
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status,
            "roles": sorted(context.roles),
            "permissions": sorted(context.permissions),
        },
    }
