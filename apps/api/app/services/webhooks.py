# ruff: noqa: E501
"""Outbound webhooks: transactional outbox, HMAC signing, retry, SSRF."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.integration_crypto import decrypt_secret, encrypt_secret, generate_integration_secret
from app.db.models import (
    OutboundEvent,
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookEndpoint,
)
from app.services.audit import add_audit_event
from app.services.b19_outbound import outbound_request
from app.services.ssrf import validate_public_https_url

KNOWN_EVENT_TYPES = frozenset(
    {
        "result.published",
        "identity.user.provisioned",
        "identity.user.deactivated",
        "roster.sync.completed",
    }
)
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = (0, 1, 2, 4, 8)


def webhook_public_dict(endpoint: WebhookEndpoint) -> dict[str, Any]:
    return {
        "id": str(endpoint.id),
        "tenant_id": str(endpoint.tenant_id),
        "name": endpoint.name,
        "destination_url": endpoint.destination_url,
        "event_types": list(endpoint.event_types_json or []),
        "enabled": endpoint.enabled,
    }


def sign_webhook_payload(*, secret: str, timestamp: str, raw_body: str) -> str:
    signed = f"{timestamp}.{raw_body}".encode()
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def verify_webhook_signature(*, secret: str, timestamp: str, raw_body: str, signature: str) -> bool:
    expected = sign_webhook_payload(secret=secret, timestamp=timestamp, raw_body=raw_body)
    return hmac.compare_digest(expected, signature)


def _allow_insecure(settings: Settings) -> bool:
    return bool(
        settings.webhook_allow_insecure_destinations
        or settings.environment.lower() in {"local", "test"}
        or settings.b19_test_providers_enabled
    )


async def create_webhook_endpoint(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    destination_url: str,
    event_types: list[str],
    settings: Settings | None = None,
) -> tuple[WebhookEndpoint, str]:
    cfg = settings or get_settings()
    unknown = set(event_types) - KNOWN_EVENT_TYPES
    if unknown:
        raise HTTPException(
            400,
            detail={"code": "invalid_event_type", "message": f"Unknown event types: {sorted(unknown)}"},
        )
    validate_public_https_url(
        destination_url, allow_insecure=_allow_insecure(cfg), purpose="webhook"
    )
    secret = generate_integration_secret()
    endpoint = WebhookEndpoint(
        tenant_id=tenant_id,
        name=name.strip(),
        destination_url=destination_url,
        encrypted_signing_secret=encrypt_secret(secret, cfg),
        event_types_json=sorted(set(event_types)),
        enabled=True,
    )
    db.add(endpoint)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="webhook_endpoint",
        entity_id=endpoint.id,
        action="created",
        after=webhook_public_dict(endpoint),
    )
    return endpoint, secret


async def update_webhook_endpoint(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    endpoint_id: uuid.UUID,
    patch: dict[str, Any],
    settings: Settings | None = None,
) -> WebhookEndpoint:
    cfg = settings or get_settings()
    endpoint = await db.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id, WebhookEndpoint.tenant_id == tenant_id
        )
    )
    if endpoint is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Webhook not found"})
    before = webhook_public_dict(endpoint)
    if "name" in patch and patch["name"]:
        endpoint.name = str(patch["name"]).strip()
    if "enabled" in patch and patch["enabled"] is not None:
        endpoint.enabled = bool(patch["enabled"])
    if "event_types" in patch and patch["event_types"] is not None:
        types = [str(t) for t in patch["event_types"]]
        unknown = set(types) - KNOWN_EVENT_TYPES
        if unknown:
            raise HTTPException(
                400,
                detail={
                    "code": "invalid_event_type",
                    "message": f"Unknown event types: {sorted(unknown)}",
                },
            )
        endpoint.event_types_json = sorted(set(types))
    if "destination_url" in patch and patch["destination_url"]:
        validate_public_https_url(
            str(patch["destination_url"]),
            allow_insecure=_allow_insecure(cfg),
            purpose="webhook",
        )
        endpoint.destination_url = str(patch["destination_url"])
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="webhook_endpoint",
        entity_id=endpoint.id,
        action="updated",
        before=before,
        after=webhook_public_dict(endpoint),
    )
    return endpoint


async def rotate_webhook_secret(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    endpoint_id: uuid.UUID,
) -> tuple[WebhookEndpoint, str]:
    endpoint = await db.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id, WebhookEndpoint.tenant_id == tenant_id
        )
    )
    if endpoint is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Webhook not found"})
    secret = generate_integration_secret()
    endpoint.encrypted_signing_secret = encrypt_secret(secret)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="webhook_endpoint",
        entity_id=endpoint.id,
        action="secret_rotated",
        after=webhook_public_dict(endpoint),
    )
    return endpoint, secret


async def record_outbound_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    event_type: str,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    payload: dict[str, Any],
    source_version: int | None = None,
    schema_version: str = "1",
) -> OutboundEvent:
    now = datetime.now(UTC)
    event = OutboundEvent(
        event_uuid=uuid.uuid4(),
        tenant_id=tenant_id,
        event_type=event_type,
        schema_version=schema_version,
        occurred_at=now,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        source_version=source_version,
        payload_json=payload,
        dispatch_state="PENDING",
    )
    db.add(event)
    await db.flush()
    endpoints = list(
        await db.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.tenant_id == tenant_id,
                WebhookEndpoint.enabled.is_(True),
            )
        )
    )
    for endpoint in endpoints:
        subscribed = set(endpoint.event_types_json or [])
        if event_type not in subscribed:
            continue
        db.add(
            WebhookDelivery(
                endpoint_id=endpoint.id,
                event_id=event.id,
                status="PENDING",
                next_attempt_at=now,
            )
        )
    await db.flush()
    return event


def serialize_event(event: OutboundEvent) -> dict[str, Any]:
    return {
        "id": str(event.event_uuid),
        "event_type": event.event_type,
        "schema_version": event.schema_version,
        "tenant_id": str(event.tenant_id),
        "occurred_at": event.occurred_at.isoformat(),
        "source": {
            "entity_type": event.source_entity_type,
            "entity_id": str(event.source_entity_id),
            "version": event.source_version,
        },
        "payload": event.payload_json or {},
    }


def serialize_delivery(delivery: WebhookDelivery) -> dict[str, Any]:
    return {
        "id": str(delivery.id),
        "endpoint_id": str(delivery.endpoint_id),
        "event_id": str(delivery.event_id),
        "status": delivery.status,
        "attempt_count": delivery.attempt_count,
        "next_attempt_at": delivery.next_attempt_at.isoformat() if delivery.next_attempt_at else None,
        "terminal_failure": delivery.terminal_failure,
    }


async def _refresh_event_dispatch_state(db: AsyncSession, event: OutboundEvent) -> None:
    deliveries = list(
        await db.scalars(select(WebhookDelivery).where(WebhookDelivery.event_id == event.id))
    )
    if not deliveries:
        event.dispatch_state = "PENDING"
        return
    statuses = {row.status for row in deliveries}
    if statuses <= {"SUCCEEDED"}:
        event.dispatch_state = "DELIVERED"
    elif "PENDING" in statuses or "RETRYING" in statuses:
        event.dispatch_state = "PARTIAL" if "SUCCEEDED" in statuses or "FAILED" in statuses else "DISPATCHING"
    elif "SUCCEEDED" in statuses:
        event.dispatch_state = "PARTIAL"
    else:
        event.dispatch_state = "FAILED"


async def deliver_due_webhooks(
    db: AsyncSession, *, settings: Settings | None = None, limit: int = 50
) -> int:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    deliveries = list(
        await db.scalars(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status.in_(("PENDING", "RETRYING")),
                WebhookDelivery.terminal_failure.is_(False),
                WebhookDelivery.next_attempt_at.is_not(None),
                WebhookDelivery.next_attempt_at <= now,
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    delivered = 0
    for delivery in deliveries:
        if await _attempt_delivery(db, delivery, cfg):
            delivered += 1
    return delivered


async def enqueue_webhook_dispatch(*, countdown: float = 0) -> str | None:
    from app.tasks.celery_app import enqueue_deliver_webhooks

    return await enqueue_deliver_webhooks(countdown=countdown)


async def _attempt_delivery(
    db: AsyncSession, delivery: WebhookDelivery, settings: Settings
) -> bool:
    endpoint = await db.scalar(
        select(WebhookEndpoint).where(WebhookEndpoint.id == delivery.endpoint_id)
    )
    event = await db.scalar(select(OutboundEvent).where(OutboundEvent.id == delivery.event_id))
    if endpoint is None or event is None or not endpoint.enabled:
        delivery.status = "FAILED"
        delivery.terminal_failure = True
        await db.flush()
        return False

    started = time.perf_counter()
    status_code: int | None = None
    error: str | None = None
    try:
        validate_public_https_url(
            endpoint.destination_url,
            allow_insecure=_allow_insecure(settings),
            purpose="webhook",
        )
        body = serialize_event(event)
        raw = json.dumps(body, separators=(",", ":"), sort_keys=True)
        timestamp = str(int(time.time()))
        secret = decrypt_secret(endpoint.encrypted_signing_secret, settings)
        signature = sign_webhook_payload(secret=secret, timestamp=timestamp, raw_body=raw)
        headers = {
            "Content-Type": "application/json",
            "X-EduVijna-Event-Id": str(event.event_uuid),
            "X-EduVijna-Event-Type": event.event_type,
            "X-EduVijna-Timestamp": timestamp,
            "X-EduVijna-Signature": signature,
            "X-EduVijna-Signature-Version": "v1",
        }
        resp = await outbound_request(
            "POST",
            endpoint.destination_url,
            content=raw,
            headers=headers,
            request_timeout=10.0,
        )
        status_code = resp.status_code
        if resp.status_code >= 400:
            error = f"http_{resp.status_code}"
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        error = str(detail.get("code") or exc.detail or exc.__class__.__name__)
    except Exception as exc:
        error = exc.__class__.__name__
    duration_ms = int((time.perf_counter() - started) * 1000)
    delivery.attempt_count += 1
    db.add(
        WebhookDeliveryAttempt(
            delivery_id=delivery.id,
            attempt_number=delivery.attempt_count,
            attempted_at=datetime.now(UTC),
            http_status=status_code,
            error_sanitized=error,
            duration_ms=duration_ms,
        )
    )
    if error is None:
        delivery.status = "SUCCEEDED"
        delivery.next_attempt_at = None
        await _refresh_event_dispatch_state(db, event)
        await db.flush()
        return True
    if delivery.attempt_count >= MAX_ATTEMPTS:
        delivery.status = "FAILED"
        delivery.terminal_failure = True
        delivery.next_attempt_at = None
        await _refresh_event_dispatch_state(db, event)
    else:
        delay = BACKOFF_SECONDS[min(delivery.attempt_count, len(BACKOFF_SECONDS) - 1)]
        if settings.celery_task_always_eager:
            delay = 0
        delivery.status = "RETRYING"
        delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        await _refresh_event_dispatch_state(db, event)
    await db.flush()
    return False


async def retry_delivery(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    delivery_id: uuid.UUID,
    settings: Settings | None = None,
) -> WebhookDelivery:
    delivery = await db.scalar(
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .where(WebhookDelivery.id == delivery_id, WebhookEndpoint.tenant_id == tenant_id)
    )
    if delivery is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Delivery not found"})
    delivery.status = "PENDING"
    delivery.terminal_failure = False
    delivery.next_attempt_at = datetime.now(UTC)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="webhook_delivery",
        entity_id=delivery.id,
        action="manual_retry",
        after=serialize_delivery(delivery),
    )
    await db.flush()
    await _attempt_delivery(db, delivery, settings or get_settings())
    return delivery
