# ruff: noqa: B008, E501
"""Gated B19 test-provider HTTP surface. Disabled unless explicitly enabled."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.models import User
from app.db.session import get_db_session
from app.services.b19_test_providers import (
    issue_lti_id_token,
    issue_oidc_authorize_redirect,
    issue_oidc_tokens,
    issue_saml_response,
    list_ags_scores,
    nrps_memberships,
    oidc_jwks,
    record_ags_score,
    record_webhook,
    require_test_providers,
    reset_test_provider_state,
    saml_idp_cert_pem,
    set_webhook_expected_secret,
    set_webhook_fail_until,
    store_lti_login,
    webhook_inbox,
)

router = APIRouter(tags=["b19-test"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


class WebhookFailIn(BaseModel):
    fail_until_attempt: int = 0
    expected_secret: str | None = None


class LocalPasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)


@router.get("/b19-test/oidc/jwks")
async def test_oidc_jwks(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    require_test_providers(settings)
    return oidc_jwks()


@router.get("/b19-test/oidc/authorize")
async def test_oidc_authorize(
    redirect_uri: str,
    state: str,
    nonce: str,
    client_id: str,
    subject: str = "oidc-user-1",
    email: str = "sso.oidc@demo.eduvijna.local",
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    require_test_providers(settings)
    url = issue_oidc_authorize_redirect(
        redirect_uri=redirect_uri,
        state=state,
        nonce=nonce,
        client_id=client_id,
        subject=subject,
        email=email,
    )
    return RedirectResponse(url, status_code=302)


@router.post("/b19-test/oidc/token")
async def test_oidc_token(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    require_test_providers(settings)
    form = await request.form()
    return issue_oidc_tokens(
        code=str(form.get("code") or ""),
        redirect_uri=str(form.get("redirect_uri") or ""),
        client_id=str(form.get("client_id") or ""),
    )


@router.get("/b19-test/saml/idp-cert")
async def test_saml_cert(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    require_test_providers(settings)
    return {"cert_pem": saml_idp_cert_pem()}


@router.get("/b19-test/saml/sso")
async def test_saml_sso(
    settings: Settings = Depends(get_settings),
    SAMLRequest: str | None = Query(default=None),
    RelayState: str | None = Query(default=None),
    issuer: str = "https://b19-test.example/saml",
    audience: str | None = None,
    name_id: str = "saml-user-1",
    email: str = "sso.saml@demo.eduvijna.local",
    acs_url: str | None = None,
) -> HTMLResponse:
    require_test_providers(settings)
    acs = acs_url or f"{settings.public_base_url.rstrip('/')}/api/v1/sso/saml/acs"
    response = issue_saml_response(
        issuer=issuer,
        audience=audience or f"{settings.public_base_url.rstrip('/')}/saml/sp",
        name_id=name_id,
        email=email,
        in_response_to=RelayState or None,
        recipient=acs,
        destination=acs,
    )
    html = f"""
    <html><body>
    <form method="post" action="{acs}" data-testid="b19-test-saml-form">
      <input type="hidden" name="SAMLResponse" value="{response}"/>
      <input type="hidden" name="RelayState" value="{RelayState or ""}"/>
      <button type="submit">Continue</button>
    </form>
    <script>document.forms[0].submit()</script>
    </body></html>
    """
    return HTMLResponse(html)


@router.get("/b19-test/lti/jwks")
async def test_lti_jwks(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    require_test_providers(settings)
    return oidc_jwks()


@router.get("/b19-test/lti/authorize")
async def test_lti_authorize(
    redirect_uri: str,
    state: str,
    nonce: str,
    client_id: str,
    login_hint: str = "lti-instructor-1",
    target_link_uri: str | None = None,
    lti_deployment_id: str = "deploy-1",
    mismatch_target: bool = False,
    unbound_assessment: bool = False,
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    require_test_providers(settings)
    store_lti_login(state, nonce, redirect_uri)
    issuer = "https://b19-test.example/lti"
    launched_target = target_link_uri or redirect_uri
    if mismatch_target:
        launched_target = "https://evil.example/lti/launch"
    resource_link_id = "res-unbound" if unbound_assessment else "res-1"
    context_id = "ctx-unbound" if unbound_assessment else "ctx-1"
    token = issue_lti_id_token(
        issuer=issuer,
        client_id=client_id,
        deployment_id=lti_deployment_id,
        nonce=nonce,
        subject=login_hint,
        resource_link_id=resource_link_id,
        context_id=context_id,
        lineitem_url=f"{settings.public_base_url.rstrip('/')}/api/v1/b19-test/ags/lineitems/1",
        memberships_url=f"{settings.public_base_url.rstrip('/')}/api/v1/b19-test/nrps/memberships",
        target_link_uri=launched_target,
    )
    html = f"""
    <html><body>
    <form method="post" action="{redirect_uri}">
      <input type="hidden" name="id_token" value="{token}"/>
      <input type="hidden" name="state" value="{state}"/>
      <button type="submit">Launch</button>
    </form>
    <script>document.forms[0].submit()</script>
    </body></html>
    """
    return HTMLResponse(html)


@router.post("/b19-test/lti/token")
async def test_lti_token(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    require_test_providers(settings)
    return {"access_token": "b19-test-ags-token", "token_type": "Bearer", "expires_in": 3600}


@router.get("/b19-test/nrps/memberships")
async def test_nrps(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    require_test_providers(settings)
    return nrps_memberships()


@router.post("/b19-test/ags/lineitems/1/scores")
async def test_ags_score(payload: dict[str, Any], settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    require_test_providers(settings)
    return record_ags_score(payload)


@router.get("/b19-test/ags/scores")
async def test_ags_list(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    require_test_providers(settings)
    return {"items": list_ags_scores()}


@router.post("/b19-test/users/{user_id}/local-password")
async def test_set_local_password(
    user_id: uuid.UUID,
    payload: LocalPasswordIn,
    db: Db,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Gated test-only helper: attach a local password to an existing SCIM-provisioned user."""
    require_test_providers(settings)
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            404, detail={"code": "not_found", "message": "User not found"}
        )
    user.password_hash = hash_password(payload.password)
    await db.commit()
    return {"status": "ok", "user_id": str(user.id)}


