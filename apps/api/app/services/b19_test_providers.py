# ruff: noqa: E501
"""Deterministic in-process B19 test IdP / LMS / webhook fixtures.

Disabled unless B19_TEST_PROVIDERS_ENABLED or APP_ENV is local/test.
Never used as a production microservice.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from fastapi import HTTPException

from app.core.config import Settings, get_settings
from app.core.integration_crypto import hash_opaque_token
from app.services.saml_sso import build_signed_assertion_for_tests
from app.services.webhooks import verify_webhook_signature

_OIDC_CODES: dict[str, dict[str, Any]] = {}
_LTI_NONCES: dict[str, dict[str, Any]] = {}
_WEBHOOK_INBOX: list[dict[str, Any]] = []
_WEBHOOK_FAIL_UNTIL = 0
_WEBHOOK_EXPECTED_SECRET: str | None = None
_AGS_SCORES: list[dict[str, Any]] = []
_KEYS: dict[str, Any] | None = None
_B19_TEST_PRIVATE_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDRtOPJNFLw0NaS
2CRF6/TGRlVaNZfprZyF++2KPVzUeDYhWL6moGLFFOzxvldAlmNHGz99wADXF0K4
B7vS6Amig40GxGUMUtInyl22Bop758XMjFapl/2WHVzHRNF5cojEXq/h9ASwJcrc
+1LzuH9KN1G1EZOkN+qYFkShN5aUITZYZ0/TbBkaqlWozYsxG8PDJe9y8vBkI0ir
Usf2fcwuJ66DFNyBT4/yjC9aGa3atWDSdPezh5uvx4I4+X737RTSRXcoeDpNptOa
WYd8+eIKOcvIWMkMg4XgTv+kD0TDmmi+f44k9v/dqasWJOAVmb/z/nn8yJZC86/8
oMVOM5dTAgMBAAECggEAAMapaE3SmHQRwJg4N0z3WOUui3Ypo/l6OQ+EMGrHrnWq
ul+fhmCxFXj55YqwPV/p9ETOELC5isgsgHpzNjhAMgAu3xhwsaJtUkyfMDReX0Ub
upCrRtGaK0ByVU5gkxNpgIzkSqObey5Vcq7B/JyWS4mobCK5UTfVPd8mwtcGdSuZ
7vr/hU7xKLCq2BADP5V1Paqh48th2+vjm2hj965JrwsoQ+F9n8aqvI3YR3Rf+S4B
eP/D1tnEGOfGv8WIwaG3vKufG2hgOVPvjZiwHwWHvm+8fx+NzkApzLsCs8vWqKLS
8pGdaQ5rhAMcnphge0PwOt+5j2NW5D99Qpm82wBWSQKBgQDrhiH16H0KUU+5rlw5
jF1n/N4JdjlRY1qy48ET7guu/AMk0qEE/sJoAhUAWb3mIor5IQy1VF/FjnfbmfCU
9zrDWpqDvxWHlTAq7l7EJKSn6/dopevxrM4l+tily/z2Q4kOZHfcQBVg1x26fMpk
gnUehspGTNutGtd9LnIVYEk3HQKBgQDj8Ck4VsuDIbM2JH6OZQDe4BJC/GuhL6tc
XDU3+ZuEJz+sqphFhf7ReKHjYadmZU2HE325hpx+ZsgC8Uw+0JuWXk3raEGhk7LW
03QIvEQAM3vBf/GALSbliPRoGh2WCCNYRVG9A9jBhpPtVOAaTFMuawtjLrxqpLYi
ah0mnO4NLwKBgATiSCwAQS+Ilh2klvb+iSVR4gzSLcgZRlU1Udim9AkR4sLNt1cS
LVfYyzSxp7Vw++7El63e7Ql8tdGQ9KMyKT7JzzByMvEXz+LkBIUOuXdd9khuQGFH
kxLIi9uMSleU+O+ad73Sel8CtvQaCFxjNCiI5QLmLxv81YEcCHOXBo2lAoGBALGE
eJXIAvc9Z7Ti9y0uvF7XY2GH9MqztWFY7pmJa/SgHJb8xVpf4PSCXpIXm6fDfX2V
UHUMwRQwN9US166UCJgzGbwclgCgZseoJtYmyU7eyaMJYavRflmFL9Njg2c1L1Gv
qtjqBgWyKcLMNzxD9QRRmazE2Ti0zqQ+wDUyQrNBAoGAefik7zsFGAWZqzYYbFEJ
6SaZq4wuGOrmBkYHkagE8XR8ZAW8+nM9wFcclq27lAj5La/fDbW669xN04aMeFh4
i3fQdXkA7MczyEet1d1P/v56WiBWiU55TOHTY/BH2uMRrANWOWOqu6+VJ8ZGhSmG
QvA+bXEv/4xNvTr/KxqLoFU=
-----END PRIVATE KEY-----
"""
_B19_TEST_CERT_PEM = """-----BEGIN CERTIFICATE-----
MIICpzCCAY+gAwIBAgIBATANBgkqhkiG9w0BAQsFADAXMRUwEwYDVQQDDAxCMTkg
VGVzdCBJZFAwHhcNMjYwMTAxMDAwMDAwWhcNMzYwMTAxMDAwMDAwWjAXMRUwEwYD
VQQDDAxCMTkgVGVzdCBJZFAwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIB
AQDRtOPJNFLw0NaS2CRF6/TGRlVaNZfprZyF++2KPVzUeDYhWL6moGLFFOzxvldA
lmNHGz99wADXF0K4B7vS6Amig40GxGUMUtInyl22Bop758XMjFapl/2WHVzHRNF5
cojEXq/h9ASwJcrc+1LzuH9KN1G1EZOkN+qYFkShN5aUITZYZ0/TbBkaqlWozYsx
G8PDJe9y8vBkI0irUsf2fcwuJ66DFNyBT4/yjC9aGa3atWDSdPezh5uvx4I4+X73
7RTSRXcoeDpNptOaWYd8+eIKOcvIWMkMg4XgTv+kD0TDmmi+f44k9v/dqasWJOAV
mb/z/nn8yJZC86/8oMVOM5dTAgMBAAEwDQYJKoZIhvcNAQELBQADggEBAClPzlWF
dxtB6Gd7vBCI3yGUtxvf6M847B1FO726Z+D4Uacza6NOh3CvgBkMaxWI9xXTUB8i
I4IaPCi8rqHXntb2ypOAoBM8R809L7jBeXSMwl2o3fxmlbiDL+r0cYLseQ0ynwMG
m0O6KhykfcjfiM2E0tIeuqaomNkAZCM4ybGyQ3VMt7CTHX6uHK+d6IREl8pCuPyp
ROmmMRNZVRWQrZ2kpU8/JDadh7b0UY4mV7AdHnPuA+WuzhpyC9cvlDPCHGqm85UN
+FkYWYQ+wLojIo8WtNgfw7CbSDiZ4OWdkNV58F+7L5TrvcW+rM3c12GLKcsJ6AQk
foPt2xcs8edkg0A=
-----END CERTIFICATE-----
"""


