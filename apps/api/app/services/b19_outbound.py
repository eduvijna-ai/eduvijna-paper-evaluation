"""Outbound HTTP with in-process dispatch for gated B19 test-provider URLs."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
from fastapi import HTTPException
from jwt import PyJWK, PyJWKClient

from app.core.config import get_settings


class OutboundResponse:
    def __init__(
        self,
        status_code: int,
        payload: Any = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> Any:
        return self._payload


def is_b19_test_url(url: str) -> bool:
    if "/api/v1/b19-test/" not in url:
        return False
    cfg = get_settings()
    return bool(cfg.b19_test_providers_enabled or cfg.environment.lower() in {"local", "test"})


def get_jwks_signing_key(jwks_uri: str, token: str) -> Any:
    if is_b19_test_url(jwks_uri):
        from app.services.b19_test_providers import oidc_jwks

        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        for key in oidc_jwks()["keys"]:
            if kid is None or key.get("kid") == kid:
                return PyJWK.from_dict(key).key
        raise HTTPException(
            400, detail={"code": "jwks_key_missing", "message": "Signing key not found"}
        )
    return PyJWKClient(jwks_uri, cache_keys=True).get_signing_key_from_jwt(token).key


def _dispatch_test(
    method: str,
    url: str,
    *,
    data: dict[str, Any] | None = None,
    json_body: Any = None,
    content: str | bytes | None = None,
    headers: dict[str, str] | None = None,
) -> OutboundResponse:
    from app.services.b19_test_providers import (
        issue_oidc_tokens,
        nrps_memberships,
        oidc_jwks,
        record_ags_score,
        record_webhook,
    )

    parsed = urlparse(url)
    path = parsed.path
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    method = method.upper()
    if method == "GET" and (path.endswith("/oidc/jwks") or path.endswith("/lti/jwks")):
        return OutboundResponse(200, oidc_jwks())
    if method == "POST" and path.endswith("/oidc/token"):
        payload = dict(data or {})
        tokens = issue_oidc_tokens(
            code=str(payload.get("code") or ""),
            redirect_uri=str(payload.get("redirect_uri") or ""),
            client_id=str(payload.get("client_id") or ""),
        )
        return OutboundResponse(200, tokens)
    if method == "POST" and path.endswith("/lti/token"):
        return OutboundResponse(
            200, {"access_token": "b19-test-ags-token", "token_type": "Bearer", "expires_in": 3600}
        )
    if method == "GET" and path.endswith("/nrps/memberships"):
        return OutboundResponse(200, nrps_memberships())
    if method == "POST" and "/ags/lineitems/" in path and path.endswith("/scores"):
        return OutboundResponse(200, record_ags_score(dict(json_body or {})))
    if method == "POST" and path.endswith("/webhook-receiver"):
        raw = content.decode("utf-8") if isinstance(content, bytes) else str(content or "")
        try:
            record_webhook(
                raw_body=raw,
                timestamp=headers.get("x-eduvijna-timestamp", ""),
                signature=headers.get("x-eduvijna-signature", ""),
                event_id=headers.get("x-eduvijna-event-id", ""),
                event_type=headers.get("x-eduvijna-event-type", ""),
                secret=None,
            )
            return OutboundResponse(200, {"status": "ok"})
        except HTTPException as exc:
            return OutboundResponse(exc.status_code, exc.detail, text=str(exc.detail))
    _ = parse_qs(parsed.query)
    raise HTTPException(404, detail={"code": "unknown_test_url", "message": path})


async def outbound_request(
    method: str,
    url: str,
    *,
    data: dict[str, Any] | None = None,
    json: Any = None,
    content: str | bytes | None = None,
    headers: dict[str, str] | None = None,
    request_timeout: float = 15.0,
) -> OutboundResponse | httpx.Response:
    if is_b19_test_url(url):
        return _dispatch_test(
            method, url, data=data, json_body=json, content=content, headers=headers
        )
    async with httpx.AsyncClient(timeout=request_timeout, follow_redirects=False) as client:
        return await client.request(
            method,
            url,
            data=data,
            json=json,
            content=content,
            headers=headers,
        )