@router.post("/b19-test/webhook-receiver")
async def test_webhook_receiver(request: Request, settings: Settings = Depends(get_settings)) -> dict[str, str]:
    require_test_providers(settings)
    raw = (await request.body()).decode("utf-8")
    record_webhook(
        raw_body=raw,
        timestamp=request.headers.get("x-eduvijna-timestamp", ""),
        signature=request.headers.get("x-eduvijna-signature", ""),
        event_id=request.headers.get("x-eduvijna-event-id", ""),
        event_type=request.headers.get("x-eduvijna-event-type", ""),
    )
    return {"status": "ok"}


@router.get("/b19-test/webhook-inbox")
async def test_webhook_inbox(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    require_test_providers(settings)
    return {"items": webhook_inbox()}


@router.post("/b19-test/webhook-receiver/config")
async def test_webhook_config(
    payload: WebhookFailIn, settings: Settings = Depends(get_settings)
) -> dict[str, int]:
    require_test_providers(settings)
    set_webhook_fail_until(payload.fail_until_attempt)
    if payload.expected_secret is not None:
        set_webhook_expected_secret(payload.expected_secret)
    return {"fail_until_attempt": payload.fail_until_attempt}


@router.post("/b19-test/reset")
async def test_reset(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    require_test_providers(settings)
    reset_test_provider_state()
    return {"status": "reset"}


@router.get("/b19-test/ready")
async def test_ready(settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    require_test_providers(settings)
    return {"enabled": True}
