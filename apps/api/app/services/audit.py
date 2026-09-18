"""Centralized AuditEvent writer with request correlation (PEV-072)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent
from app.middleware.correlation import get_correlation_id

_FORBIDDEN_AUDIT_FRAGMENTS = ("password", "token", "bearer", "secret", "assertion")


def _sanitize_audit_value(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _FORBIDDEN_AUDIT_FRAGMENTS):
                continue
            cleaned[key] = _sanitize_audit_value(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_audit_value(item) for item in value]
    return value


def _payload_json(
    *, before: dict[str, Any] | None, after: dict[str, Any] | None
) -> dict[str, Any]:
    """Preserve legacy single-payload shape when only ``after`` is supplied."""
    safe_before = _sanitize_audit_value(before) if before is not None else None
    safe_after = _sanitize_audit_value(after) if after is not None else None
    if safe_before is None and safe_after is None:
        return {}
    if safe_before is None and safe_after is not None:
        return dict(safe_after) if isinstance(safe_after, dict) else {}
    if safe_before is not None and safe_after is None:
        return {"before": safe_before}
    return {"before": safe_before, "after": safe_after}


async def add_audit_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    """Append an AuditEvent, auto-attaching the request correlation ID when omitted."""
    resolved = correlation_id if correlation_id is not None else get_correlation_id()

    event = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload_json=_payload_json(before=before, after=after),
        correlation_id=resolved,
    )
    db.add(event)
    return event
