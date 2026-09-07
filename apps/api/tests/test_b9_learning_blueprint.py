"""B9 learning plan + improvement blueprint integration coverage."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.models import (
    Assessment,
    LearningPlanRun,
    MasteryEvidence,
    Question,
    Tenant,
)
from app.db.session import async_session_factory
from tests.test_a2_gate_matrix import _foundation
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)


async def _force_concept_weak(
    *,
    student_id: str,
    curriculum_id: str,
    node_id: str | None = None,
) -> None:
    async with async_session_factory() as db:
        q = select(MasteryEvidence).where(
            MasteryEvidence.student_id == uuid.UUID(student_id),
            MasteryEvidence.curriculum_id == uuid.UUID(curriculum_id),
            MasteryEvidence.evidence_type == "CONCEPT",
            MasteryEvidence.algorithm_version == "B8_V1",
        )
        if node_id:
            q = q.where(MasteryEvidence.curriculum_node_id == uuid.UUID(node_id))
        rows = list((await db.scalars(q)).all())
        assert rows, "expected B8 mastery evidence rows"
        for r in rows:
            r.strength = "WEAK"
            r.reason_codes = list(set((r.reason_codes or []) + ["CONCEPT"]))
            r.academic_error_codes = list(
                set((r.academic_error_codes or []) + ["CONCEPT"])
            )
        await db.commit()


@pytest.mark.asyncio
async def test_b9_prepare_ready_blueprint_approve_no_assessment() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)

        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]
        assessment_id = data["assessment"]["id"]

        foreign = await client.get(
            f"/api/v1/learning/students/{uuid.uuid4()}", headers=headers
        )
        assert foreign.status_code == 404

        await _force_concept_weak(
            student_id=student_id, curriculum_id=curriculum_id, node_id=node_id
        )

        async with async_session_factory() as db:
            asm = await db.scalar(
                select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
            )
            assert asm is not None
            tenant_id = asm.tenant_id
            assessment_count_before = await db.scalar(
                select(func.count())
                .select_from(Assessment)
                .where(Assessment.tenant_id == tenant_id)
            )
            question_count_before = await db.scalar(
                select(func.count())
                .select_from(Question)
                .where(Question.tenant_id == tenant_id)
            )

        prep = await client.post(
            f"/api/v1/learning/students/{student_id}/prepare",
            headers=headers,
            json={"curriculum_id": curriculum_id},
        )
        assert prep.status_code == 200, prep.text
        body = prep.json()
        assert body["status"] == "READY"
        assert body["algorithm_version"] == "B9_V1"
        run_id = body["run_id"]

        prep2 = await client.post(
            f"/api/v1/learning/students/{student_id}/prepare",
            headers=headers,
            json={"curriculum_id": curriculum_id},
        )
        assert prep2.status_code == 200, prep2.text
        assert prep2.json()["run_id"] == run_id

        plan = await client.get(
            f"/api/v1/learning/plan-runs/{run_id}", headers=headers
        )
        assert plan.status_code == 200, plan.text
        plan_body = plan.json()
        assert plan_body["status"] == "READY"
        assert plan_body["is_stale"] is False
        assert plan_body["recommendations"]
        assert any(
            r["recommendation_kind"] == "TARGET_CONCEPT"
            for r in plan_body["recommendations"]
        )
        for r in plan_body["recommendations"]:
            assert r["mastery_evidence_ids"]
            lower = r["rationale"].lower()
            assert "http://" not in lower
            assert "https://" not in lower
            assert "www." not in lower

        workspace = await client.get(
            f"/api/v1/learning/students/{student_id}",
            headers=headers,
            params={"curriculum_id": curriculum_id},
        )
        assert workspace.status_code == 200, workspace.text
        assert workspace.json()["materialization_status"] == "READY"
        assert workspace.json()["latest_plan"]["id"] == run_id

        bp_prep = await client.post(
            f"/api/v1/learning/plan-runs/{run_id}/improvement-blueprints/prepare",
            headers=headers,
        )
        assert bp_prep.status_code == 200, bp_prep.text
        bp_id = bp_prep.json()["improvement_assessment_id"]
        assert bp_prep.json()["status"] == "PENDING_APPROVAL"

        bp = await client.get(
            f"/api/v1/improvement-assessments/{bp_id}", headers=headers
        )
        assert bp.status_code == 200, bp.text
        bp_body = bp.json()
        assert bp_body["status"] == "PENDING_APPROVAL"
        assert bp_body["items"]
        assert bp_body["blueprint_sha256"]
        for item in bp_body["items"]:
            assert item["question_template_ref"].startswith("CVB:")
            assert "http" not in item["focus"].lower()

        approve = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/approve",
            headers=headers,
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["status"] == "APPROVED"

        async with async_session_factory() as db:
            assessment_count_after = await db.scalar(
                select(func.count())
                .select_from(Assessment)
                .where(Assessment.tenant_id == tenant_id)
            )
            question_count_after = await db.scalar(
                select(func.count())
                .select_from(Question)
                .where(Question.tenant_id == tenant_id)
            )
        assert assessment_count_after == assessment_count_before
        assert question_count_after == question_count_before


@pytest.mark.asyncio
async def test_b9_evidence_not_ready_and_foreign_run() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        student_id = data["student"]["id"] if "student" in data else None
        # Foundation has no student — create via learning path with random UUID
        if student_id is None:
            # Use a nonexistent student under tenant → 404, or create curriculum-only case
            prep = await client.post(
                f"/api/v1/learning/students/{uuid.uuid4()}/prepare",
                headers=headers,
                json={"curriculum_id": data["curriculum"]["id"]},
            )
            assert prep.status_code == 404
        else:
            prep = await client.post(
                f"/api/v1/learning/students/{student_id}/prepare",
                headers=headers,
                json={"curriculum_id": data["curriculum"]["id"]},
            )
            assert prep.status_code == 409, prep.text
            assert prep.json()["detail"]["code"] == "LEARNING_EVIDENCE_NOT_READY"

        # Published path then check not-ready is harder; use student from published flow
        # with materialization blocked: create assessment flow then call prepare before publish
        data2 = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data2)
        # APPROVED but not published → materialization NOT_STARTED
        prep = await client.post(
            f"/api/v1/learning/students/{student_id}/prepare",
            headers=headers,
            json={"curriculum_id": data2["curriculum"]["id"]},
        )
        assert prep.status_code == 409, prep.text
        body = prep.json()
        code = None
        if isinstance(body.get("detail"), dict):
            code = body["detail"].get("code")
        if code is None and isinstance(body.get("error"), dict):
            code = body["error"].get("code")
        assert code == "LEARNING_EVIDENCE_NOT_READY"

        foreign_run = await client.get(
            f"/api/v1/learning/plan-runs/{uuid.uuid4()}", headers=headers
        )
        assert foreign_run.status_code == 404

        foreign_bp = await client.get(
            f"/api/v1/improvement-assessments/{uuid.uuid4()}", headers=headers
        )
        assert foreign_bp.status_code == 404

        # Unused sid keeps linter quiet about approval path
        assert sid


@pytest.mark.asyncio
async def test_b9_prerequisite_ordering_and_reject() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        curriculum_id = data["curriculum"]["id"]
        node_b_id = data["node"]["id"]

        node_a_resp = await client.post(
            f"/api/v1/curricula/{curriculum_id}/nodes",
            headers=headers,
            json={
                "node_type": "TOPIC",
                "code": f"A-{uuid.uuid4().hex[:6]}",
                "name": "Linear Equations",
                "parent_id": node_b_id,
                "sequence": 0,
                "metadata": {},
                "status": "active",
            },
        )
        assert node_a_resp.status_code == 201, node_a_resp.text
        node_a_id = node_a_resp.json()["id"]

        prereq = await client.post(
            f"/api/v1/curricula/{curriculum_id}/prerequisites",
            headers=headers,
            json={
                "prerequisite_node_id": node_a_id,
                "dependent_node_id": node_b_id,
                "relationship_type": "REQUIRED",
            },
        )
        assert prereq.status_code == 201, prereq.text

        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        await _force_concept_weak(
            student_id=student_id, curriculum_id=curriculum_id, node_id=node_b_id
        )

        async with async_session_factory() as db:
            sample = await db.scalar(
                select(MasteryEvidence).where(
                    MasteryEvidence.student_id == uuid.UUID(student_id),
                    MasteryEvidence.curriculum_id == uuid.UUID(curriculum_id),
                    MasteryEvidence.evidence_type == "CONCEPT",
                )
            )
            assert sample is not None
            db.add(
                MasteryEvidence(
                    tenant_id=sample.tenant_id,
                    student_id=sample.student_id,
                    curriculum_id=sample.curriculum_id,
                    curriculum_node_id=uuid.UUID(node_a_id),
                    published_result_id=sample.published_result_id,
                    submission_id=sample.submission_id,
                    assessment_id=sample.assessment_id,
                    assessment_version_id=sample.assessment_version_id,
                    evaluation_run_id=sample.evaluation_run_id,
                    question_evaluation_id=sample.question_evaluation_id,
                    question_version_id=sample.question_version_id,
                    evidence_type="CONCEPT",
                    strength="WEAK",
                    score_ratio=Decimal("0.200000"),
                    source_final_score=sample.source_final_score,
                    source_max_mark=sample.source_max_mark,
                    mapping_types=["PRIMARY"],
                    mapping_weight=Decimal("1.0"),
                    academic_error_codes=["CONCEPT"],
                    review_condition_codes=[],
                    reason_codes=["CONCEPT"],
                    source_ledger_snapshot_hash=sample.source_ledger_snapshot_hash,
                    algorithm_version="B8_V1",
                )
            )
            await db.commit()

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
        path = plan.json()["learning_path"]
        assert path
        ids = [s["curriculum_node_id"] for s in path]
        assert node_a_id in ids
        assert node_b_id in ids
        assert ids.index(node_a_id) < ids.index(node_b_id)

        bp_prep = await client.post(
            f"/api/v1/learning/plan-runs/{run_id}/improvement-blueprints/prepare",
            headers=headers,
        )
        assert bp_prep.status_code == 200, bp_prep.text
        bp_id = bp_prep.json()["improvement_assessment_id"]

        reject = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reject",
            headers=headers,
            json={"reason": "Needs tighter focus on prerequisites"},
        )
        assert reject.status_code == 200, reject.text
        assert reject.json()["status"] == "REJECTED"

        async with async_session_factory() as db:
            foreign = Tenant(slug=f"b9-other-{uuid.uuid4().hex[:8]}", name="Other")
            db.add(foreign)
            await db.flush()
            run = await db.scalar(
                select(LearningPlanRun).where(LearningPlanRun.id == uuid.UUID(run_id))
            )
            assert run is not None
            run.tenant_id = foreign.id
            await db.commit()

        stolen = await client.get(
            f"/api/v1/learning/plan-runs/{run_id}", headers=headers
        )
        assert stolen.status_code == 404
