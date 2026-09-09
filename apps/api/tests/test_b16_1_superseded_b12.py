"""B16.1 Blocker B — superseded PublishedResult must not drive current B12 projections."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.ai.providers.benchmark import MODEL_PASS
from app.db.models import (
    EvaluationRun,
    MasteryEvidence,
    MasteryState,
    MasteryStateSnapshot,
    MistakeNotebookEntry,
    PublishedResult,
    QuestionEvaluation,
)
from app.db.session import async_session_factory
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
from tests.test_b12_longitudinal_intelligence import _force_evidence
from tests.test_b15_gold_benchmark_regression import (
    _create_locked_version,
    _run_body,
)
from tests.test_b16_enterprise_ops import _publish, _review_all_and_finalize


def _notebook_entries(body: dict) -> list[dict]:
    return body.get("entries") or body.get("items") or []


@pytest.mark.asyncio
async def test_b16_1_grievance_v1_v2_no_double_count_b12() -> None:
    """V1→V2 grievance revision is one attempt for current mastery/mistake projections."""
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(
            client, headers, data, override_answered=Decimal("3.00")
        )
        v1_prid = await _publish_approved(client, headers, sid)

        rebuild1 = await client.post(
            f"/api/v1/analytics/students/{student_id}/b12/rebuild",
            headers=headers,
        )
        assert rebuild1.status_code == 200, rebuild1.text

        await _force_evidence(student_id=student_id, academic_codes=["CALCULATION"])
        rebuild1b = await client.post(
            f"/api/v1/analytics/students/{student_id}/b12/rebuild",
            headers=headers,
        )
        assert rebuild1b.status_code == 200, rebuild1b.text

        notebook_v1 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mistake-notebook",
            headers=headers,
        )
        assert notebook_v1.status_code == 200, notebook_v1.text
        v1_calc = [
            i
            for i in _notebook_entries(notebook_v1.json())
            if i["academic_error_code"] == "CALCULATION"
        ]
        assert len(v1_calc) >= 1
        assert all(i["published_result_id"] == v1_prid for i in v1_calc)

        trend_v1 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-trend",
            headers=headers,
        )
        assert trend_v1.status_code == 200, trend_v1.text
        assert any(
            p["published_result_id"] == v1_prid for p in trend_v1.json()["points"]
        )

        state_v1 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-state",
            headers=headers,
        )
        assert state_v1.status_code == 200, state_v1.text
        assert len(state_v1.json()["items"]) >= 1

        async with async_session_factory() as db:
            v1_pr = await db.get(PublishedResult, uuid.UUID(v1_prid))
            assert v1_pr is not None
            original_run_id = v1_pr.evaluation_run_id

        g = await client.post(
            "/api/v1/operations/grievances",
            headers=headers,
            json={
                "published_result_id": v1_prid,
                "requester_reference": "b16-1-parent",
                "reason": "Calculation was mis-marked",
            },
        )
        assert g.status_code == 200, g.text
        accept = await client.post(
            f"/api/v1/operations/grievances/{g.json()['id']}/accept",
            headers=headers,
            json={"decision_reason": "Valid recheck"},
        )
        assert accept.status_code == 200, accept.text
        new_run_id = uuid.UUID(accept.json()["reevaluation_run_id"])

        async with async_session_factory() as db:
            new_run = await db.get(EvaluationRun, new_run_id)
            assert new_run is not None
            assert new_run.run_kind == "RE_EVALUATION"
            assert new_run.supersedes_run_id == original_run_id
            assert new_run.run_number >= 2
            new_qes = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.evaluation_run_id == new_run_id
                        )
                    )
                ).all()
            )
            assert new_qes
            for qe in new_qes:
                assert qe.final_human_approved_score is None
                assert qe.reviewed_by is None
                assert qe.reviewed_at is None
                assert qe.approved_snapshot_hash is None

        fin = await _review_all_and_finalize(client, headers, sid)
        assert fin["workflow_state"] == "APPROVED"
        v2_prid = await _publish(client, headers, sid)

        async with async_session_factory() as db:
            v1 = await db.get(PublishedResult, uuid.UUID(v1_prid))
            v2 = await db.get(PublishedResult, uuid.UUID(v2_prid))
            assert v1 is not None and v2 is not None
            assert v1.status == "SUPERSEDED"
            assert v2.status == "PUBLISHED"
            assert v2.supersedes_result_id == v1.id
            v1_ev_count = await db.scalar(
                select(func.count())
                .select_from(MasteryEvidence)
                .where(MasteryEvidence.published_result_id == v1.id)
            )
            assert v1_ev_count and v1_ev_count > 0

        rebuild2 = await client.post(
            f"/api/v1/analytics/students/{student_id}/b12/rebuild",
            headers=headers,
        )
        assert rebuild2.status_code == 200, rebuild2.text

        async with async_session_factory() as db:
            v2_rows = list(
                (
                    await db.scalars(
                        select(MasteryEvidence).where(
                            MasteryEvidence.published_result_id == uuid.UUID(v2_prid)
                        )
                    )
                ).all()
            )
            assert v2_rows
            for r in v2_rows:
                r.academic_error_codes = []
            await db.commit()

        rebuild2b = await client.post(
            f"/api/v1/analytics/students/{student_id}/b12/rebuild",
            headers=headers,
        )
        assert rebuild2b.status_code == 200, rebuild2b.text
        hash_after = rebuild2b.json().get("source_evidence_hash")

        analytics = await client.get(
            f"/api/v1/analytics/assessments/{data['assessment']['id']}",
            headers=headers,
        )
        assert analytics.status_code == 200, analytics.text
        assert analytics.json()["published_attempt_count"] == 1

        student_analytics = await client.get(
            f"/api/v1/analytics/students/{student_id}",
            headers=headers,
        )
        assert student_analytics.status_code == 200, student_analytics.text
        assert student_analytics.json()["published_attempt_count"] == 1

        notebook_v2 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mistake-notebook",
            headers=headers,
        )
        assert notebook_v2.status_code == 200, notebook_v2.text
        assert not any(
            i["published_result_id"] == v1_prid
            for i in _notebook_entries(notebook_v2.json())
        )
        assert not any(
            i["academic_error_code"] == "CALCULATION"
            and i["published_result_id"] == v1_prid
            for i in _notebook_entries(notebook_v2.json())
        )

        async with async_session_factory() as db:
            stored_v1 = await db.scalar(
                select(func.count())
                .select_from(MistakeNotebookEntry)
                .where(
                    MistakeNotebookEntry.published_result_id == uuid.UUID(v1_prid),
                    MistakeNotebookEntry.academic_error_code == "CALCULATION",
                )
            )
            assert stored_v1 and stored_v1 >= 1
            snap_v1 = await db.scalar(
                select(func.count())
                .select_from(MasteryStateSnapshot)
                .where(MasteryStateSnapshot.published_result_id == uuid.UUID(v1_prid))
            )
            assert snap_v1 is not None
            states = list(
                (
                    await db.scalars(
                        select(MasteryState).where(
                            MasteryState.student_id == uuid.UUID(student_id),
                            MasteryState.algorithm_version == "B12_V1",
                        )
                    )
                ).all()
            )
            assert states

        trend_v2 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-trend",
            headers=headers,
        )
        assert trend_v2.status_code == 200, trend_v2.text
        trend_prs = {p["published_result_id"] for p in trend_v2.json()["points"]}
        assert v2_prid in trend_prs
        assert v1_prid not in trend_prs

        state_v2 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-state",
            headers=headers,
        )
        assert state_v2.status_code == 200, state_v2.text
        assert len(state_v2.json()["items"]) >= 1

        repeated = await client.get(
            f"/api/v1/analytics/students/{student_id}/repeated-errors",
            headers=headers,
        )
        assert repeated.status_code == 200, repeated.text
        calc_items = [
            i
            for i in repeated.json().get("items", [])
            if i.get("error_code") == "CALCULATION"
        ]
        for item in calc_items:
            # Superseded V1 must not inflate recurrence with V2
            assert item.get("distinct_published_result_count", 0) <= 1

        recoverable = await client.get(
            f"/api/v1/analytics/students/{student_id}/recoverable-marks",
            headers=headers,
        )
        assert recoverable.status_code == 200, recoverable.text

        rebuild3 = await client.post(
            f"/api/v1/analytics/students/{student_id}/b12/rebuild",
            headers=headers,
        )
        assert rebuild3.status_code == 200, rebuild3.text
        assert rebuild3.json().get("source_evidence_hash") == hash_after

        notebook_again = await client.get(
            f"/api/v1/analytics/students/{student_id}/mistake-notebook",
            headers=headers,
        )
        assert _notebook_entries(notebook_again.json()) == _notebook_entries(
            notebook_v2.json()
        )


@pytest.mark.asyncio
async def test_b16_1_b15_locked_case_survives_supersession() -> None:
    """Locked B15 gold referencing V1 remains valid after V1 becomes SUPERSEDED."""
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(
            client, headers, code=f"B161-{uuid.uuid4().hex[:8].upper()}"
        )
        v1_prid = ctx["prid"]
        sid = ctx["sid"]

        ds_id = ctx["dataset"]["id"]
        ver2 = await client.post(
            f"/api/v1/quality/benchmark-datasets/{ds_id}/versions",
            headers=headers,
            json={},
        )
        assert ver2.status_code == 200, ver2.text
        draft_id = ver2.json()["id"]

        # Grievance supersede V1
        g = await client.post(
            "/api/v1/operations/grievances",
            headers=headers,
            json={
                "published_result_id": v1_prid,
                "requester_reference": "b15-hist",
                "reason": "Recheck for B15 interaction",
            },
        )
        assert g.status_code == 200, g.text
        accepted = await client.post(
            f"/api/v1/operations/grievances/{g.json()['id']}/accept",
            headers=headers,
            json={"decision_reason": "ok"},
        )
        assert accepted.status_code == 200, accepted.text
        fin = await _review_all_and_finalize(client, headers, sid)
        assert fin["workflow_state"] == "APPROVED"
        v2_prid = await _publish(client, headers, sid)

        async with async_session_factory() as db:
            v1 = await db.get(PublishedResult, uuid.UUID(v1_prid))
            assert v1 is not None
            assert v1.status == "SUPERSEDED"

        # Locked regression against historical V1 gold still runs
        run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(
                MODEL_PASS, idempotency_key=f"b161-{uuid.uuid4().hex[:8]}"
            ),
        )
        assert run.status_code == 200, run.text
        assert run.json()["status"] in {
            "COMPLETED",
            "PASSED",
            "FAILED",
            "GATE_FAILED",
        }
        # Case still references original published_result
        assert ctx["case"]["published_result_id"] == v1_prid

        # New eligible sources exclude SUPERSEDED V1 and include PUBLISHED V2
        eligible = await client.get(
            f"/api/v1/quality/benchmark-versions/{draft_id}/eligible-sources",
            headers=headers,
        )
        assert eligible.status_code == 200, eligible.text
        elig_ids = {i["published_result_id"] for i in eligible.json()["items"]}
        assert v1_prid not in elig_ids
        assert v2_prid in elig_ids
