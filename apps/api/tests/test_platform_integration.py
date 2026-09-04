import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import AuditEvent, Institution, Student, Tenant
from app.db.session import async_session_factory
from app.main import create_app


async def _login(client: AsyncClient) -> tuple[dict[str, str], dict[str, object]]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
    )
    assert response.status_code == 200
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


@pytest.mark.asyncio
async def test_auth_tenant_rbac_crud_import_and_audit() -> None:
    await seed()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        bad = await client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": "wrong", "tenant_slug": "demo"},
        )
        assert bad.status_code == 401
        assert bad.json()["error"]["message"] == "Invalid credentials"

        headers, login = await _login(client)
        token = login["access_token"]
        assert isinstance(token, str)
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert "INSTITUTION_ADMIN" in me.json()["roles"]
        assert "student:import" in me.json()["permissions"]
        assert (await client.get("/api/v1/institution", headers=headers)).status_code == 200

        suffix = uuid.uuid4().hex[:8]
        year_response = await client.post(
            "/api/v1/academic-years",
            headers=headers,
            json={
                "name": f"Year-{suffix}",
                "starts_on": "2030-06-01",
                "ends_on": "2031-05-31",
                "is_current": False,
            },
        )
        assert year_response.status_code == 201
        year = year_response.json()
        section_response = await client.post(
            "/api/v1/class-sections",
            headers=headers,
            json={
                "academic_year_id": year["id"],
                "name": f"A-{suffix}",
                "grade_label": "Grade 8",
            },
        )
        assert section_response.status_code == 201
        section = section_response.json()

        student_payload = {
            "student_code": f"ST-{suffix}",
            "admission_number": f"ADM-{suffix}",
            "roll_number": f"R-{suffix}",
            "full_name": "Synthetic Student",
            "class_section_id": section["id"],
            "academic_year_id": year["id"],
            "status": "active",
        }
        created = await client.post("/api/v1/students", headers=headers, json=student_payload)
        assert created.status_code == 201
        student = created.json()
        duplicate = await client.post("/api/v1/students", headers=headers, json=student_payload)
        assert duplicate.status_code == 409
        patched = await client.patch(
            f"/api/v1/students/{student['id']}",
            headers=headers,
            json={"full_name": "Synthetic Student Updated"},
        )
        assert patched.status_code == 200

        guardian_response = await client.post(
            "/api/v1/guardians",
            headers=headers,
            json={"display_name": "Synthetic Guardian", "email": None, "phone": "5550100"},
        )
        assert guardian_response.status_code == 201
        guardian = guardian_response.json()
        linked = await client.post(
            f"/api/v1/students/{student['id']}/guardians/{guardian['id']}",
            headers=headers,
            json={"relationship_type": "parent"},
        )
        assert linked.status_code == 201
        unlinked = await client.delete(
            f"/api/v1/students/{student['id']}/guardians/{guardian['id']}", headers=headers
        )
        assert unlinked.status_code == 204

        csv_body = (
            "student_code,admission_number,roll_number,full_name,academic_year,class_section\n"
            f"IMP-{suffix},AI-{suffix},RI-{suffix},Import Valid,Year-{suffix},A-{suffix}\n"
            f"IMP-{suffix},AI2,RI2,Duplicate File,Year-{suffix},A-{suffix}\n"
            f"ST-{suffix},,,Already Exists,Year-{suffix},A-{suffix}\n"
            f"UNKNOWN-{suffix},,,Unknown Class,Year-{suffix},Missing\n"
            f",,,Missing Code,Year-{suffix},A-{suffix}\n"
            f"{'X' * 101},,,Invalid Code,Year-{suffix},A-{suffix}\n"
        )
        validated = await client.post(
            "/api/v1/students/import/validate",
            headers=headers,
            files={"file": ("students.csv", csv_body.encode(), "text/csv")},
        )
        assert validated.status_code == 200
        validation = validated.json()
        outcomes = [row["outcome"] for row in validation["row_results"]]
        assert outcomes == [
            "VALID",
            "DUPLICATE_IN_FILE",
            "DUPLICATE_EXISTING",
            "UNKNOWN_CLASS",
            "MISSING_REQUIRED_FIELD",
            "INVALID",
        ]
        committed = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": validation["import_session_id"]},
        )
        assert committed.status_code == 200
        assert committed.json()["committed_count"] == 1
        replay = await client.post(
            "/api/v1/students/import/commit",
            headers=headers,
            json={"import_session_id": validation["import_session_id"]},
        )
        assert replay.status_code == 200
        assert replay.json() == committed.json()

        context = JwtAuthProvider(get_settings()).verify_access_token(token)
        forbidden_token, _ = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"STUDENT"}),
                permissions=frozenset(),
            )
        )
        forbidden = await client.get(
            "/api/v1/students", headers={"Authorization": f"Bearer {forbidden_token}"}
        )
        assert forbidden.status_code == 403

        async with async_session_factory() as db:
            other_tenant = Tenant(slug=f"other-{suffix}", name="Other Tenant")
            db.add(other_tenant)
            await db.flush()
            other_institution = Institution(
                tenant_id=other_tenant.id, code="OTHER", name="Other Institution"
            )
            db.add(other_institution)
            await db.flush()
            foreign_student = Student(
                tenant_id=other_tenant.id,
                institution_id=other_institution.id,
                student_code=f"FOREIGN-{suffix}",
                full_name="Foreign Student",
                status="active",
                class_section_id=None,
                academic_year_id=None,
            )
            db.add(foreign_student)
            await db.commit()
            foreign_id = foreign_student.id
        isolated = await client.get(f"/api/v1/students/{foreign_id}", headers=headers)
        assert isolated.status_code == 404

        async with async_session_factory() as db:
            imported_count = await db.scalar(
                select(func.count())
                .select_from(Student)
                .where(
                    Student.tenant_id == context.tenant_id,
                    Student.student_code == f"IMP-{suffix}",
                )
            )
            audit_count = await db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.tenant_id == context.tenant_id)
            )
        assert imported_count == 1
        assert audit_count is not None and audit_count >= 7
