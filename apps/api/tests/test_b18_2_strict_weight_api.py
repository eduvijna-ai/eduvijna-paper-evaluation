"""B18.2 API/service regressions for strict weight policy."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.models.outcome_intelligence import QuestionOutcomeMapping
from app.db.session import async_session_factory
from app.services.outcome_intelligence import WEIGHT_POLICY_STRICT
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import _publish_approved, _ready_assessment_with_curriculum
from tests.test_b17_psychometrics import _clone_published_cohort
from tests.test_b18_answer_clustering import _detail_code


@pytest.mark.asyncio
async def test_b18_2_api_strict_weight_and_policy_not_client_selectable() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(
            client, headers, data, override_answered=Decimal("4.0")
        )
        prid = await _publish_approved(client, headers, sid)
        await _clone_published_cohort(template_pr_id=uuid.UUID(prid), extra_count=1)
        question_id = data["leaf_a"]["question_id"]
        av_id = data["version_id"]

        co = await client.post(
            "/api/v1/outcomes/definitions",
            headers=headers,
            json={
                "outcome_type": "CO",
                "code": f"CO-B182-{uuid.uuid4().hex[:8]}",
                "title": "B18.2 CO",
            },
        )
        assert co.status_code == 200, co.text
        co_id = co.json()["id"]

        ms = await client.post(
            "/api/v1/outcomes/mapping-sets",
            headers=headers,
            json={"assessment_version_id": av_id, "title": "B18.2 draft"},
        )
        assert ms.status_code == 200, ms.text
        ms_id = ms.json()["id"]

        # Client cannot select legacy policy via payload
        forbidden = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co_id,
                "weight": 0.5,
                "weight_policy_version": 1,
            },
        )
        assert forbidden.status_code == 422, forbidden.text

        for bad in (0, -1, 1.0001, 1.01, 1.5, 2):
            resp = await client.post(
                f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
                headers=headers,
                json={
                    "question_id": question_id,
                    "outcome_definition_id": co_id,
                    "weight": bad,
                },
            )
            assert resp.status_code in {400, 422}, bad
            if resp.status_code == 400:
                assert _detail_code(resp) == "INVALID_WEIGHT"

        ok = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co_id,
                "weight": 0.75,
            },
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert "weight_policy_version" not in body
        assert body["weight"] == 0.75

        async with async_session_factory() as db:
            row = await db.scalar(
                select(QuestionOutcomeMapping).where(
                    QuestionOutcomeMapping.id == uuid.UUID(body["id"])
                )
            )
            assert row is not None
            assert row.weight_policy_version == WEIGHT_POLICY_STRICT
            # Downgrade attempt blocked at DB
            with pytest.raises((IntegrityError, DBAPIError)):
                await db.execute(
                    text(
                        """
                        UPDATE question_outcome_mappings
                        SET weight_policy_version = 1, weight = 1.5
                        WHERE id = :id
                        """
                    ),
                    {"id": row.id},
                )
                await db.commit()
            await db.rollback()
