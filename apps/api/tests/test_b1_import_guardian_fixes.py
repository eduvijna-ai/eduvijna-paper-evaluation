"""B1 corrective gate — import uniqueness, session errors, guardian list."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.config import get_settings
from app.db.models import ImportSession, Institution, Student, StudentGuardian, Tenant
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


async def _login(client: AsyncClient) -> tuple[dict[str, str], dict[str, Any]]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
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
            "name": f"BY-{suffix}",
            "starts_on": "2036-01-01",
            "ends_on": "2036-12-31",
            "is_current": False,
        },
    )
    assert year.status_code == 201, year.text
    section = await client.post(
        "/api/v1/class-sections",
        headers=headers,
        json={
            "academic_year_id": year.json()["id"],
            "name": f"BC-{suffix}",
            "grade_label": "10",
        },
    )
    assert section.status_code == 201, section.text
    return year.json(), section.json()


def _csv(*lines: str) -> bytes:
    header = "student_code,admission_number,roll_number,full_name,academic_year,class_section"
    return ("\n".join([header, *lines]) + "\n").encode("utf-8")


def _err(response: Any) -> dict[str, Any]:
    return response.json()["error"]


@pytest.mark.asyncio
async def test_b1_fix_be_01_existing_student_code() -> None:
    """B1-FIX-BE-01"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        created = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"EXC-{suffix}",
                "full_name": "Existing Code",
                "class_section_id": section["id"],
                "academic_year_id": year["id"],
                "status": "active",
            },
        )
        assert created.status_code == 201
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(
                        f"EXC-{suffix},,1,Dup,{year['name']},{section['name']}",
                    ),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        row = validated.json()["row_results"][0]
        assert row["outcome"] == "DUPLICATE_EXISTING"
        assert row["reason_code"] == "STUDENT_CODE_DUPLICATE_EXISTING"


@pytest.mark.asyncio
async def test_b1_fix_be_02_existing_class_roll() -> None:
    """B1-FIX-BE-02"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        created = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"EXR-{suffix}",
                "roll_number": "42",
                "full_name": "Existing Roll",
                "class_section_id": section["id"],
                "academic_year_id": year["id"],
                "status": "active",
            },
        )
        assert created.status_code == 201
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"NEW-{suffix},,42,Other,{year['name']},{section['name']}"),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        row = validated.json()["row_results"][0]
        assert row["outcome"] == "DUPLICATE_EXISTING"
        assert row["reason_code"] == "CLASS_ROLL_DUPLICATE_EXISTING"


@pytest.mark.asyncio
async def test_b1_fix_be_03_same_roll_different_class() -> None:
    """B1-FIX-BE-03"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section_a = await _year_and_section(client, headers, f"{suffix}a")
        section_b = await client.post(
            "/api/v1/class-sections",
            headers=headers,
            json={
                "academic_year_id": year["id"],
                "name": f"BC-{suffix}b",
                "grade_label": "10",
            },
        )
        assert section_b.status_code == 201
        created = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"RA-{suffix}",
                "roll_number": "7",
                "full_name": "In A",
                "class_section_id": section_a["id"],
                "academic_year_id": year["id"],
                "status": "active",
            },
        )
        assert created.status_code == 201
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"RB-{suffix},,7,In B,{year['name']},{section_b.json()['name']}"),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        assert validated.json()["row_results"][0]["outcome"] == "VALID"


@pytest.mark.asyncio
async def test_b1_fix_be_04_cross_tenant_no_leak() -> None:
    """B1-FIX-BE-04"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        async with async_session_factory() as db:
            other = Tenant(slug=f"other-{suffix}", name="Other")
            db.add(other)
            await db.flush()
            other_inst = Institution(tenant_id=other.id, code="OTH", name="Other Inst")
            db.add(other_inst)
            await db.flush()
            db.add(
                Student(
                    tenant_id=other.id,
                    institution_id=other_inst.id,
                    student_code=f"FOREIGN-{suffix}",
                    roll_number="99",
                    full_name="Foreign",
                    status="active",
                )
            )
            await db.commit()
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(
                        f"FOREIGN-{suffix},ADM,99,Local,{year['name']},{section['name']}",
                    ),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        row = validated.json()["row_results"][0]
        assert row["outcome"] == "VALID"
        assert "reason_code" not in row
        assert "Isolation" not in validated.text
        assert "other-" not in validated.text.lower()


@pytest.mark.asyncio
async def test_b1_fix_be_05_infile_student_code_duplicate() -> None:
    """B1-FIX-BE-05"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(
                        f"DUP-{suffix},,1,One,{year['name']},{section['name']}",
                        f"DUP-{suffix},,2,Two,{year['name']},{section['name']}",
                    ),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        outcomes = validated.json()["row_results"]
        assert outcomes[0]["outcome"] == "VALID"
        assert outcomes[1]["outcome"] == "DUPLICATE_IN_FILE"
        assert outcomes[1]["reason_code"] == "STUDENT_CODE_DUPLICATE_IN_FILE"


