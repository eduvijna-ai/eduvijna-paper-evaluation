"""Integration credential lifecycle (machine API / SCIM auth)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.integration_crypto import (
    generate_integration_secret,
    hash_integration_secret,
    verify_integration_secret,
)
from app.db.models import IntegrationCredential
from app.services.audit import add_audit_event


def _safe_credential_payload(cred: IntegrationCredential) -> dict[str, Any]:
    return {
        "id": str(cred.id),
        "name": cred.name,
        "key_prefix": cred.key_prefix,
        "scopes": list(cred.scopes_json or []),
        "enabled": cred.enabled,
        "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
        "revoked_at": cred.revoked_at.isoformat() if cred.revoked_at else None,
    }


async def create_credential(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    scopes: list[str],
    expires_at: datetime | None = None,
) -> tuple[IntegrationCredential, str]:
    secret = generate_integration_secret()
    prefix = secret[:12]
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        name=name.strip(),
        key_prefix=prefix,
        secret_hash=hash_integration_secret(secret),
        scopes_json=sorted(set(scopes)),
        enabled=True,
        expires_at=expires_at,
        created_by=actor_user_id,
    )
    db.add(cred)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="integration_credential",
        entity_id=cred.id,
        action="created",
        after=_safe_credential_payload(cred),
    )
    return cred, secret


async def list_credentials(
    db: AsyncSession, *, tenant_id: uuid.UUID
) -> list[IntegrationCredential]:
    rows = await db.scalars(
        select(IntegrationCredential)
        .where(IntegrationCredential.tenant_id == tenant_id)
        .order_by(IntegrationCredential.created_at.desc())
    )
    return list(rows)


async def rotate_credential(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    credential_id: uuid.UUID,
) -> tuple[IntegrationCredential, str]:
    cred = await db.scalar(
        select(IntegrationCredential).where(
            IntegrationCredential.id == credential_id,
            IntegrationCredential.tenant_id == tenant_id,
        )
    )
    if cred is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Credential not found"})
    secret = generate_integration_secret()
    before = _safe_credential_payload(cred)
    cred.key_prefix = secret[:12]
    cred.secret_hash = hash_integration_secret(secret)
    cred.revoked_at = None
    cred.enabled = True
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="integration_credential",
        entity_id=cred.id,
        action="rotated",
        before=before,
        after=_safe_credential_payload(cred),
    )
    return cred, secret


async def revoke_credential(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    credential_id: uuid.UUID,
) -> IntegrationCredential:
    cred = await db.scalar(
        select(IntegrationCredential).where(
            IntegrationCredential.id == credential_id,
            IntegrationCredential.tenant_id == tenant_id,
        )
    )
    if cred is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Credential not found"})
    before = _safe_credential_payload(cred)
    cred.enabled = False
    cred.revoked_at = datetime.now(UTC)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="integration_credential",
        entity_id=cred.id,
        action="revoked",
        before=before,
        after=_safe_credential_payload(cred),
    )
    return cred


async def authenticate_integration_credential(
    db: AsyncSession,
    *,
    raw_secret: str,
    required_scopes: set[str] | None = None,
) -> IntegrationCredential:
    if not raw_secret or len(raw_secret) < 12:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "Invalid integration credential"},
        )
    prefix = raw_secret[:12]
    candidates = list(
        await db.scalars(
            select(IntegrationCredential).where(IntegrationCredential.key_prefix == prefix)
        )
    )
    matched: IntegrationCredential | None = None
    for cred in candidates:
        if verify_integration_secret(raw_secret, cred.secret_hash):
            matched = cred
            break
    if matched is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "Invalid integration credential"},
        )
    now = datetime.now(UTC)
    if not matched.enabled or matched.revoked_at is not None:
        raise HTTPException(
            status_code=401,
            detail={"code": "credential_revoked", "message": "Integration credential revoked"},
        )
    if matched.expires_at is not None and matched.expires_at <= now:
        raise HTTPException(
            status_code=401,
            detail={"code": "credential_expired", "message": "Integration credential expired"},
        )
    scopes = set(matched.scopes_json or [])
    if required_scopes and not required_scopes.issubset(scopes):
        raise HTTPException(
            status_code=403,
            detail={"code": "insufficient_scope", "message": "Missing required scopes"},
        )
    matched.last_used_at = now
    await db.flush()
    return matched
