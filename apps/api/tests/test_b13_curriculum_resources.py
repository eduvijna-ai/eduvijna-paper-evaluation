"""B13 curriculum resource catalog + student assignment coverage (PEV-041)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import (
    LearningRecommendation,
    MasteryEvidence,
    MasteryState,
    MistakeNotebookEntry,
)
from app.db.session import async_session_factory
from app.services.resources import ResourceError, reject_open_web_content_ref
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
from tests.test_b9_learning_blueprint import _force_concept_weak


def test_reject_open_web_content_ref_unit() -> None:
    reject_open_web_content_ref("internal://catalog/packet-1")
    reject_open_web_content_ref("cvb:packet:algebra-1")
    for bad in ("http://evil.example/x", "HTTPS://evil.example/x", "//cdn.example/x"):
        with pytest.raises(ResourceError) as exc:
            reject_open_web_content_ref(bad)
        assert exc.value.code == "RESOURCE_OPEN_WEB_REJECTED"


async def _create_active_resource(
    client,
    headers: dict[str, str],
    *,
    curriculum_id: str,
    node_id: str,
    code: str = "RES-ALG-01",
    content_ref: str = "internal://catalog/alg-practice-1",
) -> dict:
    created = await client.post(
        "/api/v1/learning/resources",
        headers=headers,
        json={
            "curriculum_id": curriculum_id,
            "code": code,
            "title": "Algebra practice packet",
            "description": "Institution packet",
            "resource_kind": "PRACTICE_SET",
            "content_ref": content_ref,
            "curriculum_node_ids": [node_id],
        },
    )
    assert created.status_code == 201, created.text
    resource_id = created.json()["id"]
    assert created.json()["status"] == "DRAFT"

    mapped = await client.put(
        f"/api/v1/learning/resources/{resource_id}/nodes",
        headers=headers,
        json={"curriculum_node_ids": [node_id]},
    )
    assert mapped.status_code == 200, mapped.text

    approved = await client.post(
        f"/api/v1/learning/resources/{resource_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    activated = await client.post(
        f"/api/v1/learning/resources/{resource_id}/activate",
        headers=headers,
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "ACTIVE"
    return activated.json()


@pytest.mark.asyncio
async def test_b13_create_approve_activate_assign_workspace() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)

        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]

        async with async_session_factory() as db:
            evidence_before = await db.scalar(select(func.count()).select_from(MasteryEvidence))
            mastery_before = await db.scalar(select(func.count()).select_from(MasteryState))
            notebook_before = await db.scalar(
                select(func.count()).select_from(MistakeNotebookEntry)
            )

        resource = await _create_active_resource(
            client, headers, curriculum_id=curriculum_id, node_id=node_id
        )
        resource_id = resource["id"]

        catalog = await client.get(
            "/api/v1/learning/resources",
            headers=headers,
            params={"curriculum_id": curriculum_id, "status": "ACTIVE"},
        )
        assert catalog.status_code == 200, catalog.text
        assert any(item["id"] == resource_id for item in catalog.json()["items"])

        assigned = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={"resource_id": resource_id},
        )
        assert assigned.status_code == 200, assigned.text
        body = assigned.json()
        assert body["status"] == "ASSIGNED"
        assert body["resource"]["id"] == resource_id
        assert body["learning_recommendation_id"] is None
        assignment_id = body["id"]

        listed = await client.get(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            params={"curriculum_id": curriculum_id},
        )
        assert listed.status_code == 200, listed.text
        assert any(item["id"] == assignment_id for item in listed.json()["items"])

        workspace = await client.get(
            f"/api/v1/learning/students/{student_id}",
            headers=headers,
            params={"curriculum_id": curriculum_id},
        )
        assert workspace.status_code == 200, workspace.text
        ws = workspace.json()
        assert "materialization_status" in ws
        assert any(
            item["id"] == assignment_id for item in ws.get("resource_assignments", [])
        )

        async with async_session_factory() as db:
            evidence_after = await db.scalar(select(func.count()).select_from(MasteryEvidence))
            mastery_after = await db.scalar(select(func.count()).select_from(MasteryState))
            notebook_after = await db.scalar(
                select(func.count()).select_from(MistakeNotebookEntry)
            )
        assert evidence_after == evidence_before
        assert mastery_after == mastery_before
        assert notebook_after == notebook_before


@pytest.mark.asyncio
async def test_b13_tenant_isolation_and_status_gates() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]

        draft = await client.post(
            "/api/v1/learning/resources",
            headers=headers,
            json={
                "curriculum_id": curriculum_id,
                "code": "RES-DRAFT-01",
                "title": "Draft only",
                "resource_kind": "CONCEPT_NOTE",
                "content_ref": "internal://catalog/draft-1",
                "curriculum_node_ids": [node_id],
            },
        )
        assert draft.status_code == 201, draft.text
        draft_id = draft.json()["id"]

        cannot_assign_draft = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={"resource_id": draft_id},
        )
        assert cannot_assign_draft.status_code == 409
        assert cannot_assign_draft.json()["error"]["code"] == "RESOURCE_NOT_ASSIGNABLE"

        resource = await _create_active_resource(
            client,
            headers,
            curriculum_id=curriculum_id,
            node_id=node_id,
            code="RES-ACTIVE-01",
        )
        resource_id = resource["id"]

        assigned = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={"resource_id": resource_id},
        )
        assert assigned.status_code == 200, assigned.text
        assignment_id = assigned.json()["id"]

        deactivated = await client.post(
            f"/api/v1/learning/resources/{resource_id}/deactivate",
            headers=headers,
        )
        assert deactivated.status_code == 200, deactivated.text
        assert deactivated.json()["status"] == "DEACTIVATED"

        listed = await client.get(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            params={"status": "ASSIGNED"},
        )
        assert listed.status_code == 200
        assert any(item["id"] == assignment_id for item in listed.json()["items"])

        # New assign after deactivate (cancel historical first so grain is free)
        cancelled = await client.post(
            f"/api/v1/learning/resource-assignments/{assignment_id}/cancel",
            headers=headers,
        )
        assert cancelled.status_code == 200, cancelled.text

        cannot_new_assign = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={"resource_id": resource_id},
        )
        assert cannot_new_assign.status_code == 409
        assert cannot_new_assign.json()["error"]["code"] == "RESOURCE_NOT_ASSIGNABLE"

        foreign = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset(
                    {
                        "learning:read",
                        "learning:assign",
                        "curriculum:manage",
                        "learning:approve",
                    }
                ),
            )
        )[0]
        foreign_headers = {"Authorization": f"Bearer {foreign}"}
        assert (
            await client.get(
                f"/api/v1/learning/resources/{resource_id}",
                headers=foreign_headers,
            )
        ).status_code == 404
        assert (
            await client.post(
                f"/api/v1/learning/students/{student_id}/resource-assignments",
                headers=foreign_headers,
                json={"resource_id": resource_id},
            )
        ).status_code == 404


@pytest.mark.asyncio
async def test_b13_idempotent_assign_and_cancel() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]

        resource = await _create_active_resource(
            client,
            headers,
            curriculum_id=curriculum_id,
            node_id=node_id,
            code="RES-IDEMP-01",
        )
        resource_id = resource["id"]

        first = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={"resource_id": resource_id},
        )
        assert first.status_code == 200, first.text
        second = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={"resource_id": resource_id},
        )
        assert second.status_code == 200, second.text
        assert second.json()["id"] == first.json()["id"]

        cancelled = await client.post(
            f"/api/v1/learning/resource-assignments/{first.json()['id']}/cancel",
            headers=headers,
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "CANCELLED"
        assert cancelled.json()["cancelled_at"] is not None

        history = await client.get(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            params={"status": "CANCELLED"},
        )
        assert history.status_code == 200
        assert any(item["id"] == first.json()["id"] for item in history.json()["items"])


@pytest.mark.asyncio
async def test_b13_recommendation_linkage_and_open_web_reject() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]

        open_web = await client.post(
            "/api/v1/learning/resources",
            headers=headers,
            json={
                "curriculum_id": curriculum_id,
                "code": "RES-WEB-01",
                "title": "Bad web",
                "resource_kind": "CONCEPT_NOTE",
                "content_ref": "https://example.com/lesson",
                "curriculum_node_ids": [node_id],
            },
        )
        assert open_web.status_code == 409
        assert open_web.json()["error"]["code"] == "RESOURCE_OPEN_WEB_REJECTED"

        resource = await _create_active_resource(
            client,
            headers,
            curriculum_id=curriculum_id,
            node_id=node_id,
            code="RES-REC-01",
        )
        resource_id = resource["id"]

        patch_title = await client.patch(
            f"/api/v1/learning/resources/{resource_id}",
            headers=headers,
            json={"title": "Still active title"},
        )
        assert patch_title.status_code == 200, patch_title.text

        draft = await client.post(
            "/api/v1/learning/resources",
            headers=headers,
            json={
                "curriculum_id": curriculum_id,
                "code": "RES-WEB-02",
                "title": "Draft for patch",
                "resource_kind": "INTERNAL_PACKET",
                "content_ref": "internal://ok",
                "curriculum_node_ids": [node_id],
            },
        )
        assert draft.status_code == 201, draft.text
        bad_patch = await client.patch(
            f"/api/v1/learning/resources/{draft.json()['id']}",
            headers=headers,
            json={"content_ref": "http://open.web/bad"},
        )
        assert bad_patch.status_code == 409
        assert bad_patch.json()["error"]["code"] == "RESOURCE_OPEN_WEB_REJECTED"

        await _force_concept_weak(
            student_id=student_id, curriculum_id=curriculum_id, node_id=node_id
        )
        prep = await client.post(
            f"/api/v1/learning/students/{student_id}/prepare",
            headers=headers,
            json={"curriculum_id": curriculum_id},
        )
        assert prep.status_code == 200, prep.text
        run_id = prep.json()["run_id"]
        plan = await client.get(
            f"/api/v1/learning/plan-runs/{run_id}", headers=headers
        )
        assert plan.status_code == 200, plan.text
        recommendations = plan.json()["recommendations"]
        assert recommendations
        rec_id = recommendations[0]["id"]

        async with async_session_factory() as db:
            rec_before = await db.scalar(
                select(LearningRecommendation).where(
                    LearningRecommendation.id == uuid.UUID(rec_id)
                )
            )
            assert rec_before is not None
            status_before = rec_before.status
            rationale_before = rec_before.rationale
            updated_before = rec_before.updated_at

        linked = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={
                "resource_id": resource_id,
                "learning_recommendation_id": rec_id,
            },
        )
        assert linked.status_code == 200, linked.text
        assert linked.json()["learning_recommendation_id"] == rec_id

        async with async_session_factory() as db:
            rec_after = await db.scalar(
                select(LearningRecommendation).where(
                    LearningRecommendation.id == uuid.UUID(rec_id)
                )
            )
            assert rec_after is not None
            assert rec_after.status == status_before
            assert rec_after.rationale == rationale_before
            assert rec_after.updated_at == updated_before

        async with async_session_factory() as db:
            rec = await db.scalar(
                select(LearningRecommendation).where(
                    LearningRecommendation.id == uuid.UUID(rec_id)
                )
            )
            assert rec is not None
            rec.status = "DISMISSED"
            await db.commit()

        other = await _create_active_resource(
            client,
            headers,
            curriculum_id=curriculum_id,
            node_id=node_id,
            code="RES-REC-02",
        )
        dismissed2 = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={
                "resource_id": other["id"],
                "learning_recommendation_id": rec_id,
            },
        )
        assert dismissed2.status_code == 409
        assert dismissed2.json()["error"]["code"] == "RESOURCE_RECOMMENDATION_INCOMPATIBLE"

        foreign_rec = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=headers,
            json={
                "resource_id": other["id"],
                "learning_recommendation_id": str(uuid.uuid4()),
            },
        )
        assert foreign_rec.status_code == 404


@pytest.mark.asyncio
async def test_b13_learning_assign_permission_required() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]

        resource = await _create_active_resource(
            client,
            headers,
            curriculum_id=curriculum_id,
            node_id=node_id,
            code="RES-PERM-01",
        )

        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@demo.eduvijna.local",
                "password": "DemoAdmin!2026",
                "tenant_slug": "demo",
            },
        )
        assert login.status_code == 200, login.text
        context = JwtAuthProvider(get_settings()).verify_access_token(
            login.json()["access_token"]
        )
        read_only = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"EVALUATOR"}),
                permissions=frozenset({"learning:read"}),
            )
        )[0]
        ro_headers = {"Authorization": f"Bearer {read_only}"}

        denied = await client.post(
            f"/api/v1/learning/students/{student_id}/resource-assignments",
            headers=ro_headers,
            json={"resource_id": resource["id"]},
        )
        assert denied.status_code == 403

        catalog = await client.get("/api/v1/learning/resources", headers=ro_headers)
        assert catalog.status_code == 200
