"""B2 integration coverage for authoring read seams needed by the live web adapter."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider, hash_password
from app.db.models import Tenant, User
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


async def _headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _rubric(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    curriculum = await client.post(
        "/api/v1/curricula",
        headers=headers,
        json={"code": f"B2-{suffix}", "name": "B2 Curriculum", "version_label": "1"},
    )
    assert curriculum.status_code == 201, curriculum.text
    assessment = await client.post(
        "/api/v1/assessments",
        headers=headers,
        json={
            "curriculum_id": curriculum.json()["id"],
            "code": f"B2-A-{suffix}",
            "title": "B2 assessment",
            "assessment_type": "EXAM",
            "max_marks": "10.00",
        },
    )
    assert assessment.status_code == 201, assessment.text
    version_id = assessment.json()["initial_version_id"]
    question = await client.post(
        f"/api/v1/assessment-versions/{version_id}/questions",
        headers=headers,
        json={
            "stable_code": "Q1",
            "display_label": "1",
            "sequence": 1,
            "prompt_text": "2 + 2?",
            "max_marks": "10.00",
            "question_type": "SHORT",
            "scoring_mode": "LEAF_SCORABLE",
        },
    )
    assert question.status_code == 201, question.text
    rubric = await client.post(
        f"/api/v1/assessments/{assessment.json()['id']}/rubrics",
        headers=headers,
        json={
            "question_version_id": question.json()["id"],
            "title": "Q1 rubric",
            "provenance": "TEACHER",
        },
    )
    assert rubric.status_code == 201, rubric.text
    rubric_version = await client.post(
        f"/api/v1/rubrics/{rubric.json()['id']}/versions",
        headers=headers,
        json={
            "question_version_id": question.json()["id"],
            "source_type": "TEACHER",
            "status": "DRAFT",
        },
    )
    assert rubric_version.status_code == 201, rubric_version.text
    return rubric.json()["id"], rubric_version.json()["id"]


@pytest.mark.asyncio
async def test_list_rubric_versions_returns_created_versions() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        rubric_id, version_id = await _rubric(client, headers)

        response = await client.get(f"/api/v1/rubrics/{rubric_id}/versions", headers=headers)
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == [version_id]
        assert response.json()[0]["version_number"] == 1
        assert response.json()[0]["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_list_rubric_versions_is_authenticated_and_scoped() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        rubric_id, _ = await _rubric(client, headers)

        assert (await client.get(f"/api/v1/rubrics/{rubric_id}/versions")).status_code == 401
        missing = await client.get(f"/api/v1/rubrics/{uuid.uuid4()}/versions", headers=headers)
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_list_rubric_versions_rejects_foreign_tenant() -> None:
    """Cross-tenant rubric-version discovery must 404 without leaking content."""
    async with api_client() as client:
        tenant_a_headers = await _headers(client)
        rubric_id, version_id = await _rubric(client, tenant_a_headers)

        suffix = uuid.uuid4().hex[:8]
        async with async_session_factory() as db:
            tenant_b = Tenant(slug=f"b2-foreign-{suffix}", name="B2 Foreign Tenant")
            db.add(tenant_b)
            await db.flush()
            tenant_b_user = User(
                tenant_id=tenant_b.id,
                email=f"admin@{suffix}.eduvijna.local",
                display_name="Foreign Admin",
                password_hash=hash_password(ADMIN_PASSWORD),
            )
            db.add(tenant_b_user)
            await db.commit()
            tenant_b_id = tenant_b.id
            tenant_b_user_id = tenant_b_user.id

        tenant_b_token, _ = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=tenant_b_user_id,
                tenant_id=tenant_b_id,
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset({"rubric:read"}),
            )
        )
        tenant_b_headers = {"Authorization": f"Bearer {tenant_b_token}"}

        response = await client.get(
            f"/api/v1/rubrics/{rubric_id}/versions",
            headers=tenant_b_headers,
        )
        assert response.status_code == 404
        body = response.text
        assert str(rubric_id) not in body
        assert str(version_id) not in body
        assert "DRAFT" not in body
        assert "version_number" not in body
