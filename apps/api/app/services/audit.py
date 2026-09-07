"""Centralized AuditEvent writer with request correlation (PEV-072)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent
from app.middleware.correlation import get_correlation_id


def _payload_json(
    *, before: dict[str, Any] | None, after: dict[str, Any] | None
) -> dict[str, Any]:
    """Preserve legacy single-payload shape when only ``after`` is supplied."""
    if before is None and after is None:
        return {}
    if before is None and after is not None:
        return after
    if before is not None and after is None:
        return {"before": before}
    return {"before": before, "after": after}


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
