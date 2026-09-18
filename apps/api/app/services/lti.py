# ruff: noqa: E501
"""LTI 1.3 Advantage login initiation, launch validation, and tool keys."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.integration_crypto import decrypt_secret, encrypt_secret, hash_opaque_token
from app.db.models import AuthTransaction, LtiPlatform, LtiResourceLink
from app.services.audit import add_audit_event
from app.services.b19_outbound import get_jwks_signing_key
from app.services.enterprise_identity import record_replay_or_raise
from app.services.ssrf import validate_public_https_url

LTI_VERSION = "1.3.0"
LTI_MESSAGE_TYPE = "LtiResourceLinkRequest"
SAFE_LTI_ROLE_CODES = frozenset(
    {
        "TEACHER",
        "EVALUATOR",
        "STUDENT",
        "PARENT",
        "MODERATOR",
        "AUDITOR",
        "HOD",
        "ACADEMIC_COORDINATOR",
        "EXAM_CONTROLLER",
    }
)


def generate_tool_keypair() -> tuple[str, dict[str, Any]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public = key.public_key()
    numbers = public.public_numbers()
    kid = secrets.token_hex(8)

    def _b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(raw).decode("ascii")

    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64(numbers.n),
        "e": _b64(numbers.e),
    }
    return private_pem, {"keys": [jwk]}


def serialize_platform(platform: LtiPlatform) -> dict[str, Any]:
    return {
        "id": str(platform.id),
        "tenant_id": str(platform.tenant_id),
        "name": platform.name,
        "issuer": platform.issuer,
        "client_id": platform.client_id,
        "deployment_id": platform.deployment_id,
        "auth_login_url": platform.auth_login_url,
        "token_url": platform.token_url,
        "jwks_url": platform.jwks_url,
        "enabled": platform.enabled,
        "role_mapping_json": platform.role_mapping_json or {},
        "tool_public_jwks": platform.tool_public_jwks_json or {},
    }


async def create_lti_platform(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    issuer: str,
    client_id: str,
    deployment_id: str,
    auth_login_url: str,
    token_url: str,
    jwks_url: str,
    role_mapping_json: dict[str, Any] | None = None,
    enabled: bool = True,
) -> LtiPlatform:
    private_pem, public_jwks = generate_tool_keypair()
    platform = LtiPlatform(
        tenant_id=tenant_id,
        name=name.strip(),
        issuer=issuer.strip(),
        client_id=client_id.strip(),
        deployment_id=deployment_id.strip(),
        auth_login_url=auth_login_url.strip(),
        token_url=token_url.strip(),
        jwks_url=jwks_url.strip(),
        enabled=enabled,
        role_mapping_json=role_mapping_json or {},
        encrypted_tool_private_jwk=encrypt_secret(private_pem),
        tool_public_jwks_json=public_jwks,
    )
    db.add(platform)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="lti_platform",
        entity_id=platform.id,
        action="created",
        after=serialize_platform(platform),
    )
    return platform


async def start_lti_login(
    db: AsyncSession,
    *,
    iss: str,
    client_id: str,
    login_hint: str | None,
    target_link_uri: str,
    lti_message_hint: str | None,
    lti_deployment_id: str | None,
    settings: Settings | None = None,
) -> str:
    cfg = settings or get_settings()
    query = select(LtiPlatform).where(
        LtiPlatform.issuer == iss,
        LtiPlatform.client_id == client_id,
        LtiPlatform.enabled.is_(True),
    )
    if lti_deployment_id:
        query = query.where(LtiPlatform.deployment_id == lti_deployment_id)
    platform = await db.scalar(query)
    if platform is None:
        raise HTTPException(400, detail={"code": "unknown_platform", "message": "LTI platform unknown"})
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    redirect_uri = f"{cfg.public_base_url.rstrip('/')}/lti/launch"
    tx = AuthTransaction(
        kind="LTI",
        tenant_id=platform.tenant_id,
        state=state,
        nonce=nonce,
        payload_json={
            "platform_id": str(platform.id),
            "redirect_uri": redirect_uri,
            "target_link_uri": target_link_uri,
        },
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(tx)
    await db.flush()
    params = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "prompt": "none",
        "client_id": platform.client_id,
        "redirect_uri": redirect_uri,
        "login_hint": login_hint or "",
        "state": state,
        "nonce": nonce,
    }
    if lti_message_hint:
        params["lti_message_hint"] = lti_message_hint
    params["target_link_uri"] = target_link_uri
    params["lti_deployment_id"] = platform.deployment_id
    return f"{platform.auth_login_url}?{urlencode(params)}"


def _map_lti_roles(platform: LtiPlatform, raw_roles: list[str]) -> list[str]:
    mapping = platform.role_mapping_json or {}
    mapped: list[str] = []
    for role in raw_roles:
        target = mapping.get(role)
        if not target:
            lowered = role.lower()
            if "instructor" in lowered or "teacher" in lowered:
                target = "TEACHER"
            elif "learner" in lowered or "student" in lowered:
                target = "STUDENT"
        if target in SAFE_LTI_ROLE_CODES:
            mapped.append(str(target))
    return mapped


async def complete_lti_launch(
    db: AsyncSession,
    *,
    id_token: str,
    state: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    tx = await db.scalar(
        select(AuthTransaction).where(AuthTransaction.kind == "LTI", AuthTransaction.state == state)
    )
    if tx is None or tx.consumed_at is not None or tx.expires_at <= now:
        raise HTTPException(400, detail={"code": "invalid_state", "message": "Invalid LTI state"})
    tx.consumed_at = now
    platform = await db.scalar(
        select(LtiPlatform).where(
            LtiPlatform.id == uuid.UUID(str(tx.payload_json["platform_id"])),
            LtiPlatform.tenant_id == tx.tenant_id,
        )
    )
    if platform is None or not platform.enabled:
        raise HTTPException(400, detail={"code": "platform_disabled", "message": "LTI platform disabled"})

    allow_insecure = cfg.environment.lower() in {"local", "test"} or cfg.b19_test_providers_enabled
    validate_public_https_url(platform.jwks_url, allow_insecure=allow_insecure, purpose="LTI JWKS")
    try:
        signing_key = get_jwks_signing_key(platform.jwks_url, id_token)
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            audience=platform.client_id,
            issuer=platform.issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            400, detail={"code": "invalid_lti_token", "message": "LTI token verification failed"}
        ) from exc
    if claims.get("nonce") != tx.nonce:
        raise HTTPException(400, detail={"code": "nonce_mismatch", "message": "LTI nonce mismatch"})
    azp = claims.get("azp")
    if azp and azp != platform.client_id:
        raise HTTPException(400, detail={"code": "azp_mismatch", "message": "Authorized party mismatch"})
    version = claims.get("https://purl.imsglobal.org/spec/lti/claim/version")
    message_type = claims.get("https://purl.imsglobal.org/spec/lti/claim/message_type")
    deployment_id = claims.get("https://purl.imsglobal.org/spec/lti/claim/deployment_id")
    if version != LTI_VERSION or message_type != LTI_MESSAGE_TYPE:
        raise HTTPException(400, detail={"code": "invalid_lti_message", "message": "Invalid LTI message"})
    if deployment_id != platform.deployment_id:
        raise HTTPException(400, detail={"code": "deployment_mismatch", "message": "Deployment mismatch"})

    expected_target = str((tx.payload_json or {}).get("target_link_uri") or "").rstrip("/")
    actual_target = str(claims.get("https://purl.imsglobal.org/spec/lti/claim/target_link_uri") or "").rstrip("/")
    if not expected_target or actual_target != expected_target:
        raise HTTPException(
            400,
            detail={"code": "target_mismatch", "message": "LTI target_link_uri mismatch"},
        )

    jti = claims.get("jti") or hash_opaque_token(id_token)
    await record_replay_or_raise(
        db,
        tenant_id=platform.tenant_id,
        kind="lti_id_token",
        marker_key=str(jti),
        expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
    )

    resource = claims.get("https://purl.imsglobal.org/spec/lti/claim/resource_link") or {}
    context = claims.get("https://purl.imsglobal.org/spec/lti/claim/context") or {}
    resource_link_id = str(resource.get("id") or "default")
    context_id = str(context.get("id") or "default")
    ags = claims.get("https://purl.imsglobal.org/spec/lti-ags/claim/endpoint") or {}
    nrps = claims.get("https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice") or {}
    lineitem = ags.get("lineitem")
    memberships = nrps.get("context_memberships_url")

    link = await db.scalar(
        select(LtiResourceLink).where(
            LtiResourceLink.platform_id == platform.id,
            LtiResourceLink.context_id == context_id,
            LtiResourceLink.resource_link_id == resource_link_id,
        )
    )
    if link is None:
        raise HTTPException(
            400,
            detail={
                "code": "unbound_resource",
                "message": "LTI resource link is not associated with an EduVijna assessment",
            },
        )
    if link.assessment_id is None:
        raise HTTPException(
            400,
            detail={
                "code": "unbound_resource",
                "message": "LTI resource link is not associated with an EduVijna assessment",
            },
        )
    if lineitem and not link.ags_lineitem_url:
        link.ags_lineitem_url = str(lineitem)
    if memberships and not link.nrps_memberships_url:
        link.nrps_memberships_url = str(memberships)
    link.last_launch_at = now
    await db.flush()
    mapped_roles = _map_lti_roles(
        platform, [str(r) for r in (claims.get("https://purl.imsglobal.org/spec/lti/claim/roles") or [])]
    )
    await add_audit_event(
        db,
        tenant_id=platform.tenant_id,
        actor_user_id=None,
        entity_type="lti_resource_link",
        entity_id=link.id,
        action="launch_accepted",
        after={
            "platform_id": str(platform.id),
            "resource_link_id": resource_link_id,
            "mapped_roles": mapped_roles,
        },
    )
    return {
        "tenant_id": str(platform.tenant_id),
        "platform_id": str(platform.id),
        "resource_link_id": str(link.id),
        "external_subject": str(claims["sub"]),
        "mapped_roles": mapped_roles,
        "context_id": context_id,
    }


def issue_lti_client_assertion(platform: LtiPlatform, settings: Settings | None = None) -> str:
    if not platform.encrypted_tool_private_jwk:
        raise HTTPException(400, detail={"code": "tool_key_missing", "message": "Tool private key missing"})
    private_pem = decrypt_secret(platform.encrypted_tool_private_jwk, settings)
    keys = (platform.tool_public_jwks_json or {}).get("keys") or []
    kid = str(keys[0].get("kid")) if keys else "tool"
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": platform.client_id,
            "sub": platform.client_id,
            "aud": platform.token_url,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": secrets.token_urlsafe(16),
        },
        private_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


def tool_jwks_for_platform(platform: LtiPlatform) -> dict[str, Any]:
    return platform.tool_public_jwks_json or {"keys": []}
