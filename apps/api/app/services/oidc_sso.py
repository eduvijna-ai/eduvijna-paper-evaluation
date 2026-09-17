# ruff: noqa: E501
"""OIDC Authorization Code + PKCE SSO flows."""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.integration_crypto import decrypt_secret, encrypt_secret, hash_opaque_token
from app.db.models import AuthTransaction, EnterpriseIdentityProvider
from app.services.b19_outbound import get_jwks_signing_key, outbound_request
from app.services.enterprise_identity import (
    create_sso_exchange_code,
    record_replay_or_raise,
    resolve_or_provision_user,
)
from app.services.ssrf import validate_public_https_url


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest())
        .decode("utf-8")
        .rstrip("=")
    )
    return verifier, challenge


async def fetch_oidc_metadata(
    metadata_url: str, *, settings: Settings | None = None
) -> dict[str, Any]:
    cfg = settings or get_settings()
    validate_public_https_url(
        metadata_url,
        allow_insecure=cfg.environment.lower() in {"local", "test"}
        or cfg.b19_test_providers_enabled,
        purpose="OIDC metadata",
    )
    resp = await outbound_request("GET", metadata_url, request_timeout=10.0)
    if resp.status_code >= 400:
        raise HTTPException(
            400, detail={"code": "metadata_failed", "message": "OIDC metadata fetch failed"}
        )
    return dict(resp.json())


async def start_oidc_login(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    provider_id: uuid.UUID,
    settings: Settings | None = None,
) -> dict[str, str]:
    cfg = settings or get_settings()
    provider = await db.scalar(
        select(EnterpriseIdentityProvider).where(
            EnterpriseIdentityProvider.id == provider_id,
            EnterpriseIdentityProvider.tenant_id == tenant_id,
            EnterpriseIdentityProvider.protocol == "OIDC",
            EnterpriseIdentityProvider.enabled.is_(True),
        )
    )
    if provider is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "OIDC provider not found"})
    if not provider.authorization_endpoint or not provider.client_id:
        raise HTTPException(
            400,
            detail={"code": "provider_misconfigured", "message": "OIDC provider incomplete"},
        )

    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    verifier, challenge = _pkce_pair()
    redirect_uri = f"{cfg.public_base_url.rstrip('/')}/api/v1/sso/oidc/callback"
    tx = AuthTransaction(
        kind="OIDC_STATE",
        tenant_id=tenant_id,
        provider_id=provider.id,
        state=state,
        nonce=nonce,
        code_challenge=challenge,
        encrypted_code_verifier=encrypt_secret(verifier),
        payload_json={"redirect_uri": redirect_uri},
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(tx)
    await db.flush()

    params = {
        "response_type": "code",
        "client_id": provider.client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = f"{provider.authorization_endpoint}?{urlencode(params)}"
    return {"authorize_url": authorize_url, "state": state}


async def complete_oidc_callback(
    db: AsyncSession,
    *,
    code: str,
    state: str,
    settings: Settings | None = None,
) -> dict[str, str]:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    tx = await db.scalar(
        select(AuthTransaction).where(
            AuthTransaction.kind == "OIDC_STATE",
            AuthTransaction.state == state,
        )
    )
    if tx is None or tx.consumed_at is not None or tx.expires_at <= now:
        raise HTTPException(
            400,
            detail={"code": "invalid_state", "message": "Invalid or expired OIDC state"},
        )
    tx.consumed_at = now
    provider = await db.scalar(
        select(EnterpriseIdentityProvider).where(
            EnterpriseIdentityProvider.id == tx.provider_id,
            EnterpriseIdentityProvider.tenant_id == tx.tenant_id,
        )
    )
    if provider is None or not provider.enabled:
        raise HTTPException(400, detail={"code": "provider_disabled", "message": "Provider disabled"})
    if not provider.token_endpoint or not provider.jwks_uri or not provider.client_id:
        raise HTTPException(
            400,
            detail={"code": "provider_misconfigured", "message": "OIDC provider incomplete"},
        )

    verifier = decrypt_secret(tx.encrypted_code_verifier or "")
    redirect_uri = str(tx.payload_json.get("redirect_uri"))
    client_secret = (
        decrypt_secret(provider.encrypted_client_secret)
        if provider.encrypted_client_secret
        else None
    )

    allow_insecure = cfg.environment.lower() in {"local", "test"} or cfg.b19_test_providers_enabled
    validate_public_https_url(
        provider.token_endpoint, allow_insecure=allow_insecure, purpose="OIDC token"
    )
    validate_public_https_url(
        provider.jwks_uri, allow_insecure=allow_insecure, purpose="OIDC JWKS"
    )

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": provider.client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret

    token_resp = await outbound_request("POST", provider.token_endpoint, data=data)
    if token_resp.status_code >= 400:
        raise HTTPException(
            400,
            detail={"code": "token_exchange_failed", "message": "OIDC token exchange failed"},
        )
    token_payload = token_resp.json()

    id_token = token_payload.get("id_token")
    if not id_token:
        raise HTTPException(
            400, detail={"code": "missing_id_token", "message": "ID token missing"}
        )

    try:
        signing_key = get_jwks_signing_key(provider.jwks_uri, id_token)
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=provider.client_id,
            issuer=provider.issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            400, detail={"code": "invalid_id_token", "message": "ID token verification failed"}
        ) from exc
    if claims.get("nonce") != tx.nonce:
        raise HTTPException(400, detail={"code": "nonce_mismatch", "message": "Nonce mismatch"})

    jti = claims.get("jti") or hash_opaque_token(id_token)
    await record_replay_or_raise(
        db,
        tenant_id=provider.tenant_id,
        kind="oidc_id_token",
        marker_key=str(jti),
        expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
    )

    email = claims.get("email")
    email_verified = bool(claims.get("email_verified", False))
    display_name = claims.get("name") or claims.get("preferred_username")
    roles_claim = claims.get("roles") or claims.get("groups") or []
    if isinstance(roles_claim, str):
        roles_claim = [roles_claim]

    user = await resolve_or_provision_user(
        db,
        provider=provider,
        external_subject=str(claims["sub"]),
        issuer=str(claims["iss"]),
        email=str(email).lower() if email else None,
        display_name=str(display_name) if display_name else None,
        email_verified=email_verified,
        external_roles=[str(r) for r in roles_claim],
    )
    exchange_code = await create_sso_exchange_code(
        db, tenant_id=provider.tenant_id, provider_id=provider.id, user=user
    )
    frontend = cfg.frontend_base_url.rstrip("/")
    return {
        "redirect_url": f"{frontend}/sso/complete?exchange_code={exchange_code}",
        "exchange_code": exchange_code,
    }
