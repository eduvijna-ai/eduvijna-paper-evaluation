"""A1 release-gate coverage — cases A1-T01..A1-T41 (identifiable assertions)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider, hash_password, verify_password
from app.db.models import (
    AcademicYear,
    AuditEvent,
    ClassSection,
    Guardian,
    Institution,
    Student,
    Tenant,
)
from app.db.session import async_session_factory
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
) -> tuple[dict[str, str], dict[str, Any]]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "tenant_slug": tenant_slug},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


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


@pytest.mark.asyncio
async def test_a1_t01_valid_login() -> None:
    """A1-T01"""
    async with gate_client() as client:
        headers, body = await _login(client)
        assert "access_token" in body
        assert body["token_type"].lower() == "bearer"
        assert body["expires_in"] > 0
        assert "password" not in body
        assert "password_hash" not in body["user"]
        assert headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
async def test_a1_t02_invalid_password_generic() -> None:
    """A1-T02"""
    async with gate_client() as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": "wrong-password", "tenant_slug": "demo"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_a1_t03_unknown_user_generic() -> None:
    """A1-T03"""
    async with gate_client() as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@demo.eduvijna.local",
                "password": ADMIN_PASSWORD,
                "tenant_slug": "demo",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_a1_t04_protected_without_token() -> None:
    """A1-T04"""
    async with gate_client() as client:
        assert (await client.get("/api/v1/students")).status_code == 401


@pytest.mark.asyncio
async def test_a1_t05_malformed_token_rejected() -> None:
    """A1-T05"""
    async with gate_client() as client:
        response = await client.get(
            "/api/v1/students", headers={"Authorization": "Bearer not-a-jwt"}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_a1_t06_expired_token_rejected() -> None:
    """A1-T06"""
    async with gate_client() as client:
        settings = get_settings()
        assert settings.auth_token_secret is not None
        _, body = await _login(client)
        context = JwtAuthProvider(settings).verify_access_token(body["access_token"])
        now = datetime.now(UTC)
        expired = jwt.encode(
            {
                "sub": str(context.user_id),
                "tenant_id": str(context.tenant_id),
                "roles": ["INSTITUTION_ADMIN"],
                "permissions": ["student:read"],
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
                "typ": "access",
            },
            settings.auth_token_secret,
            algorithm=settings.auth_algorithm,
        )
        assert (
            await client.get(
                "/api/v1/students", headers={"Authorization": f"Bearer {expired}"}
            )
        ).status_code == 401
        none_token = jwt.encode(
            {
                "sub": str(context.user_id),
                "tenant_id": str(context.tenant_id),
                "roles": ["INSTITUTION_ADMIN"],
                "permissions": ["student:read"],
                "iat": now,
                "exp": now + timedelta(hours=1),
                "typ": "access",
            },
            key="",
            algorithm="none",
        )
        assert (
            await client.get(
                "/api/v1/students", headers={"Authorization": f"Bearer {none_token}"}
            )
        ).status_code == 401


@pytest.mark.asyncio
async def test_a1_t07_context_from_token_not_body() -> None:
    """A1-T07"""
    async with gate_client() as client:
        headers, login = await _login(client)
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        tenant_id = me.json()["tenant_id"]
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        created = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"CTX-{suffix}",
                "admission_number": None,
                "roll_number": None,
                "full_name": "Context Bound",
                "class_section_id": section["id"],
                "academic_year_id": year["id"],
                "status": "active",
                "tenant_id": str(uuid.uuid4()),
            },
        )
        assert created.status_code in {201, 422}
        if created.status_code == 201:
            assert created.json()["tenant_id"] == tenant_id
        assert "password_hash" not in me.json()
        assert me.json()["id"] == login["user"]["id"]


@pytest.mark.asyncio
async def test_a1_tenancy_isolation_matrix() -> None:
    """A1-T08 T09 T10 T11 T12 T13 T35"""
    async with gate_client() as client:
        headers, login = await _login(client)
        context = JwtAuthProvider(get_settings()).verify_access_token(login["access_token"])
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, f"own-{suffix}")

        async with async_session_factory() as db:
            other = Tenant(slug=f"iso-{suffix}", name="Isolation Tenant")
            db.add(other)
            await db.flush()
            other_inst = Institution(tenant_id=other.id, code="ISO", name="Iso Institution")
            db.add(other_inst)
            await db.flush()
            fyear = AcademicYear(
                tenant_id=other.id,
                institution_id=other_inst.id,
                name=f"FY-{suffix}",
                starts_on=datetime.now(UTC).date(),
                ends_on=datetime.now(UTC).date(),
                is_current=True,
            )
            db.add(fyear)
            await db.flush()
            fsection = ClassSection(
                tenant_id=other.id,
                institution_id=other_inst.id,
                academic_year_id=fyear.id,
                name=f"FS-{suffix}",
                grade_label="10",
            )
            db.add(fsection)
            await db.flush()
            foreign_student = Student(
                tenant_id=other.id,
                institution_id=other_inst.id,
                student_code=f"FS-{suffix}",
                full_name="Foreign",
                status="active",
                class_section_id=fsection.id,
                academic_year_id=fyear.id,
            )
            db.add(foreign_student)
            foreign_guardian = Guardian(
                tenant_id=other.id, display_name="Foreign Guardian", email=None, phone=None
            )
            db.add(foreign_guardian)
            await db.commit()
            foreign_student_id = foreign_student.id
            foreign_section_id = fsection.id
            foreign_guardian_id = foreign_guardian.id

        listed = await client.get("/api/v1/students", headers=headers)
        assert listed.status_code == 200
        assert all(item["id"] != str(foreign_student_id) for item in listed.json())
        assert all(item["tenant_id"] == str(context.tenant_id) for item in listed.json())

        assert (
            await client.get(f"/api/v1/students/{foreign_student_id}", headers=headers)
        ).status_code == 404
        assert (
            await client.patch(
                f"/api/v1/students/{foreign_student_id}",
                headers=headers,
                json={"full_name": "Hacked"},
            )
        ).status_code == 404
        assert (
            await client.get(f"/api/v1/class-sections/{foreign_section_id}", headers=headers)
        ).status_code == 404
        assert (
            await client.get(f"/api/v1/guardians/{foreign_guardian_id}", headers=headers)
        ).status_code == 404

        own = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"OWN-{suffix}",
                "admission_number": None,
                "roll_number": None,
                "full_name": "Own Student",
                "class_section_id": section["id"],
                "academic_year_id": year["id"],
                "status": "active",
            },
        )
        assert own.status_code == 201
        assert own.json()["tenant_id"] == str(context.tenant_id)

        link = await client.post(
            f"/api/v1/students/{own.json()['id']}/guardians/{foreign_guardian_id}",
            headers=headers,
            json={"relationship_type": "parent"},
        )
        assert link.status_code == 404


@pytest.mark.asyncio
async def test_a1_rbac_and_students_crud() -> None:
    """A1-T14 T15 T16 T17 T18 T19 T20"""
    async with gate_client() as client:
        headers, login = await _login(client)
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert "INSTITUTION_ADMIN" in me.json()["roles"]
        assert (await client.get("/api/v1/institution", headers=headers)).status_code == 200

        settings = get_settings()
        context = JwtAuthProvider(settings).verify_access_token(login["access_token"])
        denied_token, _ = JwtAuthProvider(settings).issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"STUDENT"}),
                permissions=frozenset(),
            )
        )
        denied = await client.get(
            "/api/v1/students", headers={"Authorization": f"Bearer {denied_token}"}
        )
        assert denied.status_code == 403

        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        payload = {
            "student_code": f"CR-{suffix}",
            "admission_number": f"A-{suffix}",
            "roll_number": "1",
            "full_name": "Create Student",
            "class_section_id": section["id"],
            "academic_year_id": year["id"],
            "status": "active",
        }
        created = await client.post("/api/v1/students", headers=headers, json=payload)
        assert created.status_code == 201
        student_id = created.json()["id"]
        got = await client.get(f"/api/v1/students/{student_id}", headers=headers)
        assert got.status_code == 200
        assert got.json()["full_name"] == "Create Student"
        updated = await client.patch(
            f"/api/v1/students/{student_id}",
            headers=headers,
            json={"full_name": "Updated Student"},
        )
        assert updated.status_code == 200
        assert updated.json()["full_name"] == "Updated Student"
        dup = await client.post("/api/v1/students", headers=headers, json=payload)
        assert dup.status_code == 409


@pytest.mark.asyncio
async def test_a1_import_and_limits() -> None:
    """A1-T21..T31"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, f"imp-{suffix}")
        year_name = year["name"]
        section_name = section["name"]

        existing = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"EX-{suffix}",
                "admission_number": None,
                "roll_number": None,
                "full_name": "Existing",
                "class_section_id": section["id"],
                "academic_year_id": year["id"],
                "status": "active",
            },
        )
        assert existing.status_code == 201

        async with async_session_factory() as db:
            before = await db.scalar(select(func.count()).select_from(Student))

        csv_body = (
            "student_code,admission_number,roll_number,full_name,academic_year,class_section\n"
            f"V1-{suffix},,1,Valid One,{year_name},{section_name}\n"
            f"V2-{suffix},,2,Valid Two,{year_name},{section_name}\n"
            f"V1-{suffix},,3,Dup File,{year_name},{section_name}\n"
            f"EX-{suffix},,4,Dup Existing,{year_name},{section_name}\n"
            f"U-{suffix},,5,Unknown,{year_name},Missing\n"
            f",,6,Missing Code,{year_name},{section_name}\n"
            f"{'Z' * 101},,7,Invalid,{year_name},{section_name}\n"
        )
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={"file": ("students.csv", csv_body.encode("utf-8"), "text/csv")},
        )
        assert validated.status_code == 200
        outcomes = [row["outcome"] for row in validated.json()["row_results"]]
        assert outcomes == [
            "VALID",
            "VALID",
            "DUPLICATE_IN_FILE",
            "DUPLICATE_EXISTING",
            "UNKNOWN_CLASS",
            "MISSING_REQUIRED_FIELD",
            "INVALID",
        ]

        async with async_session_factory() as db:
            after_validate = await db.scalar(select(func.count()).select_from(Student))
        assert after_validate == before

        async with async_session_factory() as db:
            poison_inst = await db.scalar(select(Institution).where(Institution.code == "DEMO"))
            assert poison_inst is not None
            db.add(
                Student(
                    tenant_id=poison_inst.tenant_id,
                    institution_id=poison_inst.id,
                    student_code=f"V2-{suffix}",
                    full_name="Poison",
                    status="active",
                )
            )
            await db.commit()

        failed = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": validated.json()["import_session_id"]},
        )
        assert failed.status_code == 409
        async with async_session_factory() as db:
            v1 = await db.scalar(
                select(func.count())
                .select_from(Student)
                .where(Student.student_code == f"V1-{suffix}")
            )
        assert v1 == 0

        csv_ok = (
            "student_code,admission_number,roll_number,full_name,academic_year,class_section\n"
            f"OK-{suffix},,9,Commit Ok,{year_name},{section_name}\n"
        )
        ok_val = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={"file": ("ok.csv", csv_ok.encode("utf-8"), "text/csv")},
        )
        assert ok_val.status_code == 200
        session_id = ok_val.json()["import_session_id"]
        committed = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": session_id},
        )
        assert committed.status_code == 200
        assert committed.json()["committed_count"] == 1
        replay = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": session_id},
        )
        assert replay.status_code == 200
        assert replay.json() == committed.json()

        get_settings.cache_clear()
        settings = get_settings()
        original_rows = settings.student_import_max_rows
        settings.student_import_max_rows = 1
        try:
            too_many = (
                "student_code,admission_number,roll_number,full_name,academic_year,class_section\n"
                f"L1-{suffix},,,One,{year_name},{section_name}\n"
                f"L2-{suffix},,,Two,{year_name},{section_name}\n"
            )
            limited = await client.post(
                "/api/v1/students/import/validate",
                headers=headers,
                files={"file": ("limit.csv", too_many.encode("utf-8"), "text/csv")},
            )
            assert limited.status_code == 413
        finally:
            settings.student_import_max_rows = original_rows
            get_settings.cache_clear()


