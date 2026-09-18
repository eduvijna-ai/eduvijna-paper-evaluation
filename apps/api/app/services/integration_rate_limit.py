"""Redis-backed sliding-window rate limit for machine integration APIs."""

from __future__ import annotations

import time
import uuid

from fastapi import HTTPException
from redis import Redis

from app.core.config import Settings, get_settings

_redis: Redis[str] | None = None


def _client(settings: Settings) -> Redis[str]:
    global _redis
    if _redis is None:
        # Reuse Celery broker Redis for lightweight counters.
        _redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)
    return _redis


def check_integration_rate_limit(
    *,
    tenant_id: uuid.UUID,
    credential_id: uuid.UUID,
    settings: Settings | None = None,
) -> None:
    cfg = settings or get_settings()
    limit = max(1, int(cfg.integration_rate_limit_per_minute))
    key = f"b19:rl:{tenant_id}:{credential_id}:{int(time.time() // 60)}"
    try:
        client = _client(cfg)
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, 120)
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limited",
                    "message": "Integration rate limit exceeded",
                },
            )
    except HTTPException:
        raise
    except Exception:
        if cfg.environment.lower() in {"local", "test"}:
            return
        raise HTTPException(
            status_code=503,
            detail={"code": "rate_limit_unavailable", "message": "Rate limiter unavailable"},
        ) from None