@pytest.mark.asyncio
async def test_b1_fix_be_06_infile_class_roll_duplicate() -> None:
    """B1-FIX-BE-06"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(
                        f"A-{suffix},,5,One,{year['name']},{section['name']}",
                        f"B-{suffix},,5,Two,{year['name']},{section['name']}",
                    ),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        outcomes = validated.json()["row_results"]
        assert outcomes[0]["outcome"] == "VALID"
        assert outcomes[1]["outcome"] == "DUPLICATE_IN_FILE"
        assert outcomes[1]["reason_code"] == "CLASS_ROLL_DUPLICATE_IN_FILE"


@pytest.mark.asyncio
async def test_b1_fix_be_07_empty_rolls_allowed() -> None:
    """B1-FIX-BE-07"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(
                        f"E1-{suffix},,,Empty One,{year['name']},{section['name']}",
                        f"E2-{suffix},,,Empty Two,{year['name']},{section['name']}",
                    ),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        assert [r["outcome"] for r in validated.json()["row_results"]] == ["VALID", "VALID"]


@pytest.mark.asyncio
async def test_b1_fix_be_08_validation_writes_zero_students() -> None:
    """B1-FIX-BE-08"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        async with async_session_factory() as db:
            before = await db.scalar(select(func.count()).select_from(Student))
        await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"Z-{suffix},,1,Zero,{year['name']},{section['name']}"),
                    "text/csv",
                )
            },
        )
        async with async_session_factory() as db:
            after = await db.scalar(select(func.count()).select_from(Student))
        assert after == before


@pytest.mark.asyncio
async def test_b1_fix_be_09_valid_import_commits() -> None:
    """B1-FIX-BE-09"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        code = f"OK-{suffix}"
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"{code},ADM-1,11,Commit Ok,{year['name']},{section['name']}"),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        committed = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": validated.json()["import_session_id"]},
        )
        assert committed.status_code == 200
        assert committed.json()["committed_count"] == 1
        listed = await client.get("/api/v1/students", headers=headers)
        assert any(s["student_code"] == code for s in listed.json())


@pytest.mark.asyncio
async def test_b1_fix_be_10_race_conflict() -> None:
    """B1-FIX-BE-10"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        code = f"RACE-{suffix}"
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"{code},,12,Race,{year['name']},{section['name']}"),
                    "text/csv",
                )
            },
        )
        assert validated.status_code == 200
        async with async_session_factory() as db:
            inst = await db.scalar(select(Institution).where(Institution.code == "DEMO"))
            assert inst is not None
            db.add(
                Student(
                    tenant_id=inst.tenant_id,
                    institution_id=inst.id,
                    student_code=code,
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
        err = _err(failed)
        assert err["code"] == "STUDENT_IMPORT_CONFLICT"
        assert "revalidate" in err["message"].lower()
        assert "integrity" not in failed.text.lower()
        assert "unique" not in failed.text.lower()
        assert "sql" not in failed.text.lower()


@pytest.mark.asyncio
async def test_b1_fix_be_11_expired_session() -> None:
    """B1-FIX-BE-11"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"EXP-{suffix},,13,Exp,{year['name']},{section['name']}"),
                    "text/csv",
                )
            },
        )
        session_id = validated.json()["import_session_id"]
        async with async_session_factory() as db:
            session = await db.scalar(
                select(ImportSession).where(ImportSession.id == uuid.UUID(session_id))
            )
            assert session is not None
            session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await db.commit()
        failed = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": session_id},
        )
        assert failed.status_code == 409
        assert _err(failed)["code"] == "IMPORT_SESSION_EXPIRED"