def test_providers_enabled(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    return bool(cfg.b19_test_providers_enabled or cfg.environment.lower() in {"local", "test"})


def require_test_providers(settings: Settings | None = None) -> None:
    if not test_providers_enabled(settings):
        raise HTTPException(404, detail={"code": "not_found", "message": "Not found"})


def _keys() -> dict[str, Any]:
    global _KEYS
    if _KEYS is not None:
        return _KEYS
    key = cast(
        RSAPrivateKey,
        serialization.load_pem_private_key(_B19_TEST_PRIVATE_PEM.encode("utf-8"), password=None),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    numbers = key.public_key().public_numbers()

    def _b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(raw).decode("ascii")

    kid = "b19-test"
    _KEYS = {
        "private_pem": _B19_TEST_PRIVATE_PEM,
        "public_pem": public_pem,
        "cert_pem": _B19_TEST_CERT_PEM,
        "kid": kid,
        "jwks": {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": kid,
                    "n": _b64(numbers.n),
                    "e": _b64(numbers.e),
                }
            ]
        },
    }
    return _KEYS


def oidc_jwks() -> dict[str, Any]:
    return dict(_keys()["jwks"])


def saml_idp_cert_pem() -> str:
    return str(_keys()["cert_pem"])


def issue_oidc_authorize_redirect(
    *,
    redirect_uri: str,
    state: str,
    nonce: str,
    client_id: str,
    subject: str = "oidc-user-1",
    email: str = "sso.oidc@demo.eduvijna.local",
    email_verified: bool = True,
) -> str:
    code = secrets.token_urlsafe(24)
    _OIDC_CODES[code] = {
        "nonce": nonce,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "subject": subject,
        "email": email,
        "email_verified": email_verified,
        "issuer": "https://b19-test.example/oidc",
    }
    return f"{redirect_uri}?{urlencode({'code': code, 'state': state})}"


def issue_oidc_tokens(*, code: str, redirect_uri: str, client_id: str) -> dict[str, Any]:
    payload = _OIDC_CODES.pop(code, None)
    if payload is None or payload["redirect_uri"] != redirect_uri or payload["client_id"] != client_id:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    now = datetime.now(UTC)
    keys = _keys()
    id_token = jwt.encode(
        {
            "iss": payload["issuer"],
            "sub": payload["subject"],
            "aud": client_id,
            "exp": now + timedelta(minutes=5),
            "iat": now,
            "nonce": payload["nonce"],
            "email": payload["email"],
            "email_verified": payload["email_verified"],
            "name": "OIDC Test User",
            "jti": secrets.token_urlsafe(12),
        },
        keys["private_pem"],
        algorithm="RS256",
        headers={"kid": keys["kid"]},
    )
    return {"id_token": id_token, "token_type": "Bearer", "expires_in": 300}


