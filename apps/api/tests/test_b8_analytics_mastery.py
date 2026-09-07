"""B8 analytics + mastery evidence integration coverage."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.base import Base
from app.db.models import Assessment, MasteryEvidence, QuestionEvaluation, Tenant
from app.db.session import async_session_factory
from tests.test_a2_gate_matrix import _foundation
from tests.test_b3_submission_ingestion import _headers
from tests.test_b4_answer_region_mapping import _add_leaf
from tests.test_b7_publication_reports import _to_approved, api_client_publication


async def _ready_assessment_with_curriculum(
    client: AsyncClient, headers: dict[str, str]
) -> dict:
    """ACTIVE two-leaf assessment with PRIMARY curriculum mappings on both leaves."""
    data = await _foundation(client, headers)
    leaf_a = await _add_leaf(
        client, headers, data, marks="5.00", sequence=1, label="1"
    )
    leaf_b = await _add_leaf(
        client, headers, data, marks="5.00", sequence=2, label="2"
    )
    node_id = data["node"]["id"]
    for leaf in (leaf_a, leaf_b):
        mapping = await client.post(
            f"/api/v1/question-versions/{leaf['id']}/curriculum-mappings",
            headers=headers,
            json={
                "curriculum_node_id": node_id,
                "mapping_type": "PRIMARY",
                "weight": "1.00",
            },
        )
        assert mapping.status_code == 201, mapping.text
    ready = await client.post(
        f"/api/v1/assessments/{data['assessment']['id']}/transition",
        headers=headers,
        json={"to_status": "READY"},
    )
    assert ready.status_code == 200, ready.text
    active = await client.post(
        f"/api/v1/assessments/{data['assessment']['id']}/transition",
        headers=headers,
        json={"to_status": "ACTIVE"},
    )
    assert active.status_code == 200, active.text
    data["leaf_a"] = leaf_a
    data["leaf_b"] = leaf_b
    return data


async def _publish_approved(
    client: AsyncClient,
    headers: dict[str, str],
    submission_id: str,
) -> str:
    """Prepare publication, wait for GENERATED (eager), publish. Returns published_result_id."""
    prep = await client.post(
        f"/api/v1/submissions/{submission_id}/publication/prepare",
        headers=headers,
    )
    assert prep.status_code == 200, prep.text
    prid = prep.json()["published_result_id"]

    workspace = await client.get(
        f"/api/v1/submissions/{submission_id}/publication", headers=headers
    )
    assert workspace.status_code == 200, workspace.text
    latest = workspace.json()["latest"]
    assert latest is not None
    assert latest["status"] == "GENERATED"
    assert latest["id"] == prid

    pub = await client.post(
        f"/api/v1/publication-results/{prid}/publish", headers=headers
    )
    assert pub.status_code == 200, pub.text
    assert pub.json()["status"] == "PUBLISHED"
    return prid


@pytest.mark.asyncio
async def test_b8_approved_unpublished_excluded_then_included_after_publish() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        assessment_id = data["assessment"]["id"]

        before = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}", headers=headers
        )
        assert before.status_code == 200, before.text
        assert before.json()["published_attempt_count"] == 0
        assert before.json()["mean_percentage"] is None
        assert before.json()["pass_threshold_percent"] is None

        prid = await _publish_approved(client, headers, sid)

        after = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}", headers=headers
        )
        assert after.status_code == 200, after.text
        body = after.json()
        assert body["published_attempt_count"] == 1
        assert body["unique_student_count"] == 1
        assert body["source"] == "PUBLISHED_LEDGER"
        assert body["mean_percentage"] is not None
        assert body["median_percentage"] is not None

        # Override was 3.5/5 answered + 0/5 blank → 35%
        assert body["mean_percentage"] == pytest.approx(35.0)
        assert body["median_percentage"] == pytest.approx(35.0)

        # proposed_ai_score ignored: published uses override final, not AI proposal
        async with async_session_factory() as db:
            qes = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.submission_id == uuid.UUID(sid)
                        )
                    )
                ).all()
            )
            answered = next(
                q
                for q in qes
                if q.final_human_approved_score is not None
                and Decimal(q.final_human_approved_score) == Decimal("3.5")
            )
            assert answered.proposed_ai_score is not None
            assert Decimal(answered.proposed_ai_score) != Decimal("3.5")

        # Materialization after publish (eager celery)
        async with async_session_factory() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(MasteryEvidence)
                .where(MasteryEvidence.published_result_id == uuid.UUID(prid))
            )
            assert (count or 0) > 0

        student = await client.get(
            f"/api/v1/analytics/students/{student_id}", headers=headers
        )
        assert student.status_code == 200, student.text
        sbody = student.json()
        assert sbody["published_attempt_count"] == 1
        assert sbody["concept_signals"]
        for sig in sbody["concept_signals"]:
            assert "concept" in sig
            assert "execution" in sig
            assert "procedure" in sig
            assert sig["concept"]["signal"] in {"STRONG", "WEAK", "INCONCLUSIVE"}
            assert sig["execution"]["signal"] in {"STRONG", "WEAK", "INCONCLUSIVE"}


@pytest.mark.asyncio
async def test_b8_zero_published_mean_median_threshold_and_foreign_tenant() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        assessment_id = data["assessment"]["id"]

        zero = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}", headers=headers
        )
        assert zero.status_code == 200, zero.text
        assert zero.json()["published_attempt_count"] == 0
        assert zero.json()["mean_percentage"] is None
        assert zero.json()["median_percentage"] is None
        assert zero.json()["pass_rate"] is None

        # One published
        sid1, _ = await _to_approved(
            client, headers, data, override_answered=Decimal("4")
        )
        await _publish_approved(client, headers, sid1)
        one = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}", headers=headers
        )
        assert one.status_code == 200
        # 4/5 + 0/5 = 40%
        assert one.json()["mean_percentage"] == pytest.approx(40.0)
        assert one.json()["median_percentage"] == pytest.approx(40.0)
        assert one.json()["published_attempt_count"] == 1

        # Two published
        sid2, _ = await _to_approved(
            client, headers, data, override_answered=Decimal("2")
        )
        await _publish_approved(client, headers, sid2)
        two = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}", headers=headers
        )
        assert two.status_code == 200
        # 40% and 20% → mean 30, median 30
        assert two.json()["published_attempt_count"] == 2
        assert two.json()["mean_percentage"] == pytest.approx(30.0)
        assert two.json()["median_percentage"] == pytest.approx(30.0)

        # Optional pass_threshold_percent
        with_thr = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}",
            headers=headers,
            params={"pass_threshold_percent": 35},
        )
        assert with_thr.status_code == 200, with_thr.text
        assert with_thr.json()["pass_threshold_percent"] == 35
        assert with_thr.json()["pass_rate"] == pytest.approx(0.5)

        omitted = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}", headers=headers
        )
        assert omitted.json()["pass_threshold_percent"] is None
        assert omitted.json()["pass_rate"] is None

        # Invalid threshold → 400
        bad = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}",
            headers=headers,
            params={"pass_threshold_percent": 150},
        )
        assert bad.status_code == 400, bad.text

        # Foreign tenant 404 (same pattern as B7): retarget assessment tenant
        async with async_session_factory() as db:
            foreign = Tenant(slug=f"b8-other-{uuid.uuid4().hex[:8]}", name="Other")
            db.add(foreign)
            await db.flush()
            asm = await db.scalar(
                select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
            )
            assert asm is not None
            asm.tenant_id = foreign.id
            await db.commit()

        foreign_get = await client.get(
            f"/api/v1/analytics/assessments/{assessment_id}", headers=headers
        )
        assert foreign_get.status_code == 404


@pytest.mark.asyncio
async def test_b8_blank_not_concept_weak_and_mastery_provenance() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)

        evidence = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-evidence",
            headers=headers,
        )
        assert evidence.status_code == 200, evidence.text
        items = evidence.json()["items"]
        assert items
        for item in items:
            assert item["algorithm_version"] == "B8_V1"
            assert item["source_ledger_snapshot_hash"]
            assert item["published_result_id"] == prid
            assert item["evidence_type"] in {"CONCEPT", "EXECUTION", "PROCEDURE"}
            assert "score_ratio" in item
            assert "academic_error_codes" in item
            assert "reason_codes" in item

        # BLANK leaf must not produce concept WEAK
        blankish = [i for i in items if "BLANK" in (i.get("reason_codes") or [])]
        if not blankish:
            async with async_session_factory() as db:
                rows = list(
                    (
                        await db.scalars(
                            select(MasteryEvidence).where(
                                MasteryEvidence.published_result_id == uuid.UUID(prid)
                            )
                        )
                    ).all()
                )
                blankish_db = [
                    r for r in rows if "BLANK" in (r.reason_codes or [])
                ]
                assert blankish_db, "expected BLANK reason on mastery evidence"
                for r in blankish_db:
                    if r.evidence_type == "CONCEPT":
                        assert r.strength == "INCONCLUSIVE"
                        assert r.strength != "WEAK"
        else:
            for i in blankish:
                if i["evidence_type"] == "CONCEPT":
                    assert i["strength"] == "INCONCLUSIVE"
                    assert i["strength"] != "WEAK"


@pytest.mark.asyncio
async def test_b8_prepare_idempotent_and_no_duplicate_evidence() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _student_id = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)

        async with async_session_factory() as db:
            count1 = await db.scalar(
                select(func.count())
                .select_from(MasteryEvidence)
                .where(MasteryEvidence.published_result_id == uuid.UUID(prid))
            )
            assert (count1 or 0) > 0

        prep1 = await client.post(
            f"/api/v1/analytics/published-results/{prid}/prepare",
            headers=headers,
        )
        assert prep1.status_code == 200, prep1.text
        assert prep1.json()["algorithm_version"] == "B8_V1"
        job_id = prep1.json()["pipeline_job_id"]

        prep2 = await client.post(
            f"/api/v1/analytics/published-results/{prid}/prepare",
            headers=headers,
        )
        assert prep2.status_code == 200, prep2.text
        assert prep2.json()["pipeline_job_id"] == job_id
        assert prep2.json()["job_status"] == "SUCCEEDED"

        async with async_session_factory() as db:
            count2 = await db.scalar(
                select(func.count())
                .select_from(MasteryEvidence)
                .where(MasteryEvidence.published_result_id == uuid.UUID(prid))
            )
            assert count2 == count1

        # No MasteryState model/table — MasteryEvidence only
        import app.db.models as models_pkg

        assert hasattr(models_pkg, "MasteryEvidence")
        assert not hasattr(models_pkg, "MasteryState")
        table_names = set(Base.metadata.tables.keys())
        assert "mastery_states" not in table_names
        assert "mastery_state" not in table_names
