"""A2 release-gate coverage — identifiable cases A2-T01..A2-T24."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import AiExecutionRecord, AuditEvent, Curriculum, Tenant
from app.db.session import async_session_factory
from app.main import create_app
from app.services.assessment_transitions import validate_transition
from app.services.mark_reconciliation import reconcile_marks
from app.services.rubric_reconciliation import reconcile_rubric


@asynccontextmanager
async def gate_client() -> AsyncIterator[AsyncClient]:
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


async def _foundation(
    client: AsyncClient, headers: dict[str, str], *, marks: str = "10.00"
) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:8]
    curriculum = await client.post(
        "/api/v1/curricula",
        headers=headers,
        json={
            "code": f"CUR-{suffix}",
            "name": "Mathematics",
            "version_label": "2026",
            "status": "active",
        },
    )
    assert curriculum.status_code == 201, curriculum.text
    node = await client.post(
        f"/api/v1/curricula/{curriculum.json()['id']}/nodes",
        headers=headers,
        json={
            "node_type": "SUBJECT",
            "code": f"MATH-{suffix}",
            "name": "Mathematics",
            "sequence": 1,
            "metadata": {},
            "status": "active",
        },
    )
    assert node.status_code == 201, node.text
    assessment = await client.post(
        "/api/v1/assessments",
        headers=headers,
        json={
            "curriculum_id": curriculum.json()["id"],
            "subject_node_id": node.json()["id"],
            "code": f"ASM-{suffix}",
            "title": "Gate assessment",
            "assessment_type": "EXAM",
            "max_marks": marks,
            "duration_minutes": 60,
        },
    )
    assert assessment.status_code == 201, assessment.text
    return {
        "curriculum": curriculum.json(),
        "node": node.json(),
        "assessment": assessment.json(),
        "version_id": assessment.json()["initial_version_id"],
    }


@pytest.mark.asyncio
async def test_a2_curriculum_tree_cycles_and_prerequisites() -> None:
    """A2-T01 create/list; T02 tree; T03 parent cycle; T04 prerequisite cycle."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        curriculum_id = data["curriculum"]["id"]
        root_id = data["node"]["id"]
        child = await client.post(
            f"/api/v1/curricula/{curriculum_id}/nodes",
            headers=headers,
            json={
                "parent_id": root_id,
                "node_type": "TOPIC",
                "code": f"ALG-{uuid.uuid4().hex[:6]}",
                "name": "Algebra",
                "sequence": 2,
                "metadata": {"level": 1},
            },
        )
        assert child.status_code == 201
        tree = await client.get(f"/api/v1/curricula/{curriculum_id}/tree", headers=headers)
        assert tree.status_code == 200
        assert tree.json()[0]["children"][0]["id"] == child.json()["id"]
        cycle = await client.patch(
            f"/api/v1/curriculum-nodes/{root_id}",
            headers=headers,
            json={"parent_id": child.json()["id"]},
        )
        assert cycle.status_code == 409
        first = await client.post(
            f"/api/v1/curricula/{curriculum_id}/prerequisites",
            headers=headers,
            json={
                "prerequisite_node_id": root_id,
                "dependent_node_id": child.json()["id"],
                "relationship_type": "REQUIRED",
            },
        )
        assert first.status_code == 201
        reverse = await client.post(
            f"/api/v1/curricula/{curriculum_id}/prerequisites",
            headers=headers,
            json={
                "prerequisite_node_id": child.json()["id"],
                "dependent_node_id": root_id,
                "relationship_type": "RECOMMENDED",
            },
        )
        assert reverse.status_code == 409