def issue_saml_response(
    *,
    issuer: str,
    audience: str,
    name_id: str,
    email: str,
    in_response_to: str | None = None,
    recipient: str | None = None,
    destination: str | None = None,
) -> str:
    keys = _keys()
    now = datetime.now(UTC)
    return build_signed_assertion_for_tests(
        assertion_id=f"_assert{secrets.token_hex(8)}",
        issuer=issuer,
        name_id=name_id,
        audience=audience,
        email=email,
        not_before=now - timedelta(minutes=1),
        not_on_or_after=now + timedelta(minutes=5),
        private_key_pem=str(keys["private_pem"]),
        cert_pem=str(keys["cert_pem"]),
        in_response_to=in_response_to,
        recipient=recipient,
        destination=destination,
    )


def issue_lti_id_token(
    *,
    issuer: str,
    client_id: str,
    deployment_id: str,
    nonce: str,
    subject: str,
    resource_link_id: str,
    context_id: str,
    lineitem_url: str,
    memberships_url: str,
    roles: list[str] | None = None,
    target_link_uri: str,
) -> str:
    now = datetime.now(UTC)
    keys = _keys()
    return jwt.encode(
        {
            "iss": issuer,
            "sub": subject,
            "aud": client_id,
            "azp": client_id,
            "exp": now + timedelta(minutes=5),
            "iat": now,
            "nonce": nonce,
            "jti": secrets.token_urlsafe(12),
            "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
            "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
            "https://purl.imsglobal.org/spec/lti/claim/deployment_id": deployment_id,
            "https://purl.imsglobal.org/spec/lti/claim/target_link_uri": target_link_uri,
            "https://purl.imsglobal.org/spec/lti/claim/resource_link": {"id": resource_link_id},
            "https://purl.imsglobal.org/spec/lti/claim/context": {"id": context_id},
            "https://purl.imsglobal.org/spec/lti/claim/roles": roles
            or ["http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor"],
            "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {"lineitem": lineitem_url},
            "https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice": {
                "context_memberships_url": memberships_url
            },
        },
        keys["private_pem"],
        algorithm="RS256",
        headers={"kid": keys["kid"]},
    )


def store_lti_login(state: str, nonce: str, redirect_uri: str) -> None:
    _LTI_NONCES[state] = {"nonce": nonce, "redirect_uri": redirect_uri}


def pop_lti_login(state: str) -> dict[str, Any]:
    data = _LTI_NONCES.pop(state, None)
    if data is None:
        raise HTTPException(400, detail={"code": "invalid_state", "message": "Unknown LTI state"})
    return data


def nrps_memberships() -> dict[str, Any]:
    return {
        "id": "https://b19-test.example/nrps",
        "members": [
            {
                "status": "Active",
                "name": "Roster Student One",
                "user_id": "nrps-student-1",
                "roles": ["http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"],
            }
        ],
    }


def record_ags_score(payload: dict[str, Any]) -> dict[str, Any]:
    _AGS_SCORES.append(payload)
    return {"id": str(len(_AGS_SCORES))}


def list_ags_scores() -> list[dict[str, Any]]:
    return list(_AGS_SCORES)


def set_webhook_fail_until(attempt: int) -> None:
    global _WEBHOOK_FAIL_UNTIL
    _WEBHOOK_FAIL_UNTIL = attempt


def set_webhook_expected_secret(secret: str | None) -> None:
    global _WEBHOOK_EXPECTED_SECRET
    _WEBHOOK_EXPECTED_SECRET = secret


def expected_webhook_secret() -> str:
    if _WEBHOOK_EXPECTED_SECRET:
        return _WEBHOOK_EXPECTED_SECRET
    cfg = get_settings()
    configured = getattr(cfg, "b19_test_webhook_signing_secret", None)
    if configured:
        return str(configured)
    raise HTTPException(
        401,
        detail={"code": "webhook_secret_unconfigured", "message": "Test webhook secret missing"},
    )


def record_webhook(
    *,
    raw_body: str,
    timestamp: str,
    signature: str,
    event_id: str,
    event_type: str,
    secret: str | None = None,
) -> int:
    verify_secret = secret if secret else expected_webhook_secret()
    if not verify_secret:
        raise HTTPException(
            401,
            detail={"code": "webhook_secret_unconfigured", "message": "Test webhook secret missing"},
        )
    if not verify_webhook_signature(
        secret=verify_secret, timestamp=timestamp, raw_body=raw_body, signature=signature
    ):
        raise HTTPException(401, detail={"code": "bad_signature", "message": "Invalid webhook signature"})
    _WEBHOOK_INBOX.append(
        {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "signature": signature,
            "body": raw_body,
        }
    )
    global _WEBHOOK_FAIL_UNTIL
    if _WEBHOOK_FAIL_UNTIL > 0:
        _WEBHOOK_FAIL_UNTIL -= 1
        raise HTTPException(500, detail={"code": "forced_failure", "message": "Configured fixture failure"})
    return 200


def webhook_inbox() -> list[dict[str, Any]]:
    return list(_WEBHOOK_INBOX)


def reset_test_provider_state() -> None:
    _OIDC_CODES.clear()
    _LTI_NONCES.clear()
    _WEBHOOK_INBOX.clear()
    _AGS_SCORES.clear()
    set_webhook_fail_until(0)
    set_webhook_expected_secret(None)


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def opaque_hash(value: str) -> str:
    return hash_opaque_token(value)


def new_uuid() -> str:
    return str(uuid.uuid4())
