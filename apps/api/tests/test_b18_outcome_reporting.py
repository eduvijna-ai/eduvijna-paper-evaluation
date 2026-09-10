"""B18 PEV-051 CO/PO outcome reporting acceptance coverage."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.authorization import ROLE_PERMISSION_MAP, AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import PublishedResult, QuestionEvaluation
from app.db.session import async_session_factory
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
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


@pytest.mark.asyncio
async def test_b18_outcome_reporting_lifecycle_exact_math_csv_immutability() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(
            client, headers, data, override_answered=Decimal("4.0")
        )
        prid = await _publish_approved(client, headers, sid)
        question_id = data["leaf_a"]["question_id"]
        question_version_id = uuid.UUID(data["leaf_a"]["id"])
        av_id = data["version_id"]

        # Normalize all QEs for leaf_a to known scores/max for exact math.
        async with async_session_factory() as db:
            rows = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.assessment_version_id
                            == uuid.UUID(av_id),
                            QuestionEvaluation.question_id == uuid.UUID(question_id),
                        )
                    )
                ).all()
            )
            for row in rows:
                row.max_mark = Decimal("5.00")
                row.final_human_approved_score = Decimal("4.00")
            await db.commit()

        await _clone_published_cohort(
            template_pr_id=uuid.UUID(prid),
            extra_count=3,
            score_overrides=[
                {question_version_id: Decimal("2.00")},
                {question_version_id: Decimal("2.00")},
                {question_version_id: Decimal("2.00")},
            ],
        )

        async with async_session_factory() as db:
            rows = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.assessment_version_id
                            == uuid.UUID(av_id),
                            QuestionEvaluation.question_id == uuid.UUID(question_id),
                            QuestionEvaluation.workflow_state.in_(
                                ["ACCEPTED", "OVERRIDDEN"]
                            ),
                        )
                    )
                ).all()
            )
            for row in rows:
                row.max_mark = Decimal("5.00")
            await db.commit()

        co = await client.post(
            "/api/v1/outcomes/definitions",
            headers=headers,
            json={
                "outcome_type": "CO",
                "code": f"CO-B18-{uuid.uuid4().hex[:8]}",
                "title": "Course Outcome B18",
                "description": "Understand energy conversion",
            },
        )
        assert co.status_code == 200, co.text
        co_id = co.json()["id"]

        po = await client.post(
            "/api/v1/outcomes/definitions",
            headers=headers,
            json={
                "outcome_type": "PO",
                "code": f"PO-B18-{uuid.uuid4().hex[:8]}",
                "title": "Program Outcome B18",
            },
        )
        assert po.status_code == 200
        po_id = po.json()["id"]

        mapping_set = await client.post(
            "/api/v1/outcomes/mapping-sets",
            headers=headers,
            json={"assessment_version_id": av_id, "title": "B18 mapping v1"},
        )
        assert mapping_set.status_code == 200, mapping_set.text
        set_id = mapping_set.json()["id"]
        assert mapping_set.json()["status"] == "DRAFT"
        assert mapping_set.json()["version_number"] == 1

        map_co = await client.post(
            f"/api/v1/outcomes/mapping-sets/{set_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co_id,
                "weight": "1.0",
            },
        )
        assert map_co.status_code == 200, map_co.text

        map_po = await client.post(
            f"/api/v1/outcomes/mapping-sets/{set_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": po_id,
                "weight": "2.0",
            },
        )
        assert map_po.status_code == 200

        activate = await client.post(
            f"/api/v1/outcomes/mapping-sets/{set_id}/activate",
            headers=headers,
        )
        assert activate.status_code == 200
        assert activate.json()["status"] == "ACTIVE"

        blocked = await client.post(
            f"/api/v1/outcomes/mapping-sets/{set_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co_id,
                "weight": "1.0",
            },
        )
        assert blocked.status_code == 409
        assert _detail_code(blocked) == "MAPPING_SET_NOT_DRAFT"

        mapping_set_v2 = await client.post(
            "/api/v1/outcomes/mapping-sets",
            headers=headers,
            json={"assessment_version_id": av_id, "title": "B18 mapping v2"},
        )
        assert mapping_set_v2.status_code == 200
        assert mapping_set_v2.json()["version_number"] == 2
        assert mapping_set_v2.json()["status"] == "DRAFT"

        report = await client.post(
            "/api/v1/outcomes/attainment-reports",
            headers=headers,
            json={"assessment_version_id": av_id, "mapping_set_id": set_id},
        )
        assert report.status_code == 200, report.text
        body = report.json()
        assert body["status"] == "COMPLETED"
        assert body["algorithm_version"] == "MARKS_WEIGHTED_V1"
        assert body["source_result_count"] == 4
        metrics = {m["outcome_definition_id"]: m for m in body["metrics"]}

        # Template score 4 + three clones score 2 = earned 10; max 5*4=20; pct 50
        # PO weight 2 → earned 20, max 40, pct 50
        co_m = metrics[co_id]
        assert float(co_m["weighted_earned"]) == 10.0
        assert float(co_m["weighted_max"]) == 20.0
        assert float(co_m["attainment_pct"]) == 50.0
        assert co_m["denom_status"] == "OK"

        po_m = metrics[po_id]
        assert float(po_m["weighted_earned"]) == 20.0
        assert float(po_m["weighted_max"]) == 40.0
        assert float(po_m["attainment_pct"]) == 50.0

        report2 = await client.post(
            "/api/v1/outcomes/attainment-reports",
            headers=headers,
            json={"assessment_version_id": av_id, "mapping_set_id": set_id},
        )
        assert report2.status_code == 200
        assert report2.json()["id"] == body["id"]

        csv_resp = await client.get(
            f"/api/v1/outcomes/attainment-reports/{body['id']}/export.csv",
            headers=headers,
        )
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers.get("content-type", "")
        csv_text = csv_resp.text
        assert "outcome_code" in csv_text
        assert "weighted_earned" in csv_text
        assert co.json()["code"] in csv_text


@pytest.mark.asyncio
async def test_b18_outcome_zero_denom_and_superseded_exclusion() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        question_id = data["leaf_a"]["question_id"]
        av_id = data["version_id"]

        async with async_session_factory() as db:
            for qe_row in (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.assessment_version_id == uuid.UUID(av_id),
                        QuestionEvaluation.question_id == uuid.UUID(question_id),
                    )
                )
            ).all():
                qe_row.max_mark = Decimal("0.00")
                qe_row.final_human_approved_score = Decimal("0.00")
            await db.commit()

        clones = await _clone_published_cohort(
            template_pr_id=uuid.UUID(prid), extra_count=1
        )
        async with async_session_factory() as db:
            clone = await db.scalar(
                select(PublishedResult).where(PublishedResult.id == clones[0])
            )
            assert clone is not None
            clone.status = "SUPERSEDED"
            for qe_row in (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.assessment_version_id == uuid.UUID(av_id),
                        QuestionEvaluation.question_id == uuid.UUID(question_id),
                    )
                )
            ).all():
                qe_row.max_mark = Decimal("0.00")
                qe_row.final_human_approved_score = Decimal("0.00")
            await db.commit()

        co = await client.post(
            "/api/v1/outcomes/definitions",
            headers=headers,
            json={
                "outcome_type": "CO",
                "code": f"CO-ZD-{uuid.uuid4().hex[:8]}",
                "title": "Zero denom CO",
            },
        )
        assert co.status_code == 200
        set_resp = await client.post(
            "/api/v1/outcomes/mapping-sets",
            headers=headers,
            json={"assessment_version_id": av_id, "title": "ZD set"},
        )
        set_id = set_resp.json()["id"]
        await client.post(
            f"/api/v1/outcomes/mapping-sets/{set_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co.json()["id"],
                "weight": "1",
            },
        )
        await client.post(
            f"/api/v1/outcomes/mapping-sets/{set_id}/activate",
            headers=headers,
        )
        report = await client.post(
            "/api/v1/outcomes/attainment-reports",
            headers=headers,
            json={"assessment_version_id": av_id, "mapping_set_id": set_id},
        )
        assert report.status_code == 200, report.text
        assert report.json()["source_result_count"] == 1
        metric = report.json()["metrics"][0]
        assert metric["denom_status"] == "ZERO_DENOM"
        assert metric["attainment_pct"] is None
        assert float(metric["weighted_max"]) == 0.0


@pytest.mark.asyncio
async def test_b18_outcomes_rbac() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@demo.eduvijna.local",
                "password": "DemoAdmin!2026",
                "tenant_slug": "demo",
            },
        )
        context = JwtAuthProvider(get_settings()).verify_access_token(
            login.json()["access_token"]
        )
        denied = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"STUDENT"}),
                permissions=frozenset(),
            )
        )[0]
        resp = await client.get(
            "/api/v1/outcomes/definitions",
            headers={"Authorization": f"Bearer {denied}"},
        )
        assert resp.status_code == 403
        assert data["version_id"]

        assert "outcomes:manage" in ROLE_PERMISSION_MAP["TEACHER"]
        assert "outcomes:report" in ROLE_PERMISSION_MAP["HOD"]
        assert "outcomes:read" in ROLE_PERMISSION_MAP["EVALUATOR"]
        assert "outcomes:read" in ROLE_PERMISSION_MAP["AUDITOR"]
        assert "outcomes:read" not in ROLE_PERMISSION_MAP["PARENT"]
