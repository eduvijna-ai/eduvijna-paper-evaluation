"""B18 PEV-050 answer clustering acceptance coverage."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.authorization import ROLE_PERMISSION_MAP, AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import (
    PublishedResult,
    QuestionEvaluation,
    ReviewAction,
    RubricVersion,
)
from app.db.session import async_session_factory
from app.services.cluster_math import connected_components, cosine_similarity, l2_normalize
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
from tests.test_b17_psychometrics import _clone_published_cohort

PATTERN_A = "alpha pattern chlorophyll photosynthesis light energy chemical"
PATTERN_B = "beta pattern mitochondria respiration glucose glycolysis energy"


def _detail_code(resp) -> str | None:
    body = resp.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code")
    err = body.get("error")
    if isinstance(err, dict):
        return err.get("code")
    return None


async def _set_transcription_patterns(
    *,
    assessment_version_id: uuid.UUID,
    question_id: uuid.UUID,
) -> None:
    async with async_session_factory() as db:
        qes = list(
            (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.assessment_version_id
                        == assessment_version_id,
                        QuestionEvaluation.question_id == question_id,
                        QuestionEvaluation.workflow_state.in_(
                            ["ACCEPTED", "OVERRIDDEN"]
                        ),
                    )
                )
            ).all()
        )
        for i, qe in enumerate(sorted(qes, key=lambda x: str(x.id))):
            text = PATTERN_A if i % 2 == 0 else PATTERN_B
            qe.transcription_refs = [{"text": text}]
            qe.evidence_metadata = {
                **(qe.evidence_metadata or {}),
                "transcription_text": text,
            }
        await db.commit()


def test_cluster_math_deterministic_and_order_independent() -> None:
    ids = ["c", "a", "b"]
    emb = [
        l2_normalize([1.0, 0.0, 0.0]),
        l2_normalize([1.0, 0.01, 0.0]),
        l2_normalize([0.0, 1.0, 0.0]),
    ]
    c1 = connected_components(ids, emb, threshold=0.9)
    c2 = connected_components(
        list(reversed(ids)), list(reversed(emb)), threshold=0.9
    )
    assert c1 == c2
    assert c1[0] == ["a", "c"]
    assert cosine_similarity(emb[0], emb[1]) >= 0.9


@pytest.mark.asyncio
async def test_b18_clustering_lifecycle_idempotent_review_non_mutation() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        question_id = uuid.UUID(data["leaf_a"]["question_id"])
        av_id = uuid.UUID(data["version_id"])

        await _clone_published_cohort(
            template_pr_id=uuid.UUID(prid), extra_count=5
        )
        await _set_transcription_patterns(
            assessment_version_id=av_id, question_id=question_id
        )

        create1 = await client.post(
            "/api/v1/quality/answer-clusters/runs",
            headers=headers,
            json={
                "assessment_version_id": str(av_id),
                "question_id": str(question_id),
                "similarity_threshold": 0.75,
            },
        )
        assert create1.status_code == 200, create1.text
        run = create1.json()
        assert run["algorithm_version"] == "COSINE_GRAPH_V1"
        assert run["status"] == "COMPLETED"
        assert run["cluster_count"] >= 2
        assert float(run["similarity_threshold"]) == 0.75
        assert run["embedding_provider"] == "fixed"
        run_id = run["id"]

        create2 = await client.post(
            "/api/v1/quality/answer-clusters/runs",
            headers=headers,
            json={
                "assessment_version_id": str(av_id),
                "question_id": str(question_id),
                "similarity_threshold": 0.75,
            },
        )
        assert create2.status_code == 200
        assert create2.json()["id"] == run_id

        clusters = await client.get(
            f"/api/v1/quality/answer-clusters/runs/{run_id}/clusters",
            headers=headers,
        )
        assert clusters.status_code == 200
        items = clusters.json()["items"]
        assert len(items) >= 2

        detail = await client.get(
            f"/api/v1/quality/answer-clusters/clusters/{items[0]['id']}",
            headers=headers,
        )
        assert detail.status_code == 200
        assert len(detail.json()["members"]) >= 1

        async with async_session_factory() as db:
            qe_count_before = await db.scalar(
                select(func.count()).select_from(QuestionEvaluation)
            )
            review_count_before = await db.scalar(
                select(func.count()).select_from(ReviewAction)
            )
            rubric_count_before = await db.scalar(
                select(func.count()).select_from(RubricVersion)
            )
            member_qe_ids = [
                uuid.UUID(m["question_evaluation_id"])
                for m in detail.json()["members"]
            ]
            qe_scores_before = {
                str(row.id): str(row.final_human_approved_score)
                for row in (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.id.in_(member_qe_ids)
                        )
                    )
                ).all()
            }

        review = await client.post(
            f"/api/v1/quality/answer-clusters/clusters/{items[0]['id']}/reviews",
            headers=headers,
            json={
                "observation": "Students confuse photosynthesis with respiration",
                "suggested_rubric_refinement": "Add explicit method credit note",
            },
        )
        assert review.status_code == 200, review.text
        assert "observation" in review.json()

        async with async_session_factory() as db:
            qe_count_after = await db.scalar(
                select(func.count()).select_from(QuestionEvaluation)
            )
            review_count_after = await db.scalar(
                select(func.count()).select_from(ReviewAction)
            )
            rubric_count_after = await db.scalar(
                select(func.count()).select_from(RubricVersion)
            )
            qe_scores_after = {
                str(row.id): str(row.final_human_approved_score)
                for row in (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.id.in_(member_qe_ids)
                        )
                    )
                ).all()
            }
        assert qe_count_before == qe_count_after
        assert review_count_before == review_count_after
        assert rubric_count_before == rubric_count_after
        assert qe_scores_before == qe_scores_after


@pytest.mark.asyncio
async def test_b18_clustering_excludes_superseded() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        question_id = uuid.UUID(data["leaf_a"]["question_id"])
        av_id = uuid.UUID(data["version_id"])

        clones = await _clone_published_cohort(
            template_pr_id=uuid.UUID(prid), extra_count=3
        )
        await _set_transcription_patterns(
            assessment_version_id=av_id, question_id=question_id
        )

        async with async_session_factory() as db:
            row = await db.scalar(
                select(PublishedResult).where(PublishedResult.id == clones[0])
            )
            assert row is not None
            row.status = "SUPERSEDED"
            await db.commit()

        resp = await client.post(
            "/api/v1/quality/answer-clusters/runs",
            headers=headers,
            json={
                "assessment_version_id": str(av_id),
                "question_id": str(question_id),
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["source_result_count"] == 3  # template + 2 remaining clones
        assert str(clones[0]) not in body["source_published_result_ids"]


@pytest.mark.asyncio
async def test_b18_clustering_rbac_and_tenant_isolation() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        question_id = data["leaf_a"]["question_id"]
        av_id = data["version_id"]

        await _clone_published_cohort(template_pr_id=uuid.UUID(prid), extra_count=2)
        await _set_transcription_patterns(
            assessment_version_id=uuid.UUID(av_id),
            question_id=uuid.UUID(question_id),
        )

        create = await client.post(
            "/api/v1/quality/answer-clusters/runs",
            headers=headers,
            json={
                "assessment_version_id": av_id,
                "question_id": question_id,
            },
        )
        assert create.status_code == 200, create.text
        run_id = create.json()["id"]

        foreign = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset(
                    {"clustering:read", "clustering:manage", "clustering:review"}
                ),
            )
        )[0]
        foreign_headers = {"Authorization": f"Bearer {foreign}"}
        assert (
            await client.get(
                f"/api/v1/quality/answer-clusters/runs/{run_id}",
                headers=foreign_headers,
            )
        ).status_code == 404

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
        denied_headers = {"Authorization": f"Bearer {denied}"}
        assert (
            await client.post(
                "/api/v1/quality/answer-clusters/runs",
                headers=denied_headers,
                json={
                    "assessment_version_id": av_id,
                    "question_id": question_id,
                },
            )
        ).status_code == 403

        assert "clustering:manage" in ROLE_PERMISSION_MAP["TEACHER"]
        assert "clustering:review" in ROLE_PERMISSION_MAP["EVALUATOR"]
        assert "clustering:read" in ROLE_PERMISSION_MAP["AUDITOR"]
        assert "clustering:read" not in ROLE_PERMISSION_MAP["STUDENT"]