@pytest.mark.asyncio
async def test_a1_guardians_and_audit() -> None:
    """A1-T32 T33 T34 T36 T37 T38 T39 T40 T41 + Argon2"""
    assert verify_password("secret", hash_password("secret"))

    async with gate_client() as client:
        headers, login = await _login(client)
        context = JwtAuthProvider(get_settings()).verify_access_token(login["access_token"])
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, f"aud-{suffix}")

        student = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"AUD-{suffix}",
                "admission_number": None,
                "roll_number": None,
                "full_name": "Audit Student",
                "class_section_id": section["id"],
                "academic_year_id": year["id"],
                "status": "active",
            },
        )
        assert student.status_code == 201
        patched = await client.patch(
            f"/api/v1/students/{student.json()['id']}",
            headers=headers,
            json={"full_name": "Audit Student 2"},
        )
        assert patched.status_code == 200

        guardian = await client.post(
            "/api/v1/guardians",
            headers=headers,
            json={"display_name": "Audit Guardian", "email": None, "phone": None},
        )
        assert guardian.status_code == 201
        linked = await client.post(
            f"/api/v1/students/{student.json()['id']}/guardians/{guardian.json()['id']}",
            headers=headers,
            json={"relationship_type": "parent"},
        )
        assert linked.status_code == 201
        unlinked = await client.delete(
            f"/api/v1/students/{student.json()['id']}/guardians/{guardian.json()['id']}",
            headers=headers,
        )
        assert unlinked.status_code == 204

        csv_body = (
            "student_code,admission_number,roll_number,full_name,academic_year,class_section\n"
            f"IMP-AUD-{suffix},,,Import Audit,{year['name']},{section['name']}\n"
        )
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={"file": ("a.csv", csv_body.encode(), "text/csv")},
        )
        assert validated.status_code == 200
        committed = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": validated.json()["import_session_id"]},
        )
        assert committed.status_code == 200

        async with async_session_factory() as db:
            events = (
                await db.scalars(
                    select(AuditEvent).where(AuditEvent.tenant_id == context.tenant_id)
                )
            ).all()
            actions = {(e.entity_type, e.action) for e in events}
            assert ("Student", "created") in actions
            assert ("Student", "updated") in actions
            assert ("ImportSession", "committed") in actions
            assert ("Guardian", "created") in actions
            assert ("AcademicYear", "created") in actions
            assert ("ClassSection", "created") in actions
            for event in events:
                blob = str(event.payload_json).lower()
                assert "password" not in blob
                assert "token" not in blob
                assert "bearer" not in blob
                assert ADMIN_PASSWORD.lower() not in blob
