"""B17 PEV-049 evaluator calibration acceptance coverage."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.authorization import ROLE_PERMISSION_MAP, AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import (
    QuestionEvaluation,
    ReviewAction,
)
from app.db.session import async_session_factory
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
from tests.test_b15_gold_benchmark_regression import _eligible_qe
from tests.test_b16_enterprise_ops import _auth_context, _create_role_user
from tests.test_b17_psychometrics import _clone_published_cohort


def _detail_code(resp) -> str | None:
    body = resp.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code")
    err = body.get("error")
    if isinstance(err, dict):
        return err.get("code")
    return None


async def _all_eligible_qes(published_result_id: str) -> list[dict]:
    async with async_session_factory() as db:
        from app.db.models import PublishedResult

        pr = await db.scalar(
            select(PublishedResult).where(
                PublishedResult.id == uuid.UUID(published_result_id)
            )
        )
        assert pr is not None
        qes = list(
            (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.evaluation_run_id == pr.evaluation_run_id,
                        QuestionEvaluation.workflow_state.in_(
                            ["ACCEPTED", "OVERRIDDEN"]
                        ),
                        QuestionEvaluation.final_human_approved_score.is_not(None),
                    )
                )
            ).all()
        )
        assert len(qes) >= 2
        return [
            {
                "published_result_id": str(pr.id),
                "question_evaluation_id": str(qe.id),
                "reference_score": float(qe.final_human_approved_score),
                "max_mark": float(qe.max_mark),
            }
            for qe in qes
        ]


@pytest.mark.asyncio
async def test_b17_calibration_lifecycle_blind_icc_immutable() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _auth_context(headers)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        cases_src = await _all_eligible_qes(prid)

        eval_a_id, eval_a = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="EVALUATOR", email_prefix="cal-a"
        )
        eval_b_id, eval_b = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="EVALUATOR", email_prefix="cal-b"
        )

        session = await client.post(
            "/api/v1/quality/calibration/sessions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "title": "B17 Calibration",
                "min_cases": 2,
            },
        )
        assert session.status_code == 200, session.text
        session_id = session.json()["id"]
        assert session.json()["status"] == "DRAFT"
        assert session.json()["min_cases"] == 2

        for src in cases_src[:2]:
            added = await client.post(
                f"/api/v1/quality/calibration/sessions/{session_id}/cases",
                headers=headers,
                json={
                    "published_result_id": src["published_result_id"],
                    "question_evaluation_id": src["question_evaluation_id"],
                },
            )
            assert added.status_code == 200, added.text
            assert "reference_score" in added.json()

        for uid in (eval_a_id, eval_b_id):
            part = await client.post(
                f"/api/v1/quality/calibration/sessions/{session_id}/participants",
                headers=headers,
                json={"user_id": str(uid)},
            )
            assert part.status_code == 200, part.text

        # Activate gates: insufficient cases when min_cases raised.
        bad_activate = await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/activate",
            headers=headers,
        )
        # min_cases=2 and we added 2 → should succeed
        assert bad_activate.status_code == 200, bad_activate.text
        assert bad_activate.json()["status"] == "ACTIVE"

        # Cannot add cases after activate.
        more = await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/cases",
            headers=headers,
            json={
                "published_result_id": cases_src[0]["published_result_id"],
                "question_evaluation_id": cases_src[0]["question_evaluation_id"],
            },
        )
        assert more.status_code == 409
        assert _detail_code(more) == "CALIBRATION_SESSION_NOT_DRAFT"

        detail = await client.get(
            f"/api/v1/quality/calibration/sessions/{session_id}",
            headers=headers,
        )
        assert detail.status_code == 200
        case_ids = [c["id"] for c in detail.json()["cases"]]
        assert len(case_ids) == 2

        my = await client.get(
            "/api/v1/quality/calibration/my-sessions", headers=eval_a
        )
        assert my.status_code == 200
        assert any(s["id"] == session_id for s in my.json()["items"])

        blind = await client.get(
            f"/api/v1/quality/calibration/sessions/{session_id}/cases/{case_ids[0]}/blind",
            headers=eval_a,
        )
        assert blind.status_code == 200, blind.text
        blind_body = blind.json()
        assert "reference_score" not in blind_body
        assert "published_result_id" not in blind_body
        assert "student_id" not in (blind_body.get("evidence_snapshot") or {})

        # Submit identical scores for both raters on both cases → ICC=1.
        for case_id, src in zip(case_ids, cases_src[:2], strict=True):
            for h in (eval_a, eval_b):
                resp = await client.post(
                    f"/api/v1/quality/calibration/sessions/{session_id}/cases/{case_id}/responses",
                    headers=h,
                    json={"score": src["reference_score"]},
                )
                assert resp.status_code == 200, resp.text

        # Immutable response.
        again = await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/cases/{case_ids[0]}/responses",
            headers=eval_a,
            json={"score": 0},
        )
        assert again.status_code == 409
        assert _detail_code(again) == "CALIBRATION_RESPONSE_IMMUTABLE"

        closed = await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/close",
            headers=headers,
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()["status"] == "CLOSED"

        metrics = await client.get(
            f"/api/v1/quality/calibration/sessions/{session_id}/metrics",
            headers=headers,
        )
        assert metrics.status_code == 200, metrics.text
        icc_rows = metrics.json()["items"]
        assert len(icc_rows) == 1
        assert icc_rows[0]["metric_name"] == "ICC_A1"
        # Reliability floor is always MIN_CALIBRATION_CASES=10; 2 cases → insufficient.
        assert icc_rows[0]["status"] == "INSUFFICIENT_SAMPLE"
        assert icc_rows[0]["common_case_count"] == 2
        assert icc_rows[0]["icc_value"] is None

        eval_metrics = await client.get(
            f"/api/v1/quality/calibration/sessions/{session_id}/evaluator-metrics",
            headers=headers,
        )
        assert eval_metrics.status_code == 200, eval_metrics.text
        rows = eval_metrics.json()["items"]
        assert len(rows) == 2
        for row in rows:
            assert row["mae"] == 0.0
            assert row["exact_match_rate"] == 1.0

        mine = await client.get(
            f"/api/v1/quality/calibration/sessions/{session_id}/my-metrics",
            headers=eval_a,
        )
        assert mine.status_code == 200, mine.text
        assert mine.json()["user_id"] == str(eval_a_id)
        assert mine.json()["mae"] == 0.0


@pytest.mark.asyncio
async def test_b17_calibration_icc_completed_with_ten_cases() -> None:
    """Build 10 common cases → ICC completes with near-perfect agreement."""
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _auth_context(headers)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        cases_src = await _all_eligible_qes(prid)
        assert len(cases_src) >= 1

        # Clone enough published QEs for 10 calibration cases.
        await _clone_published_cohort(
            template_pr_id=uuid.UUID(prid), extra_count=9, score_overrides=None
        )

        # Collect 10 eligible sources across all published results for this version.
        async with async_session_factory() as db:
            from app.db.models import PublishedResult

            prs = list(
                (
                    await db.scalars(
                        select(PublishedResult).where(
                            PublishedResult.tenant_id == ctx.tenant_id,
                            PublishedResult.assessment_version_id
                            == uuid.UUID(data["version_id"]),
                            PublishedResult.status == "PUBLISHED",
                        )
                    )
                ).all()
            )
            sources: list[dict] = []
            for pr in prs:
                qes = list(
                    (
                        await db.scalars(
                            select(QuestionEvaluation).where(
                                QuestionEvaluation.evaluation_run_id
                                == pr.evaluation_run_id,
                                QuestionEvaluation.workflow_state.in_(
                                    ["ACCEPTED", "OVERRIDDEN"]
                                ),
                                QuestionEvaluation.final_human_approved_score.is_not(
                                    None
                                ),
                            )
                        )
                    ).all()
                )
                for qe in qes:
                    sources.append(
                        {
                            "published_result_id": str(pr.id),
                            "question_evaluation_id": str(qe.id),
                            "reference_score": float(qe.final_human_approved_score),
                        }
                    )
                    if len(sources) >= 10:
                        break
                if len(sources) >= 10:
                    break
        assert len(sources) >= 10
        sources = sources[:10]

        eval_a_id, eval_a = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="EVALUATOR", email_prefix="cal10-a"
        )
        eval_b_id, eval_b = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="EVALUATOR", email_prefix="cal10-b"
        )

        session = await client.post(
            "/api/v1/quality/calibration/sessions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "title": "B17 Calibration 10",
                "min_cases": 10,
            },
        )
        assert session.status_code == 200, session.text
        session_id = session.json()["id"]

        for src in sources:
            added = await client.post(
                f"/api/v1/quality/calibration/sessions/{session_id}/cases",
                headers=headers,
                json={
                    "published_result_id": src["published_result_id"],
                    "question_evaluation_id": src["question_evaluation_id"],
                },
            )
            assert added.status_code == 200, added.text

        for uid in (eval_a_id, eval_b_id):
            part = await client.post(
                f"/api/v1/quality/calibration/sessions/{session_id}/participants",
                headers=headers,
                json={"user_id": str(uid)},
            )
            assert part.status_code == 200, part.text

        act = await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/activate",
            headers=headers,
        )
        assert act.status_code == 200, act.text

        detail = await client.get(
            f"/api/v1/quality/calibration/sessions/{session_id}",
            headers=headers,
        )
        case_ids = [c["id"] for c in detail.json()["cases"]]
        assert len(case_ids) == 10

        for case_id, src in zip(case_ids, sources, strict=True):
            for h in (eval_a, eval_b):
                resp = await client.post(
                    f"/api/v1/quality/calibration/sessions/{session_id}/cases/{case_id}/responses",
                    headers=h,
                    json={"score": src["reference_score"]},
                )
                assert resp.status_code == 200, resp.text

        closed = await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/close",
            headers=headers,
        )
        assert closed.status_code == 200, closed.text

        metrics = await client.get(
            f"/api/v1/quality/calibration/sessions/{session_id}/metrics",
            headers=headers,
        )
        assert metrics.status_code == 200, metrics.text
        icc_rows = metrics.json()["items"]
        assert icc_rows[0]["status"] == "COMPLETED"
        assert icc_rows[0]["common_case_count"] == 10
        assert abs(float(icc_rows[0]["icc_value"]) - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_b17_calibration_activate_gates_and_non_mutation() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _auth_context(headers)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        gold = await _eligible_qe(client, headers, prid)
        cases_src = await _all_eligible_qes(prid)

        eval_a_id, _ = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="EVALUATOR", email_prefix="gate-a"
        )
        eval_b_id, _ = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="EVALUATOR", email_prefix="gate-b"
        )

        session = await client.post(
            "/api/v1/quality/calibration/sessions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "title": "Gates",
                "min_cases": 2,
            },
        )
        session_id = session.json()["id"]

        # One case only → insufficient.
        await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/cases",
            headers=headers,
            json={
                "published_result_id": gold["published_result_id"],
                "question_evaluation_id": gold["question_evaluation_id"],
            },
        )
        await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/participants",
            headers=headers,
            json={"user_id": str(eval_a_id)},
        )
        await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/participants",
            headers=headers,
            json={"user_id": str(eval_b_id)},
        )
        insuf = await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/activate",
            headers=headers,
        )
        assert insuf.status_code == 409
        assert _detail_code(insuf) == "CALIBRATION_INSUFFICIENT_CASES"

        # Add second case; remove one participant path by creating new session.
        session2 = await client.post(
            "/api/v1/quality/calibration/sessions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "title": "One participant",
                "min_cases": 2,
            },
        )
        sid2 = session2.json()["id"]
        for src in cases_src[:2]:
            await client.post(
                f"/api/v1/quality/calibration/sessions/{sid2}/cases",
                headers=headers,
                json={
                    "published_result_id": src["published_result_id"],
                    "question_evaluation_id": src["question_evaluation_id"],
                },
            )
        await client.post(
            f"/api/v1/quality/calibration/sessions/{sid2}/participants",
            headers=headers,
            json={"user_id": str(eval_a_id)},
        )
        one_part = await client.post(
            f"/api/v1/quality/calibration/sessions/{sid2}/activate",
            headers=headers,
        )
        assert one_part.status_code == 409
        assert _detail_code(one_part) == "CALIBRATION_INSUFFICIENT_PARTICIPANTS"

        async with async_session_factory() as db:
            qe_before = await db.scalar(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.id == uuid.UUID(gold["question_evaluation_id"])
                )
            )
            assert qe_before is not None
            score_before = qe_before.final_human_approved_score
            review_count_before = await db.scalar(
                select(func.count()).select_from(ReviewAction)
            )

        # Creating/activating does not mutate ledger.
        session3 = await client.post(
            "/api/v1/quality/calibration/sessions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "title": "No mutate",
                "min_cases": 2,
            },
        )
        sid3 = session3.json()["id"]
        for src in cases_src[:2]:
            await client.post(
                f"/api/v1/quality/calibration/sessions/{sid3}/cases",
                headers=headers,
                json={
                    "published_result_id": src["published_result_id"],
                    "question_evaluation_id": src["question_evaluation_id"],
                },
            )
        for uid in (eval_a_id, eval_b_id):
            await client.post(
                f"/api/v1/quality/calibration/sessions/{sid3}/participants",
                headers=headers,
                json={"user_id": str(uid)},
            )
        await client.post(
            f"/api/v1/quality/calibration/sessions/{sid3}/activate",
            headers=headers,
        )

        async with async_session_factory() as db:
            qe_after = await db.scalar(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.id == uuid.UUID(gold["question_evaluation_id"])
                )
            )
            assert qe_after is not None
            assert qe_after.final_human_approved_score == score_before
            review_count_after = await db.scalar(
                select(func.count()).select_from(ReviewAction)
            )
            assert review_count_after == review_count_before


@pytest.mark.asyncio
async def test_b17_calibration_tenant_isolation_and_permissions() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _auth_context(headers)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        gold = await _eligible_qe(client, headers, prid)

        session = await client.post(
            "/api/v1/quality/calibration/sessions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "title": "RBAC",
                "min_cases": 1,
            },
        )
        session_id = session.json()["id"]
        await client.post(
            f"/api/v1/quality/calibration/sessions/{session_id}/cases",
            headers=headers,
            json={
                "published_result_id": gold["published_result_id"],
                "question_evaluation_id": gold["question_evaluation_id"],
            },
        )

        foreign = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset({"quality:read", "quality:manage"}),
            )
        )[0]
        foreign_headers = {"Authorization": f"Bearer {foreign}"}
        assert (
            await client.get(
                f"/api/v1/quality/calibration/sessions/{session_id}",
                headers=foreign_headers,
            )
        ).status_code == 404

        # Student cannot manage; evaluator without participate cannot hit my-sessions
        # (EVALUATOR has calibration:participate in ROLE_PERMISSION_MAP).
        student_token = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=ctx.user_id,
                tenant_id=ctx.tenant_id,
                roles=frozenset({"STUDENT"}),
                permissions=frozenset(),
            )
        )[0]
        student_headers = {"Authorization": f"Bearer {student_token}"}
        assert (
            await client.get(
                "/api/v1/quality/calibration/sessions", headers=student_headers
            )
        ).status_code == 403
        assert (
            await client.get(
                "/api/v1/quality/calibration/my-sessions", headers=student_headers
            )
        ).status_code == 403

        # Explicitly assert EVALUATOR has participate.
        assert "calibration:participate" in ROLE_PERMISSION_MAP["EVALUATOR"]
