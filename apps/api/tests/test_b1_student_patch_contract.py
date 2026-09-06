"""B1 student PATCH regression coverage for optional academic assignment."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.config import get_settings
from app.db.models import AcademicYear, ClassSection, Institution, Tenant
from app.db.session import async_session_factory
from app.main import create_app


@asynccontextmanager
async def api_client() -> AsyncIterator[AsyncClient]:
    await seed()
    get_settings.cache_clear()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client


async def _login(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _create_year_section(
    client: AsyncClient, headers: dict[str, str], suffix: str
) -> tuple[dict[str, object], dict[str, object]]:
    year_response = await client.post(
        "/api/v1/academic-years",
        headers=headers,
        json={
            "name": f"PATCH-{suffix}",
            "starts_on": "2040-01-01",
            "ends_on": "2040-12-31",
            "is_current": False,
        },
    )
    assert year_response.status_code == 201, year_response.text
    year = year_response.json()
    section_response = await client.post(
        "/api/v1/class-sections",
        headers=headers,
        json={
            "academic_year_id": year["id"],
            "name": f"SEC-{suffix}",
            "grade_label": "Grade 10",
        },
    )
    assert section_response.status_code == 201, section_response.text
    return year, section_response.json()


@pytest.mark.asyncio
async def test_unassigned_student_can_be_edited_without_assignment() -> None:
    async with api_client() as client:
        headers = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        created = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"UNASSIGNED-{suffix}",
                "full_name": "Unassigned Student",
                "academic_year_id": None,
                "class_section_id": None,
                "status": "active",
            },
        )
        assert created.status_code == 201, created.text
        student_id = created.json()["id"]
        assert created.json()["academic_year_id"] is None
        assert created.json()["class_section_id"] is None

        renamed = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={"full_name": "Unassigned Student Renamed"},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["full_name"] == "Unassigned Student Renamed"
        assert renamed.json()["academic_year_id"] is None
        assert renamed.json()["class_section_id"] is None

        recoded = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={"student_code": f"UNASSIGNED-EDIT-{suffix}"},
        )
        assert recoded.status_code == 200, recoded.text
        assert recoded.json()["student_code"] == f"UNASSIGNED-EDIT-{suffix}"

        explicit_nulls = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={
                "full_name": "Still Unassigned",
                "academic_year_id": None,
                "class_section_id": None,
            },
        )
        assert explicit_nulls.status_code == 200, explicit_nulls.text
        assert explicit_nulls.json()["academic_year_id"] is None
        assert explicit_nulls.json()["class_section_id"] is None


@pytest.mark.asyncio
async def test_student_patch_rejects_mixed_and_mismatched_assignment() -> None:
    async with api_client() as client:
        headers = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year_a, section_a = await _create_year_section(client, headers, f"{suffix}-a")
        year_b, section_b = await _create_year_section(client, headers, f"{suffix}-b")
        created = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"PAIR-{suffix}",
                "full_name": "Pair Validation",
                "academic_year_id": None,
                "class_section_id": None,
                "status": "active",
            },
        )
        assert created.status_code == 201, created.text
        student_id = created.json()["id"]

        year_only = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={"academic_year_id": year_a["id"]},
        )
        assert year_only.status_code == 422

        section_only = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={"class_section_id": section_a["id"]},
        )
        assert section_only.status_code == 422

        mismatch = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={
                "academic_year_id": year_a["id"],
                "class_section_id": section_b["id"],
            },
        )
        assert mismatch.status_code == 422
        assert "does not belong" in mismatch.json()["error"]["message"].lower()

        valid_pair = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={
                "academic_year_id": year_b["id"],
                "class_section_id": section_b["id"],
            },
        )
        assert valid_pair.status_code == 200, valid_pair.text


@pytest.mark.asyncio
async def test_student_patch_rejects_cross_tenant_assignment() -> None:
    async with api_client() as client:
        headers = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        created = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"TENANT-{suffix}",
                "full_name": "Tenant Scoped Student",
                "academic_year_id": None,
                "class_section_id": None,
                "status": "active",
            },
        )
        assert created.status_code == 201, created.text
        student_id = created.json()["id"]

        async with async_session_factory() as db:
            other_tenant = Tenant(slug=f"patch-other-{suffix}", name="Patch Other")
            db.add(other_tenant)
            await db.flush()
            institution = Institution(
                tenant_id=other_tenant.id,
                code=f"P{suffix[:6]}",
                name="Patch Other Institution",
            )
            db.add(institution)
            await db.flush()
            foreign_year = AcademicYear(
                tenant_id=other_tenant.id,
                institution_id=institution.id,
                name=f"Foreign-{suffix}",
                starts_on=date(2041, 1, 1),
                ends_on=date(2041, 12, 31),
                is_current=False,
            )
            db.add(foreign_year)
            await db.flush()
            foreign_section = ClassSection(
                tenant_id=other_tenant.id,
                institution_id=institution.id,
                academic_year_id=foreign_year.id,
                name=f"ForeignSec-{suffix}",
                grade_label="Grade 10",
            )
            db.add(foreign_section)
            await db.commit()
            foreign_year_id = str(foreign_year.id)
            foreign_section_id = str(foreign_section.id)

        response = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={
                "academic_year_id": foreign_year_id,
                "class_section_id": foreign_section_id,
            },
        )
        assert response.status_code == 404
        assert "other" not in response.text.lower()
        assert foreign_year_id not in response.text
        assert foreign_section_id not in response.text
