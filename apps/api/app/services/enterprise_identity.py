# ruff: noqa: E501
"""Enterprise identity provider CRUD, identity binding, and SSO exchange."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import ROLE_CODES, ROLE_PERMISSION_MAP, AuthContext
from app.core.integration_crypto import encrypt_secret, hash_opaque_token
from app.core.security import AuthProvider
from app.db.models import (
    AuthTransaction,
    EnterpriseIdentityProvider,
    ExternalUserIdentity,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.services.audit import add_audit_event

SAFE_SSO_ROLE_CODES = frozenset(ROLE_CODES) - {"PLATFORM_ADMIN", "INSTITUTION_ADMIN"}


def provider_public_dict(provider: EnterpriseIdentityProvider) -> dict[str, Any]:
    return {
        "id": str(provider.id),
        "tenant_id": str(provider.tenant_id),
        "name": provider.name,
        "protocol": provider.protocol,
        "enabled": provider.enabled,
        "issuer": provider.issuer,
        "client_id": provider.client_id,
        "authorization_endpoint": provider.authorization_endpoint,
        "token_endpoint": provider.token_endpoint,
        "jwks_uri": provider.jwks_uri,
        "metadata_url": provider.metadata_url,
        "entity_id": provider.entity_id,
        "sso_url": provider.sso_url,
        "jit_enabled": provider.jit_enabled,
        "account_linking_policy": provider.account_linking_policy,
        "role_mapping_json": provider.role_mapping_json or {},
        "status": provider.status,
        "has_client_secret": bool(provider.encrypted_client_secret),
        "has_saml_idp_cert": bool(provider.encrypted_saml_idp_cert),
        "config_json": provider.config_json or {},
    }


async def create_provider(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    protocol: str,
    issuer: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    authorization_endpoint: str | None = None,
    token_endpoint: str | None = None,
    jwks_uri: str | None = None,
    metadata_url: str | None = None,
    entity_id: str | None = None,
    sso_url: str | None = None,
    saml_idp_cert: str | None = None,
    jit_enabled: bool = False,
    account_linking_policy: str = "NONE",
    role_mapping_json: dict[str, Any] | None = None,
    config_json: dict[str, Any] | None = None,
    enabled: bool = True,
) -> EnterpriseIdentityProvider:
    if protocol not in {"OIDC", "SAML"}:
        raise HTTPException(400, detail={"code": "invalid_protocol", "message": "Invalid protocol"})
    if account_linking_policy not in {"NONE", "VERIFIED_EMAIL_EXPLICIT"}:
        raise HTTPException(
            400,
            detail={"code": "invalid_linking_policy", "message": "Invalid account linking policy"},
        )
    provider = EnterpriseIdentityProvider(
        tenant_id=tenant_id,
        name=name.strip(),
        protocol=protocol,
        enabled=enabled,
        issuer=issuer,
        client_id=client_id,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        jwks_uri=jwks_uri,
        metadata_url=metadata_url,
        entity_id=entity_id,
        sso_url=sso_url,
        jit_enabled=jit_enabled,
        account_linking_policy=account_linking_policy,
        role_mapping_json=role_mapping_json or {},
        config_json=config_json or {},
        encrypted_client_secret=encrypt_secret(client_secret) if client_secret else None,
        encrypted_saml_idp_cert=encrypt_secret(saml_idp_cert) if saml_idp_cert else None,
        status="ACTIVE" if enabled else "DISABLED",
    )
    db.add(provider)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="enterprise_identity_provider",
        entity_id=provider.id,
        action="created",
        after=provider_public_dict(provider),
    )
    return provider


async def list_providers(
    db: AsyncSession, *, tenant_id: uuid.UUID
) -> list[EnterpriseIdentityProvider]:
    rows = await db.scalars(
        select(EnterpriseIdentityProvider)
        .where(EnterpriseIdentityProvider.tenant_id == tenant_id)
        .order_by(EnterpriseIdentityProvider.name)
    )
    return list(rows)


async def get_provider(
    db: AsyncSession, *, tenant_id: uuid.UUID, provider_id: uuid.UUID
) -> EnterpriseIdentityProvider:
    provider = await db.scalar(
        select(EnterpriseIdentityProvider).where(
            EnterpriseIdentityProvider.id == provider_id,
            EnterpriseIdentityProvider.tenant_id == tenant_id,
        )
    )
    if provider is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Provider not found"})
    return provider


async def update_provider(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    provider_id: uuid.UUID,
    patch: dict[str, Any],
) -> EnterpriseIdentityProvider:
    provider = await get_provider(db, tenant_id=tenant_id, provider_id=provider_id)
    before = provider_public_dict(provider)
    for field in (
        "name",
        "enabled",
        "issuer",
        "client_id",
        "authorization_endpoint",
        "token_endpoint",
        "jwks_uri",
        "metadata_url",
        "entity_id",
        "sso_url",
        "jit_enabled",
        "account_linking_policy",
        "role_mapping_json",
        "config_json",
        "status",
    ):
        if field in patch and patch[field] is not None:
            setattr(provider, field, patch[field])
    if "client_secret" in patch and patch["client_secret"]:
        provider.encrypted_client_secret = encrypt_secret(str(patch["client_secret"]))
    if "saml_idp_cert" in patch and patch["saml_idp_cert"]:
        provider.encrypted_saml_idp_cert = encrypt_secret(str(patch["saml_idp_cert"]))
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="enterprise_identity_provider",
        entity_id=provider.id,
        action="updated",
        before=before,
        after=provider_public_dict(provider),
    )
    return provider


async def _ensure_role(
    db: AsyncSession, *, tenant_id: uuid.UUID, role_code: str
) -> Role:
    if role_code not in SAFE_SSO_ROLE_CODES:
        raise HTTPException(
            400,
            detail={"code": "invalid_role", "message": f"Role {role_code} cannot be assigned via SSO"},
        )
    role = await db.scalar(
        select(Role).where(Role.tenant_id == tenant_id, Role.code == role_code)
    )
    if role is not None:
        return role
    role = Role(
        tenant_id=tenant_id,
        code=role_code,
        name=role_code.replace("_", " ").title(),
        is_system=True,
    )
    db.add(role)
    await db.flush()
    for permission_code in ROLE_PERMISSION_MAP.get(role_code, frozenset()):
        permission = await db.scalar(
            select(Permission).where(Permission.code == permission_code)
        )
        if permission is None:
            permission = Permission(
                code=permission_code, name=permission_code.replace(":", " ").title()
            )
            db.add(permission)
            await db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await db.flush()
    return role


async def _assign_mapped_roles(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    provider: EnterpriseIdentityProvider,
    external_roles: list[str],
) -> None:
    mapping = provider.role_mapping_json or {}
    for ext_role in external_roles:
        role_code = mapping.get(ext_role)
        if not role_code:
            continue
        role = await _ensure_role(db, tenant_id=tenant_id, role_code=str(role_code))
        exists = await db.scalar(
            select(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
            )
        )
        if exists is None:
            db.add(UserRole(tenant_id=tenant_id, user_id=user_id, role_id=role.id))


async def resolve_or_provision_user(
    db: AsyncSession,
    *,
    provider: EnterpriseIdentityProvider,
    external_subject: str,
    issuer: str,
    email: str | None,
    display_name: str | None,
    email_verified: bool,
    external_roles: list[str] | None = None,
) -> User:
    """Bind external identity to a tenant user via subject, optional explicit email link, or JIT."""
    now = datetime.now(UTC)
    existing = await db.scalar(
        select(ExternalUserIdentity).where(
            ExternalUserIdentity.tenant_id == provider.tenant_id,
            ExternalUserIdentity.provider_id == provider.id,
            ExternalUserIdentity.external_subject == external_subject,
        )
    )
    if existing is not None:
        linked = await db.scalar(
            select(User).where(
                User.id == existing.user_id, User.tenant_id == provider.tenant_id
            )
        )
        if linked is None or linked.status != "active":
            raise HTTPException(
                403,
                detail={"code": "user_inactive", "message": "Linked user is inactive"},
            )
        existing.last_authenticated_at = now
        existing.external_email = email
        if external_roles:
            await _assign_mapped_roles(
                db,
                tenant_id=provider.tenant_id,
                user_id=linked.id,
                provider=provider,
                external_roles=external_roles,
            )
        await db.flush()
        return linked

    user: User | None = None
    if (
        provider.account_linking_policy == "VERIFIED_EMAIL_EXPLICIT"
        and email
        and email_verified
    ):
        user = await db.scalar(
            select(User).where(
                User.tenant_id == provider.tenant_id,
                User.email == email.strip().lower(),
            )
        )
        if user is not None and user.status != "active":
            raise HTTPException(
                403,
                detail={"code": "user_inactive", "message": "Linked user is inactive"},
            )

    if user is None:
        if not provider.jit_enabled:
            raise HTTPException(
                403,
                detail={
                    "code": "identity_unlinked",
                    "message": "No linked account and JIT provisioning disabled",
                },
            )
        if not email:
            raise HTTPException(
                400,
                detail={"code": "email_required", "message": "Email required for JIT provisioning"},
            )
        user = User(
            tenant_id=provider.tenant_id,
            email=email.strip().lower(),
            display_name=(display_name or email).strip()[:255],
            status="active",
            password_hash=None,
            auth_version=1,
        )
        db.add(user)
        await db.flush()
        await add_audit_event(
            db,
            tenant_id=provider.tenant_id,
            actor_user_id=None,
            entity_type="user",
            entity_id=user.id,
            action="jit_provisioned",
            after={
                "email": user.email,
                "provider_id": str(provider.id),
                "external_subject": external_subject,
            },
        )

    assert user is not None
    identity = ExternalUserIdentity(
        tenant_id=provider.tenant_id,
        provider_id=provider.id,
        user_id=user.id,
        protocol=provider.protocol,
        external_subject=external_subject,
        issuer=issuer,
        external_email=email,
        last_authenticated_at=now,
    )
    db.add(identity)
    if external_roles:
        await _assign_mapped_roles(
            db,
            tenant_id=provider.tenant_id,
            user_id=user.id,
            provider=provider,
            external_roles=external_roles,
        )
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=provider.tenant_id,
        actor_user_id=None,
        entity_type="external_user_identity",
        entity_id=identity.id,
        action="linked",
        after={
            "user_id": str(user.id),
            "provider_id": str(provider.id),
            "external_subject": external_subject,
            "issuer": issuer,
        },
    )
    return user


async def authorization_for_user(
    db: AsyncSession, *, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> tuple[frozenset[str], frozenset[str]]:
    role_rows = (
        await db.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
        )
    ).scalars()
    roles = frozenset(role_rows)
    permission_rows = (
        await db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
        )
    ).scalars()
    return roles, frozenset(permission_rows)


async def create_sso_exchange_code(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    provider_id: uuid.UUID | None,
    user: User,
) -> str:
    exchange_code = secrets.token_urlsafe(32)
    tx = AuthTransaction(
        kind="SSO_EXCHANGE",
        tenant_id=tenant_id,
        provider_id=provider_id,
        exchange_code_hash=hash_opaque_token(exchange_code),
        payload_json={"user_id": str(user.id)},
        expires_at=datetime.now(UTC) + timedelta(minutes=2),
    )
    db.add(tx)
    await db.flush()
    return exchange_code


async def exchange_sso_code(
    db: AsyncSession,
    *,
    exchange_code: str,
    provider: AuthProvider,
) -> tuple[str, int, User, AuthContext]:
    code_hash = hash_opaque_token(exchange_code)
    now = datetime.now(UTC)
    tx = await db.scalar(
        select(AuthTransaction).where(
            AuthTransaction.kind == "SSO_EXCHANGE",
            AuthTransaction.exchange_code_hash == code_hash,
        )
    )
    if tx is None or tx.consumed_at is not None or tx.expires_at <= now:
        raise HTTPException(
            400,
            detail={"code": "invalid_exchange_code", "message": "Invalid or expired exchange code"},
        )
    user_id = uuid.UUID(str(tx.payload_json["user_id"]))
    user = await db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == tx.tenant_id)
    )
    if user is None or user.status != "active":
        raise HTTPException(
            403,
            detail={"code": "user_inactive", "message": "User inactive"},
        )
    tx.consumed_at = now
    roles, permissions = await authorization_for_user(
        db, user_id=user.id, tenant_id=user.tenant_id
    )
    context = AuthContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        roles=roles,
        permissions=permissions,
        auth_version=int(user.auth_version),
    )
    token, ttl = provider.issue_access_token(context)
    user.last_login_at = now
    await db.flush()
    return token, ttl, user, context


async def record_replay_or_raise(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    kind: str,
    marker_key: str,
    expires_at: datetime,
) -> None:
    from app.db.models import ReplayMarker

    existing = await db.scalar(
        select(ReplayMarker).where(
            ReplayMarker.tenant_id == tenant_id,
            ReplayMarker.kind == kind,
            ReplayMarker.marker_key == marker_key,
        )
    )
    if existing is not None:
        raise HTTPException(
            400,
            detail={"code": "replay_detected", "message": "Replay detected"},
        )
    db.add(
        ReplayMarker(
            tenant_id=tenant_id,
            kind=kind,
            marker_key=marker_key,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
    )
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            400,
            detail={"code": "replay_detected", "message": "Replay detected"},
        ) from exc
