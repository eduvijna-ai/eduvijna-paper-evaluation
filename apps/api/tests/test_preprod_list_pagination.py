"""Production-safe list pagination bounds for hot list endpoints."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.pagination import clamp_limit, clamp_offset
from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.config import get_settings
from app.main import create_app


@asynccontextmanager
async def gate_client() -> AsyncIterator[AsyncClient]:
    await seed()
    get_settings.cache_clear()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client


async def _login(
    client: AsyncClient,
    *,
    email: str = ADMIN_EMAIL,
    password: str = ADMIN_PASSWORD,
    tenant_slug: str = "demo",
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "tenant_slug": tenant_slug},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


async def _year_and_section(
    client: AsyncClient, headers: dict[str, str], suffix: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    year = await client.post(
        "/api/v1/academic-years",
        headers=headers,
        json={
            "name": f"Y-{suffix}",
            "starts_on": "2035-01-01",
            "ends_on": "2035-12-31",
            "is_current": False,
        },
    )
    assert year.status_code == 201, year.text
    section = await client.post(
        "/api/v1/class-sections",
        headers=headers,
        json={
            "academic_year_id": year.json()["id"],
            "name": f"C-{suffix}",
            "grade_label": "10",
        },
    )
    assert section.status_code == 201, section.text
    return year.json(), section.json()


def test_clamp_limit_defaults_and_caps() -> None:
    assert clamp_limit(None) == 100
    assert clamp_limit(0) == 1
    assert clamp_limit(-5) == 1
    assert clamp_limit(1) == 1
    assert clamp_limit(500) == 500
    assert clamp_limit(501) == 500
    assert clamp_limit(9999) == 500


def test_clamp_offset_non_negative() -> None:
    assert clamp_offset(None) == 0
    assert clamp_offset(0) == 0
    assert clamp_offset(10) == 10
    assert clamp_offset(-3) == 0


@pytest.mark.asyncio
async def test_students_list_default_cap_and_limit_one() -> None:
    async with gate_client() as client:
        headers = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        for i in range(3):
            created = await client.post(
                "/api/v1/students",
                headers=headers,
                json={
                    "student_code": f"PAG-{suffix}-{i}",
                    "admission_number": f"ADM-{suffix}-{i}",
                    "roll_number": f"R{i}",
                    "full_name": f"Pag Student {suffix} {i}",
                    "academic_year_id": year["id"],
                    "class_section_id": section["id"],
                    "status": "active",
                },
            )
            assert created.status_code == 201, created.text

        default_list = await client.get("/api/v1/students", headers=headers)
        assert default_list.status_code == 200, default_list.text
        body = default_list.json()
        assert isinstance(body, list)
        assert len(body) <= 100

        limited = await client.get("/api/v1/students", headers=headers, params={"limit": 1})
        assert limited.status_code == 200, limited.text
        limited_body = limited.json()
        assert isinstance(limited_body, list)
        assert len(limited_body) <= 1
        assert len(limited_body) == 1


@pytest.mark.asyncio
async def test_guardians_and_assessments_limit_one() -> None:
    async with gate_client() as client:
        headers = await _login(client)

        for i in range(2):
            g = await client.post(
                "/api/v1/guardians",
                headers=headers,
                json={
                    "display_name": f"Pag Guardian {uuid.uuid4().hex[:6]}-{i}",
                    "email": f"pag-g-{uuid.uuid4().hex[:8]}@demo.eduvijna.local",
                    "phone": None,
                },
            )
            assert g.status_code == 201, g.text

        guardians = await client.get(
            "/api/v1/guardians", headers=headers, params={"limit": 1}
        )
        assert guardians.status_code == 200, guardians.text
        assert isinstance(guardians.json(), list)
        assert len(guardians.json()) <= 1

        curricula = await client.get(
            "/api/v1/curricula", headers=headers, params={"limit": 1}
        )
        assert curricula.status_code == 200, curricula.text
        assert isinstance(curricula.json(), list)
        assert len(curricula.json()) <= 1

        assessments = await client.get(
            "/api/v1/assessments", headers=headers, params={"limit": 1}
        )
        assert assessments.status_code == 200, assessments.text
        assert isinstance(assessments.json(), list)
        assert len(assessments.json()) <= 1

        submissions = await client.get(
            "/api/v1/submissions", headers=headers, params={"limit": 1}
        )
        assert submissions.status_code == 200, submissions.text
        assert isinstance(submissions.json(), list)
        assert len(submissions.json()) <= 1
