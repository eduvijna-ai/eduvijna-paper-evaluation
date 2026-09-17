# ruff: noqa: B008
"""B19 admin integration APIs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.core.config import Settings, get_settings
from app.db.models import (
    GradePassback,
    LtiPlatform,
    LtiResourceLink,
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookEndpoint,
)
from app.db.session import get_db_session
from app.services.enterprise_identity import (
    create_provider,
    get_provider,
    list_providers,
    provider_public_dict,
    update_provider,
)
from app.services.grade_passback import request_grade_passback, serialize_passback
from app.services.integration_credentials import (
    create_credential,
    list_credentials,
    revoke_credential,
    rotate_credential,
)
from app.services.lti import create_lti_platform, serialize_platform, tool_jwks_for_platform
from app.services.roster import serialize_sync_run, sync_nrps_memberships, upsert_roster_members
from app.services.webhooks import (
    create_webhook_endpoint,
    enqueue_webhook_dispatch,
    retry_delivery,
    rotate_webhook_secret,
    serialize_delivery,
    update_webhook_endpoint,
    webhook_public_dict,
)

router = APIRouter(tags=["enterprise-identity"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


class ProviderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    protocol: str
    issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    jwks_uri: str | None = None
    metadata_url: str | None = None
    entity_id: str | None = None
    sso_url: str | None = None
    saml_idp_cert: str | None = None
    jit_enabled: bool = False
    account_linking_policy: str = "NONE"
    role_mapping_json: dict[str, Any] = Field(default_factory=dict)
    config_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ProviderPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    enabled: bool | None = None
    issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    jwks_uri: str | None = None
    metadata_url: str | None = None
    entity_id: str | None = None
    sso_url: str | None = None
    saml_idp_cert: str | None = None
    jit_enabled: bool | None = None
    account_linking_policy: str | None = None
    role_mapping_json: dict[str, Any] | None = None
    config_json: dict[str, Any] | None = None
    status: str | None = None


class LtiPlatformIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    issuer: str
    client_id: str
    deployment_id: str
    auth_login_url: str
    token_url: str
    jwks_url: str
    role_mapping_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class RosterSyncIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_key: str
    members: list[dict[str, Any]] = Field(default_factory=list)
    resource_link_id: uuid.UUID | None = None
    source: str = "SIS"


class GradePassbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published_result_id: uuid.UUID
    resource_link_id: uuid.UUID
    external_user_id: str | None = None
    score: float | None = None


class CredentialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    scopes: list[str]
    expires_at: datetime | None = None


class WebhookIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    destination_url: str
    event_types: list[str]


class WebhookPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    destination_url: str | None = None
    event_types: list[str] | None = None
    enabled: bool | None = None


def _cred_public(cred: Any, secret: str | None = None) -> dict[str, Any]:
    payload = {
        "id": str(cred.id),
        "name": cred.name,
        "key_prefix": cred.key_prefix,
        "scopes": list(cred.scopes_json or []),
        "enabled": cred.enabled,
        "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
        "revoked_at": cred.revoked_at.isoformat() if cred.revoked_at else None,
        "last_used_at": cred.last_used_at.isoformat() if cred.last_used_at else None,
    }
    if secret:
        payload["secret"] = secret
    return payload


@router.get("/integrations/identity-providers")
async def list_identity_providers(
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    rows = await list_providers(db, tenant_id=auth.tenant_id)
    return {"items": [provider_public_dict(row) for row in rows]}


@router.post("/integrations/identity-providers")
async def create_identity_provider(
    payload: ProviderIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:manage")),
) -> dict[str, Any]:
    provider = await create_provider(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        **payload.model_dump(),
    )
    await db.commit()
    return provider_public_dict(provider)


@router.patch("/integrations/identity-providers/{provider_id}")
async def patch_identity_provider(
    provider_id: uuid.UUID,
    payload: ProviderPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:manage")),
) -> dict[str, Any]:
    provider = await update_provider(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        provider_id=provider_id,
        patch=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    return provider_public_dict(provider)


@router.post("/integrations/identity-providers/{provider_id}/scim-token")
async def create_scim_token(
    provider_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:credentials:manage")),
) -> dict[str, Any]:
    await get_provider(db, tenant_id=auth.tenant_id, provider_id=provider_id)
    cred, secret = await create_credential(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        name=f"scim:{provider_id}",
        scopes=["scim"],
    )
    await db.commit()
    return {**_cred_public(cred, secret), "scim_base_url": "/scim/v2"}


@router.get("/integrations/lti-platforms")
async def list_lti_platforms(
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    rows = list(
        await db.scalars(
            select(LtiPlatform)
            .where(LtiPlatform.tenant_id == auth.tenant_id)
            .order_by(LtiPlatform.name)
        )
    )
    return {"items": [serialize_platform(row) for row in rows]}


@router.post("/integrations/lti-platforms")
async def create_platform(
    payload: LtiPlatformIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:manage")),
) -> dict[str, Any]:
    platform = await create_lti_platform(
        db, tenant_id=auth.tenant_id, actor_user_id=auth.user_id, **payload.model_dump()
    )
    await db.commit()
    return serialize_platform(platform)


@router.get("/integrations/lti-platforms/{platform_id}/tool-jwks")
async def get_tool_jwks(
    platform_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    platform = await db.scalar(
        select(LtiPlatform).where(
            LtiPlatform.id == platform_id, LtiPlatform.tenant_id == auth.tenant_id
        )
    )
    if platform is None:
        from fastapi import HTTPException

        raise HTTPException(404, detail={"code": "not_found", "message": "Platform not found"})
    return tool_jwks_for_platform(platform)


@router.get("/integrations/lti-resource-links")
async def list_resource_links(
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    rows = list(
        await db.scalars(
            select(LtiResourceLink).where(LtiResourceLink.tenant_id == auth.tenant_id)
        )
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "platform_id": str(row.platform_id),
                "context_id": row.context_id,
                "resource_link_id": row.resource_link_id,
                "assessment_id": str(row.assessment_id) if row.assessment_id else None,
                "ags_lineitem_url": row.ags_lineitem_url,
                "nrps_memberships_url": row.nrps_memberships_url,
                "last_launch_at": row.last_launch_at.isoformat() if row.last_launch_at else None,
            }
            for row in rows
        ]
    }


@router.post("/integrations/roster-sync")
async def start_roster_sync(
    payload: RosterSyncIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:roster:sync")),
) -> dict[str, Any]:
    if payload.resource_link_id:
        run = await sync_nrps_memberships(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            resource_link_id=payload.resource_link_id,
        )
    else:
        run = await upsert_roster_members(
            db,
            tenant_id=auth.tenant_id,
            provider_key=payload.provider_key,
            members=payload.members,
            actor_user_id=auth.user_id,
            source=payload.source,
        )
    await db.commit()
    await enqueue_webhook_dispatch()
    return serialize_sync_run(run)


@router.get("/integrations/roster-sync/{run_id}")
async def get_roster_sync(
    run_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    from fastapi import HTTPException

    from app.db.models import RosterSyncRun

    run = await db.scalar(
        select(RosterSyncRun).where(
            RosterSyncRun.id == run_id, RosterSyncRun.tenant_id == auth.tenant_id
        )
    )
    if run is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Sync run not found"})
    return serialize_sync_run(run)


@router.get("/integrations/grade-passbacks")
async def list_passbacks(
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    rows = list(
        await db.scalars(
            select(GradePassback)
            .where(GradePassback.tenant_id == auth.tenant_id)
            .order_by(GradePassback.created_at.desc())
        )
    )
    return {"items": [serialize_passback(row) for row in rows]}


@router.post("/integrations/grade-passbacks")
async def create_passback(
    payload: GradePassbackIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:grade:passback")),
) -> dict[str, Any]:
    row = await request_grade_passback(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        published_result_id=payload.published_result_id,
        resource_link_id=payload.resource_link_id,
        external_user_id=payload.external_user_id,
        requested_score=None if payload.score is None else payload.score,  # type: ignore[arg-type]
    )
    await db.commit()
    return serialize_passback(row)


@router.get("/integrations/credentials")
async def list_creds(
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    rows = await list_credentials(db, tenant_id=auth.tenant_id)
    return {"items": [_cred_public(row) for row in rows]}


@router.post("/integrations/credentials")
async def create_cred(
    payload: CredentialIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:credentials:manage")),
) -> dict[str, Any]:
    cred, secret = await create_credential(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        name=payload.name,
        scopes=payload.scopes,
        expires_at=payload.expires_at,
    )
    await db.commit()
    return _cred_public(cred, secret)


@router.post("/integrations/credentials/{credential_id}/rotate")
async def rotate_cred(
    credential_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:credentials:manage")),
) -> dict[str, Any]:
    cred, secret = await rotate_credential(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        credential_id=credential_id,
    )
    await db.commit()
    return _cred_public(cred, secret)


@router.post("/integrations/credentials/{credential_id}/revoke")
async def revoke_cred(
    credential_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:credentials:manage")),
) -> dict[str, Any]:
    cred = await revoke_credential(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        credential_id=credential_id,
    )
    await db.commit()
    return _cred_public(cred)


@router.get("/integrations/webhooks")
async def list_webhooks(
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    rows = list(
        await db.scalars(
            select(WebhookEndpoint).where(WebhookEndpoint.tenant_id == auth.tenant_id)
        )
    )
    return {"items": [webhook_public_dict(row) for row in rows]}


@router.post("/integrations/webhooks")
async def create_webhook(
    payload: WebhookIn,
    db: Db,
    settings: Settings = Depends(get_settings),
    auth: AuthContext = Depends(require_permissions("integration:webhook:manage")),
) -> dict[str, Any]:
    endpoint, secret = await create_webhook_endpoint(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        name=payload.name,
        destination_url=payload.destination_url,
        event_types=payload.event_types,
        settings=settings,
    )
    await db.commit()
    return {**webhook_public_dict(endpoint), "signing_secret": secret}


@router.patch("/integrations/webhooks/{endpoint_id}")
async def patch_webhook(
    endpoint_id: uuid.UUID,
    payload: WebhookPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:webhook:manage")),
) -> dict[str, Any]:
    endpoint = await update_webhook_endpoint(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        endpoint_id=endpoint_id,
        patch=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    return webhook_public_dict(endpoint)


@router.post("/integrations/webhooks/{endpoint_id}/rotate-secret")
async def rotate_secret(
    endpoint_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:webhook:manage")),
) -> dict[str, Any]:
    endpoint, secret = await rotate_webhook_secret(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        endpoint_id=endpoint_id,
    )
    await db.commit()
    return {**webhook_public_dict(endpoint), "signing_secret": secret}


@router.get("/integrations/webhooks/{endpoint_id}/deliveries")
async def list_deliveries(
    endpoint_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    from fastapi import HTTPException

    endpoint = await db.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id, WebhookEndpoint.tenant_id == auth.tenant_id
        )
    )
    if endpoint is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Webhook not found"})
    rows = list(
        await db.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.endpoint_id == endpoint_id)
            .order_by(WebhookDelivery.created_at.desc())
        )
    )
    return {"items": [serialize_delivery(row) for row in rows]}


@router.get("/integrations/webhook-deliveries/{delivery_id}/attempts")
async def list_delivery_attempts(
    delivery_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:read")),
) -> dict[str, Any]:
    from fastapi import HTTPException

    delivery = await db.scalar(
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .where(WebhookDelivery.id == delivery_id, WebhookEndpoint.tenant_id == auth.tenant_id)
    )
    if delivery is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Delivery not found"})
    rows = list(
        await db.scalars(
            select(WebhookDeliveryAttempt)
            .where(WebhookDeliveryAttempt.delivery_id == delivery.id)
            .order_by(WebhookDeliveryAttempt.attempt_number.asc())
        )
    )
    return {
        "items": [
            {
                "attempt_number": row.attempt_number,
                "attempted_at": row.attempted_at.isoformat() if row.attempted_at else None,
                "http_status": row.http_status,
                "error_sanitized": row.error_sanitized,
                "duration_ms": row.duration_ms,
            }
            for row in rows
        ]
    }


@router.post("/integrations/webhook-deliveries/{delivery_id}/retry")
async def retry_webhook(
    delivery_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("integration:webhook:manage")),
) -> dict[str, Any]:
    delivery = await retry_delivery(
        db,
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        delivery_id=delivery_id,
    )
    await db.commit()
    await enqueue_webhook_dispatch()
    return serialize_delivery(delivery)
