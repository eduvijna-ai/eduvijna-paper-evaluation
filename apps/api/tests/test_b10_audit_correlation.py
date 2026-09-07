"""B10 PEV-072 audit correlation ID propagation and construction guard."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.db.models import AuditEvent
from app.db.session import async_session_factory
from app.main import create_app
from app.middleware.correlation import (
    MAX_CORRELATION_ID_LENGTH,
    get_correlation_id,
    normalize_correlation_id,
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
ALLOWLIST_AUDIT_EVENT_CTOR = {
    (APP_ROOT / "services" / "audit.py").resolve(),
    (APP_ROOT / "db" / "models" / "audit.py").resolve(),
}
_AUDIT_EVENT_CTOR = re.compile(r"\bAuditEvent\s*\(")


async def _login(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_client_correlation_id_echoed_and_stored() -> None:
    await seed()
    correlation = f"b10-corr-{uuid.uuid4().hex[:12]}"
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        headers = await _login(client)
        headers["X-Correlation-ID"] = correlation
        suffix = uuid.uuid4().hex[:8]
        year = await client.post(
            "/api/v1/academic-years",
            headers=headers,
            json={
                "name": f"Year-{suffix}",
                "starts_on": "2031-06-01",
                "ends_on": "2032-05-31",
                "is_current": False,
            },
        )
        assert year.status_code == 201, year.text
        assert year.headers["X-Correlation-ID"] == correlation
        year_id = year.json()["id"]

    async with async_session_factory() as db:
        events = list(
            (
                await db.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_id == uuid.UUID(year_id),
                        AuditEvent.action == "created",
                    )
                )
            ).all()
        )
        assert events
        assert all(e.correlation_id == correlation for e in events)


@pytest.mark.asyncio
async def test_missing_correlation_header_generates_and_stores() -> None:
    await seed()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        headers = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year = await client.post(
            "/api/v1/academic-years",
            headers=headers,
            json={
                "name": f"Year-{suffix}",
                "starts_on": "2032-06-01",
                "ends_on": "2033-05-31",
                "is_current": False,
            },
        )
        assert year.status_code == 201, year.text
        generated = year.headers["X-Correlation-ID"]
        assert generated
        assert generated != ""
        year_id = year.json()["id"]

    async with async_session_factory() as db:
        event = await db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == uuid.UUID(year_id),
                AuditEvent.action == "created",
            )
        )
        assert event is not None
        assert event.correlation_id == generated


@pytest.mark.asyncio
async def test_multiple_audit_events_same_request_share_correlation_id() -> None:
    await seed()
    correlation = f"b10-multi-{uuid.uuid4().hex[:12]}"
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        headers = await _login(client)
        headers["X-Correlation-ID"] = correlation
        suffix = uuid.uuid4().hex[:8]
        year = await client.post(
            "/api/v1/academic-years",
            headers=headers,
            json={
                "name": f"Year-{suffix}",
                "starts_on": "2033-06-01",
                "ends_on": "2034-05-31",
                "is_current": False,
            },
        )
        assert year.status_code == 201, year.text
        year_id = year.json()["id"]
        section = await client.post(
            "/api/v1/class-sections",
            headers=headers,
            json={
                "academic_year_id": year_id,
                "name": f"A-{suffix}",
                "grade_label": "Grade 8",
            },
        )
        assert section.status_code == 201, section.text
        section_id = section.json()["id"]
        student = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"ST-{suffix}",
                "admission_number": f"ADM-{suffix}",
                "roll_number": f"R-{suffix}",
                "full_name": "Correlation Student",
                "class_section_id": section_id,
                "academic_year_id": year_id,
                "status": "active",
            },
        )
        assert student.status_code == 201, student.text
        student_id = student.json()["id"]

    entity_ids = {uuid.UUID(year_id), uuid.UUID(section_id), uuid.UUID(student_id)}
    async with async_session_factory() as db:
        events = list(
            (
                await db.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_id.in_(entity_ids),
                        AuditEvent.action == "created",
                    )
                )
            ).all()
        )
        assert len(events) >= 3
        # Each create is its own request; verify per-response echo and that stored
        # IDs are non-null. Same-request multi-event check uses middleware ContextVar.
        assert all(e.correlation_id for e in events)

    # Same-request multi-event: ContextVar + two writes without HTTP round-trip.
    from app.middleware.correlation import _correlation_id_ctx
    from app.services.audit import add_audit_event

    token = _correlation_id_ctx.set(correlation)
    try:
        assert get_correlation_id() == correlation
        async with async_session_factory() as db:
            e1 = await add_audit_event(
                db,
                tenant_id=None,
                actor_user_id=None,
                entity_type="UnitTest",
                entity_id=uuid.uuid4(),
                action="corr_a",
                after={"n": 1},
            )
            e2 = await add_audit_event(
                db,
                tenant_id=None,
                actor_user_id=None,
                entity_type="UnitTest",
                entity_id=uuid.uuid4(),
                action="corr_b",
                after={"n": 2},
            )
            await db.commit()
            assert e1.correlation_id == correlation
            assert e2.correlation_id == correlation
    finally:
        _correlation_id_ctx.reset(token)


def test_normalize_correlation_id_bounds_and_charset() -> None:
    assert normalize_correlation_id("ok-id_1.2") == "ok-id_1.2"
    bad = normalize_correlation_id("has space")
    assert bad != "has space"
    too_long = "a" * (MAX_CORRELATION_ID_LENGTH + 1)
    assert normalize_correlation_id(too_long) != too_long


def test_forbid_direct_audit_event_construction_outside_allowlist() -> None:
    offenders: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        resolved = path.resolve()
        if resolved in ALLOWLIST_AUDIT_EVENT_CTOR:
            continue
        text = path.read_text(encoding="utf-8")
        if _AUDIT_EVENT_CTOR.search(text):
            offenders.append(str(resolved.relative_to(APP_ROOT)))
    assert offenders == [], f"Direct AuditEvent( outside allowlist: {offenders}"