@pytest.mark.asyncio
async def test_b1_fix_be_12_invalid_session() -> None:
    """B1-FIX-BE-12"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"INV-{suffix},,14,Inv,{year['name']},{section['name']}"),
                    "text/csv",
                )
            },
        )
        session_id = validated.json()["import_session_id"]
        async with async_session_factory() as db:
            session = await db.scalar(
                select(ImportSession).where(ImportSession.id == uuid.UUID(session_id))
            )
            assert session is not None
            session.status = "EXPIRED"
            await db.commit()
        failed = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": session_id},
        )
        assert failed.status_code == 409
        assert _err(failed)["code"] == "IMPORT_SESSION_INVALID"


@pytest.mark.asyncio
async def test_b1_fix_be_13_committed_replay() -> None:
    """B1-FIX-BE-13"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"REP-{suffix},,15,Replay,{year['name']},{section['name']}"),
                    "text/csv",
                )
            },
        )
        session_id = validated.json()["import_session_id"]
        first = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": session_id},
        )
        assert first.status_code == 200
        second = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": session_id},
        )
        assert second.status_code == 200
        assert second.json() == first.json()


@pytest.mark.asyncio
async def test_b1_fix_be_14_raw_db_exception_hidden() -> None:
    """B1-FIX-BE-14"""
    async with gate_client() as client:
        headers, _ = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        code = f"HID-{suffix}"
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={
                "file": (
                    "t.csv",
                    _csv(f"{code},,16,Hide,{year['name']},{section['name']}"),
                    "text/csv",
                )
            },
        )
        async with async_session_factory() as db:
            inst = await db.scalar(select(Institution).where(Institution.code == "DEMO"))
            assert inst is not None
            db.add(
                Student(
                    tenant_id=inst.tenant_id,
                    institution_id=inst.id,
                    student_code=code,
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
        body = failed.text.lower()
        assert failed.status_code == 409
        assert "psycopg" not in body
        assert "sqlalchemy" not in body
        assert "duplicate key" not in body
        assert "traceback" not in body


@pytest.mark.asyncio
async def test_b1_fix_be_15_16_17_18_guardian_get() -> None:
    """B1-FIX-BE-15..18"""
    async with gate_client() as client:
        headers, login = await _login(client)
        suffix = uuid.uuid4().hex[:8]
        year, section = await _year_and_section(client, headers, suffix)
        student = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"G-{suffix}",
                "full_name": "Guardian Student",
                "class_section_id": section["id"],
                "academic_year_id": year["id"],
                "status": "active",
            },
        )
        assert student.status_code == 201
        student_id = student.json()["id"]

        empty = await client.get(
            f"/api/v1/students/{student_id}/guardians", headers=headers
        )
        assert empty.status_code == 200
        assert empty.json() == []

        guardian = await client.post(
            "/api/v1/guardians",
            headers=headers,
            json={"display_name": f"Parent {suffix}", "email": f"p-{suffix}@ex.com"},
        )
        assert guardian.status_code == 201
        guardian_id = guardian.json()["id"]
        linked = await client.post(
            f"/api/v1/students/{student_id}/guardians/{guardian_id}",
            headers=headers,
            json={"relationship_type": "PARENT"},
        )
        assert linked.status_code == 201

        listed = await client.get(
            f"/api/v1/students/{student_id}/guardians", headers=headers
        )
        assert listed.status_code == 200
        rows = listed.json()
        assert len(rows) == 1
        assert rows[0]["student_id"] == student_id
        assert rows[0]["guardian_id"] == guardian_id
        assert rows[0]["display_name"] == f"Parent {suffix}"
        assert rows[0]["relationship_type"] == "PARENT"
        assert rows[0]["email"] == f"p-{suffix}@ex.com"

        # Permission enforced
        no_auth = await client.get(f"/api/v1/students/{student_id}/guardians")
        assert no_auth.status_code == 401

        # Cross-tenant student protected
        async with async_session_factory() as db:
            other = Tenant(slug=f"goth-{suffix}", name="G Other")
            db.add(other)
            await db.flush()
            other_inst = Institution(tenant_id=other.id, code="GOT", name="G Inst")
            db.add(other_inst)
            await db.flush()
            foreign = Student(
                tenant_id=other.id,
                institution_id=other_inst.id,
                student_code=f"FG-{suffix}",
                full_name="Foreign G",
                status="active",
            )
            db.add(foreign)
            await db.flush()
            foreign_id = foreign.id
            await db.commit()
        cross = await client.get(
            f"/api/v1/students/{foreign_id}/guardians", headers=headers
        )
        assert cross.status_code == 404
        assert "Parent" not in cross.text

        # Foreign guardian must never appear via join leak
        async with async_session_factory() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(StudentGuardian)
                .where(StudentGuardian.student_id == uuid.UUID(student_id))
            )
        assert count == 1