@pytest.mark.asyncio
async def test_a2_assessment_question_marks_and_delete() -> None:
    """A2-T05 assessment/version; T06 tree; T07 Decimal reconcile; T08 DRAFT delete."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        container = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "Q1",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "Section A",
                "max_marks": "10.00",
                "question_type": "SECTION",
                "scoring_mode": "CONTAINER_DERIVED",
            },
        )
        assert container.status_code == 201, container.text
        leaf = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "Q1A",
                "parent_question_version_id": container.json()["id"],
                "display_label": "1(a)",
                "sequence": 1,
                "prompt_text": "Solve",
                "max_marks": "10.00",
                "question_type": "STRUCTURED",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        assert leaf.status_code == 201, leaf.text
        tree = await client.get(
            f"/api/v1/assessment-versions/{data['version_id']}/questions", headers=headers
        )
        assert tree.json()[0]["children"][0]["id"] == leaf.json()["id"]
        reconcile = await client.get(
            f"/api/v1/assessment-versions/{data['version_id']}/marks/reconcile",
            headers=headers,
        )
        assert reconcile.json()["valid"] is True
        assert Decimal(reconcile.json()["leaf_marks_total"]) == Decimal("10.00")
        assert (
            await client.delete(f"/api/v1/question-versions/{leaf.json()['id']}", headers=headers)
        ).status_code == 204


@pytest.mark.asyncio
async def test_a2_answer_key_rubric_mapping_and_readiness() -> None:
    """A2-T09..T16 answer key, rubric, mapping, approvals, immutable, READY."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        leaf = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "Q1",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "2+2?",
                "max_marks": "10.00",
                "question_type": "SHORT",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        assert leaf.status_code == 201
        mapping = await client.post(
            f"/api/v1/question-versions/{leaf.json()['id']}/curriculum-mappings",
            headers=headers,
            json={
                "curriculum_node_id": data["node"]["id"],
                "mapping_type": "PRIMARY",
                "weight": "1.00",
            },
        )
        assert mapping.status_code == 201, mapping.text
        key = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/answer-key-versions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "question_version_id": leaf.json()["id"],
                "answer_text": "4",
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert key.status_code == 201, key.text
        approved_key = await client.post(
            f"/api/v1/answer-key-versions/{key.json()['id']}/approve", headers=headers
        )
        assert approved_key.status_code == 200
        immutable = await client.patch(
            f"/api/v1/answer-key-versions/{key.json()['id']}",
            headers=headers,
            json={"answer_text": "five"},
        )
        assert immutable.status_code == 409
        rubric = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/rubrics",
            headers=headers,
            json={
                "question_version_id": leaf.json()["id"],
                "title": "Q1 rubric",
                "provenance": "TEACHER",
            },
        )
        assert rubric.status_code == 201, rubric.text
        rubric_version = await client.post(
            f"/api/v1/rubrics/{rubric.json()['id']}/versions",
            headers=headers,
            json={
                "question_version_id": leaf.json()["id"],
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert rubric_version.status_code == 201, rubric_version.text
        criterion = await client.post(
            f"/api/v1/rubric-versions/{rubric_version.json()['id']}/criteria",
            headers=headers,
            json={
                "criterion_code": "C1",
                "description": "Correct answer",
                "max_marks": "10.00",
                "sequence": 1,
                "scoring_mode": "ADDITIVE",
                "partial_credit_allowed": True,
                "ecf_policy": "ALLOW_METHOD_CREDIT",
                "accepted_equivalents": ["4", "four"],
            },
        )
        assert criterion.status_code == 201, criterion.text
        reconciled = await client.get(
            f"/api/v1/rubric-versions/{rubric_version.json()['id']}/reconcile",
            headers=headers,
        )
        assert reconciled.json()["valid"] is True
        approved_rubric = await client.post(
            f"/api/v1/rubric-versions/{rubric_version.json()['id']}/approve",
            headers=headers,
        )
        assert approved_rubric.status_code == 200, approved_rubric.text
        immutable_rubric = await client.patch(
            f"/api/v1/rubric-versions/{rubric_version.json()['id']}",
            headers=headers,
            json={
                "question_version_id": leaf.json()["id"],
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert immutable_rubric.status_code == 409
        ready = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "READY"


@pytest.mark.asyncio
async def test_a2_readiness_rejects_incomplete_and_transition_invalid() -> None:
    """A2-T17 incomplete readiness; T18 invalid transition."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "Q1",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "Missing approvals",
                "max_marks": "10.00",
                "question_type": "SHORT",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        not_ready = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert not_ready.status_code == 409
        invalid = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "ACTIVE"},
        )
        assert invalid.status_code == 409


@pytest.mark.asyncio
async def test_a2_rbac_tenant_isolation_and_audit() -> None:
    """A2-T19 RBAC; T20 tenant list isolation; T21 cross-tenant 404; T22 audit."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        provider = JwtAuthProvider(get_settings())
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
        )
        context = provider.verify_access_token(login.json()["access_token"])
        denied_token, _ = provider.issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"STUDENT"}),
                permissions=frozenset(),
            )
        )
        assert (
            await client.get(
                "/api/v1/curricula",
                headers={"Authorization": f"Bearer {denied_token}"},
            )
        ).status_code == 403
        async with async_session_factory() as db:
            other = Tenant(slug=f"a2-{uuid.uuid4().hex[:8]}", name="A2 other")
            db.add(other)
            await db.flush()
            foreign = Curriculum(
                tenant_id=other.id,
                code="FOREIGN",
                name="Foreign",
                version_label="1",
                status="active",
            )
            db.add(foreign)
            await db.commit()
            foreign_id = foreign.id
        listed = await client.get("/api/v1/curricula", headers=headers)
        assert all(item["id"] != str(foreign_id) for item in listed.json())
        assert (
            await client.get(f"/api/v1/curricula/{foreign_id}", headers=headers)
        ).status_code == 404
        async with async_session_factory() as db:
            event = await db.scalar(
                select(AuditEvent).where(
                    AuditEvent.entity_id == uuid.UUID(data["assessment"]["id"]),
                    AuditEvent.action == "created",
                )
            )
            assert event is not None


@pytest.mark.asyncio
async def test_a2_ai_unavailable_is_controlled_and_recorded() -> None:
    """A2-T23 controlled 503; T24 execution attempt record."""
    async with gate_client() as client:
        headers = await _headers(client)
        response = await client.post(
            "/api/v1/ai/proposals/answer-key",
            headers=headers,
            json={"question_version_id": str(uuid.uuid4())},
        )
        assert response.status_code == 503
        assert response.json()["error"]["details"]["code"] == "AI_PROVIDER_UNAVAILABLE"
        async with async_session_factory() as db:
            record = await db.scalar(
                select(AiExecutionRecord)
                .where(AiExecutionRecord.operation == "propose_answer_key")
                .order_by(AiExecutionRecord.created_at.desc())
            )
            assert record is not None
            assert record.status == "UNAVAILABLE"


def test_a2_domain_service_edges() -> None:
    """Pure-domain guard coverage for scoring and transitions."""
    with pytest.raises(HTTPException):
        validate_transition("DRAFT", "ACTIVE")
    assert reconcile_marks([], Decimal("0.00")) == (True, Decimal("0.00"))
    assert reconcile_rubric([], Decimal("1.00")) == (False, Decimal("0.00"))
