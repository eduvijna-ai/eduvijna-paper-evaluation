"""Redis-backed rate limits for authentication brute-force protection.

Uses Celery broker Redis (same pattern as integration_rate_limit).
Keys never store passwords or tokens — only hashed email + client IP counters.
"""

from __future__ import annotations

import hashlib
import logging
import time

from fastapi import HTTPException, Request
from redis import Redis

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_redis: Redis[str] | None = None


def _client(settings: Settings) -> Redis[str]:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)
    return _redis


def reset_rate_limit_client_for_tests() -> None:
    """Clear cached Redis client (unit tests only)."""
    global _redis
    _redis = None


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:128]
    if request.client and request.client.host:
        return request.client.host[:128]
    return "unknown"


def _email_hash(email: str) -> str:
    normalized = (email or "").strip().lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:32]


def check_auth_login_rate_limit(
    *,
    request: Request,
    email: str,
    settings: Settings | None = None,
) -> None:
    """Enforce failed-login attempt budgets before credential verification.

    Counts are incremented by ``record_auth_login_failure`` after a failed login.
    This pre-check rejects when the sliding window already exceeds the budget.
    """
    cfg = settings or get_settings()
    email_limit = int(cfg.auth_login_fail_limit_per_email_per_minute)
    ip_limit = int(cfg.auth_login_fail_limit_per_ip_per_minute)
    if email_limit <= 0 and ip_limit <= 0:
        return

    window = int(time.time() // 60)
    ip = client_ip(request)
    ehash = _email_hash(email)
    try:
        client = _client(cfg)
        if email_limit > 0:
            email_key = f"auth:login:fail:email:{ehash}:{window}"
            email_count = int(client.get(email_key) or 0)
            if email_count >= email_limit:
                logger.warning(
                    "auth_login_rate_limited",
                    extra={"scope": "email", "client_ip": ip},
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "auth_rate_limited",
                        "message": "Too many login attempts. Try again later.",
                    },
                    headers={"Retry-After": "60"},
                )
        if ip_limit > 0:
            ip_key = f"auth:login:fail:ip:{ip}:{window}"
            ip_count = int(client.get(ip_key) or 0)
            if ip_count >= ip_limit:
                logger.warning(
                    "auth_login_rate_limited",
                    extra={"scope": "ip", "client_ip": ip},
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "auth_rate_limited",
                        "message": "Too many login attempts. Try again later.",
                    },
                    headers={"Retry-After": "60"},
                )
    except HTTPException:
        raise
    except Exception:
        if cfg.environment.lower() in {"local", "test"}:
            logger.warning("auth_login_rate_limit_unavailable_fail_open")
            return
        raise HTTPException(
            status_code=503,
            detail={
                "code": "rate_limit_unavailable",
                "message": "Authentication rate limiter unavailable",
            },
        ) from None


def record_auth_login_failure(
    *,
    request: Request,
    email: str,
    settings: Settings | None = None,
) -> None:
    """Increment failed-login counters (no secrets logged)."""
    cfg = settings or get_settings()
    email_limit = int(cfg.auth_login_fail_limit_per_email_per_minute)
    ip_limit = int(cfg.auth_login_fail_limit_per_ip_per_minute)
    if email_limit <= 0 and ip_limit <= 0:
        return

    window = int(time.time() // 60)
    ip = client_ip(request)
    ehash = _email_hash(email)
    try:
        client = _client(cfg)
        pipe = client.pipeline()
        if email_limit > 0:
            email_key = f"auth:login:fail:email:{ehash}:{window}"
            pipe.incr(email_key)
            pipe.expire(email_key, 120)
        if ip_limit > 0:
            ip_key = f"auth:login:fail:ip:{ip}:{window}"
            pipe.incr(ip_key)
            pipe.expire(ip_key, 120)
        pipe.execute()
    except Exception:
        if cfg.environment.lower() in {"local", "test"}:
            return
        # Do not block the original 401 response path on counter failure in prod either —
        # limiter availability is enforced on the pre-check; recording is best-effort.
        logger.warning("auth_login_fail_counter_unavailable")
