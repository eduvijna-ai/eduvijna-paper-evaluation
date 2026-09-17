# ruff: noqa: E501
"""SCIM 2.0 Users provisioning (create/read/patch/deactivate)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EnterpriseIdentityProvider, ExternalUserIdentity, User
from app.services.audit import add_audit_event
from app.services.webhooks import record_outbound_event


def user_to_scim(user: User, *, external_id: str | None = None) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "externalId": external_id,
        "userName": user.email,
        "displayName": user.display_name,
        "active": user.status == "active",
        "emails": [{"value": user.email, "primary": True}],
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat() if user.created_at else None,
            "lastModified": user.updated_at.isoformat() if user.updated_at else None,
        },
    }


async def _scim_provider(db: AsyncSession, *, tenant_id: uuid.UUID) -> EnterpriseIdentityProvider:
    issuer = f"scim://{tenant_id}"
    provider = await db.scalar(
        select(EnterpriseIdentityProvider).where(
            EnterpriseIdentityProvider.tenant_id == tenant_id,
            EnterpriseIdentityProvider.issuer == issuer,
        )
    )
    if provider is None:
        provider = EnterpriseIdentityProvider(
            tenant_id=tenant_id,
            name="SCIM Binding",
            protocol="OIDC",
            enabled=False,
            issuer=issuer,
            jit_enabled=False,
            account_linking_policy="NONE",
            status="DISABLED",
        )
        db.add(provider)
        await db.flush()
    return provider


async def _identity_for_user(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> ExternalUserIdentity | None:
    provider = await _scim_provider(db, tenant_id=tenant_id)
    identity: ExternalUserIdentity | None = await db.scalar(
        select(ExternalUserIdentity).where(
            ExternalUserIdentity.tenant_id == tenant_id,
            ExternalUserIdentity.provider_id == provider.id,
            ExternalUserIdentity.user_id == user_id,
        )
    )
    return identity


def _parse_filter(filter_expr: str) -> tuple[str, str] | None:
    lowered = filter_expr.strip()
    for attr in ("userName", "externalId"):
        needle = f"{attr} eq"
        if needle.lower() in lowered.lower():
            parts = lowered.split("eq", 1)
            value = parts[1].strip().strip('"').strip("'")
            return attr, value
    return None


async def scim_list_users(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    filter_expr: str | None = None,
    start_index: int = 1,
    count: int = 100,
) -> dict[str, Any]:
    query = select(User).where(User.tenant_id == tenant_id)
    if filter_expr:
        parsed = _parse_filter(filter_expr)
        if parsed:
            attr, value = parsed
            if attr == "userName":
                query = query.where(User.email == value.strip().lower())
            else:
                provider = await _scim_provider(db, tenant_id=tenant_id)
                identities = list(
                    await db.scalars(
                        select(ExternalUserIdentity).where(
                            ExternalUserIdentity.tenant_id == tenant_id,
                            ExternalUserIdentity.provider_id == provider.id,
                            ExternalUserIdentity.external_subject == value,
                        )
                    )
                )
                user_ids = [row.user_id for row in identities]
                if not user_ids:
                    return {
                        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                        "totalResults": 0,
                        "startIndex": start_index,
                        "itemsPerPage": 0,
                        "Resources": [],
                    }
                query = query.where(User.id.in_(user_ids))
    rows = list(await db.scalars(query.order_by(User.created_at)))
    start = max(start_index - 1, 0)
    page = rows[start : start + count]
    resources = []
    for user in page:
        identity = await _identity_for_user(db, tenant_id=tenant_id, user_id=user.id)
        resources.append(
            user_to_scim(user, external_id=identity.external_subject if identity else None)
        )
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(rows),
        "startIndex": start_index,
        "itemsPerPage": len(page),
        "Resources": resources,
    }


async def scim_get_user(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any]:
    user = await db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    if user is None:
        raise HTTPException(
            404,
            detail={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "User not found",
                "status": "404",
            },
        )
    identity = await _identity_for_user(db, tenant_id=tenant_id, user_id=user.id)
    return user_to_scim(user, external_id=identity.external_subject if identity else None)


async def _bind_external(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user: User,
    external_id: str | None,
) -> None:
    if not external_id:
        return
    provider = await _scim_provider(db, tenant_id=tenant_id)
    current = await db.scalar(
        select(ExternalUserIdentity).where(
            ExternalUserIdentity.tenant_id == tenant_id,
            ExternalUserIdentity.provider_id == provider.id,
            ExternalUserIdentity.user_id == user.id,
        )
    )
    if current is not None:
        if current.external_subject != external_id:
            raise HTTPException(409, detail="immutable external identity cannot be replaced")
        current.external_email = user.email
        await db.flush()
        return
    existing = await db.scalar(
        select(ExternalUserIdentity).where(
            ExternalUserIdentity.tenant_id == tenant_id,
            ExternalUserIdentity.provider_id == provider.id,
            ExternalUserIdentity.external_subject == external_id,
        )
    )
    if existing is None:
        db.add(
            ExternalUserIdentity(
                tenant_id=tenant_id,
                provider_id=provider.id,
                user_id=user.id,
                protocol="OIDC",
                external_subject=external_id,
                issuer=provider.issuer or f"scim://{tenant_id}",
                external_email=user.email,
                last_authenticated_at=None,
            )
        )
        await db.flush()
        return
    if existing.user_id != user.id:
        raise HTTPException(409, detail="externalId already bound")
    existing.external_email = user.email
    await db.flush()


async def scim_create_user(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    email = str(payload.get("userName") or "").strip().lower()
    if not email:
        emails = payload.get("emails") or []
        if emails and isinstance(emails[0], dict):
            email = str(emails[0].get("value") or "").strip().lower()
    display_name = str(payload.get("displayName") or email)
    if not email:
        raise HTTPException(400, detail="userName required")
    external_id = str(payload.get("externalId") or "").strip()
    if not external_id:
        raise HTTPException(
            400,
            detail={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "externalId is required for durable SCIM identity",
                "status": "400",
                "scimType": "invalidValue",
            },
        )
    if external_id.lower() == email:
        raise HTTPException(
            400,
            detail={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": "externalId must not be the user email address",
                "status": "400",
                "scimType": "invalidValue",
            },
        )
    provider = await _scim_provider(db, tenant_id=tenant_id)
    by_external = await db.scalar(
        select(ExternalUserIdentity).where(
            ExternalUserIdentity.tenant_id == tenant_id,
            ExternalUserIdentity.provider_id == provider.id,
            ExternalUserIdentity.external_subject == external_id,
        )
    )
    existing = await db.scalar(select(User).where(User.tenant_id == tenant_id, User.email == email))
    if by_external is not None:
        existing = await db.scalar(
            select(User).where(User.id == by_external.user_id, User.tenant_id == tenant_id)
        )
    active = bool(payload.get("active", True))
    if existing is not None:
        existing.display_name = display_name[:255]
        if active and existing.status != "active":
            existing.status = "active"
        elif not active and existing.status == "active":
            existing.status = "inactive"
            existing.auth_version = int(existing.auth_version) + 1
        await _bind_external(db, tenant_id=tenant_id, user=existing, external_id=external_id)
        await db.flush()
        identity = await _identity_for_user(db, tenant_id=tenant_id, user_id=existing.id)
        await db.refresh(existing)
        return user_to_scim(existing, external_id=identity.external_subject if identity else external_id)

    user = User(
        tenant_id=tenant_id,
        email=email,
        display_name=display_name[:255],
        status="active" if active else "inactive",
        password_hash=None,
        auth_version=1,
    )
    db.add(user)
    await db.flush()
    await _bind_external(db, tenant_id=tenant_id, user=user, external_id=external_id)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=None,
        entity_type="user",
        entity_id=user.id,
        action="scim_created",
        after={"email": user.email, "status": user.status, "external_id": external_id},
    )
    await record_outbound_event(
        db,
        tenant_id=tenant_id,
        event_type="identity.user.provisioned",
        source_entity_type="user",
        source_entity_id=user.id,
        payload={"email": user.email, "status": user.status},
    )
    await db.refresh(user)
    return user_to_scim(user, external_id=external_id)


async def scim_replace_user(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    user = await db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    if user is None:
        raise HTTPException(404, detail="User not found")
    before = {"email": user.email, "status": user.status, "auth_version": user.auth_version}
    if "userName" in payload:
        user.email = str(payload["userName"]).strip().lower()
    if "displayName" in payload:
        user.display_name = str(payload["displayName"])[:255]
    if "externalId" in payload:
        await _bind_external(db, tenant_id=tenant_id, user=user, external_id=str(payload["externalId"]))
    if "active" in payload:
        active = bool(payload["active"])
        if not active and user.status == "active":
            user.status = "inactive"
            user.auth_version = int(user.auth_version) + 1
            await record_outbound_event(
                db,
                tenant_id=tenant_id,
                event_type="identity.user.deactivated",
                source_entity_type="user",
                source_entity_id=user.id,
                payload={"email": user.email},
            )
        elif active:
            user.status = "active"
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=None,
        entity_type="user",
        entity_id=user.id,
        action="scim_replaced",
        before=before,
        after={"email": user.email, "status": user.status, "auth_version": user.auth_version},
    )
    identity = await _identity_for_user(db, tenant_id=tenant_id, user_id=user.id)
    await db.refresh(user)
    return user_to_scim(user, external_id=identity.external_subject if identity else None)


async def scim_patch_user(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    user = await db.scalar(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    if user is None:
        raise HTTPException(404, detail="User not found")
    before = {"email": user.email, "status": user.status, "auth_version": user.auth_version}
    for op in payload.get("Operations") or []:
        path = str(op.get("path") or "").lower()
        operation = str(op.get("op") or "").lower()
        value = op.get("value")
        if operation not in {"replace", "add"}:
            continue
        if path == "active" or (isinstance(value, dict) and "active" in value) or path == "":
            active_value = value if path == "active" else (value.get("active") if isinstance(value, dict) else None)
            if active_value is not None:
                active = bool(active_value)
                if not active and user.status == "active":
                    user.status = "inactive"
                    user.auth_version = int(user.auth_version) + 1
                    await record_outbound_event(
                        db,
                        tenant_id=tenant_id,
                        event_type="identity.user.deactivated",
                        source_entity_type="user",
                        source_entity_id=user.id,
                        payload={"email": user.email},
                    )
                elif active:
                    user.status = "active"
        if path == "displayname" or (isinstance(value, dict) and "displayName" in value):
            user.display_name = str(value if path == "displayname" else value["displayName"])[:255]
        if path == "username" or (isinstance(value, dict) and "userName" in value):
            user.email = str(value if path == "username" else value["userName"]).strip().lower()
        if path == "externalid" or (isinstance(value, dict) and "externalId" in value):
            await _bind_external(
                db,
                tenant_id=tenant_id,
                user=user,
                external_id=str(value if path == "externalid" else value["externalId"]),
            )
    user.updated_at = datetime.now(UTC)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=None,
        entity_type="user",
        entity_id=user.id,
        action="scim_patched",
        before=before,
        after={"email": user.email, "status": user.status, "auth_version": user.auth_version},
    )
    identity = await _identity_for_user(db, tenant_id=tenant_id, user_id=user.id)
    await db.refresh(user)
    return user_to_scim(user, external_id=identity.external_subject if identity else None)


def service_provider_config() -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter": {"supported": True, "maxResults": 200},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Tenant-scoped SCIM integration credential",
            }
        ],
    }


def resource_types() -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 1,
        "Resources": [
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
                "id": "User",
                "name": "User",
                "endpoint": "/scim/v2/Users",
                "schema": "urn:ietf:params:scim:schemas:core:2.0:User",
            }
        ],
    }
