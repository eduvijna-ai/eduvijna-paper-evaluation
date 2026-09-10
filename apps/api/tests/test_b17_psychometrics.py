"""B17 PEV-048 psychometric run acceptance coverage."""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import (
    EvaluationRun,
    PublishedResult,
    QuestionEvaluation,
    ReviewAction,
    Submission,
)
from app.db.session import async_session_factory
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
from tests.test_b15_gold_benchmark_regression import _eligible_qe


async def _clone_published_cohort(
    *,
    template_pr_id: uuid.UUID,
    extra_count: int,
    score_overrides: list[dict[uuid.UUID, Decimal]] | None = None,
) -> list[uuid.UUID]:
    """Clone PUBLISHED result + human-final QEs for cohort size without full pipeline."""
    created: list[uuid.UUID] = []
    async with async_session_factory() as db:
        template = await db.scalar(
            select(PublishedResult).where(PublishedResult.id == template_pr_id)
        )
        assert template is not None
        template_sub = await db.scalar(
            select(Submission).where(Submission.id == template.submission_id)
        )
        assert template_sub is not None
        template_qes = list(
            (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.evaluation_run_id
                        == template.evaluation_run_id,
                        QuestionEvaluation.workflow_state.in_(
                            ["ACCEPTED", "OVERRIDDEN"]
                        ),
                        QuestionEvaluation.final_human_approved_score.is_not(None),
                    )
                )
            ).all()
        )
        assert template_qes

        for i in range(extra_count):
            digest = uuid.uuid4().hex
            sub = Submission(
                tenant_id=template_sub.tenant_id,
                assessment_id=template_sub.assessment_id,
                assessment_version_id=template_sub.assessment_version_id,
                student_id=template_sub.student_id,
                workflow_state="PUBLISHED",
                student_match_state=template_sub.student_match_state,
                identity_confidence=template_sub.identity_confidence,
                mapping_confidence=template_sub.mapping_confidence,
                transcription_state="READY",
                source_storage_key=f"clone/{digest}.pdf",
                source_content_sha256=digest,
                original_filename=f"clone-{digest}.pdf",
                mime_type="application/pdf",
                byte_size=100,
                storage_status="AVAILABLE",
                page_count=1,
                uploaded_by=template_sub.uploaded_by,
                uploaded_at=datetime.now(UTC),
            )
            db.add(sub)
            await db.flush()

            run = EvaluationRun(
                tenant_id=template.tenant_id,
                submission_id=sub.id,
                assessment_id=template.assessment_id,
                assessment_version_id=template.assessment_version_id,
                run_number=1,
                run_kind="INITIAL",
                status="COMPLETED",
                provider="fixed",
                model="clone",
            )
            db.add(run)
            await db.flush()

            overrides = (
                score_overrides[i]
                if score_overrides is not None and i < len(score_overrides)
                else {}
            )
            for qe in template_qes:
                score = overrides.get(
                    qe.question_version_id, qe.final_human_approved_score
                )
                clone_qe = QuestionEvaluation(
                    tenant_id=qe.tenant_id,
                    evaluation_run_id=run.id,
                    submission_id=sub.id,
                    student_id=sub.student_id,
                    assessment_id=qe.assessment_id,
                    assessment_version_id=qe.assessment_version_id,
                    question_id=qe.question_id,
                    question_version_id=qe.question_version_id,
                    rubric_version_id=qe.rubric_version_id,
                    answer_key_version_id=qe.answer_key_version_id,
                    mapping_id=qe.mapping_id,
                    answer_region_ids=copy.deepcopy(qe.answer_region_ids or []),
                    transcription_refs=copy.deepcopy(qe.transcription_refs or []),
                    evidence_metadata=copy.deepcopy(qe.evidence_metadata or {}),
                    max_mark=qe.max_mark,
                    proposed_ai_score=qe.proposed_ai_score,
                    final_human_approved_score=score,
                    error_codes=copy.deepcopy(qe.error_codes or []),
                    deduction_reasons=copy.deepcopy(qe.deduction_reasons or []),
                    criterion_snapshot=copy.deepcopy(qe.criterion_snapshot or []),
                    workflow_state=qe.workflow_state,
                    ledger_version=1,
                )
                db.add(clone_qe)

            total = sum(
                Decimal(
                    str(
                        overrides.get(qe.question_version_id, qe.final_human_approved_score)
                    )
                )
                for qe in template_qes
            )
            pr = PublishedResult(
                tenant_id=template.tenant_id,
                submission_id=sub.id,
                student_id=sub.student_id,
                assessment_id=template.assessment_id,
                assessment_version_id=template.assessment_version_id,
                evaluation_run_id=run.id,
                version_number=1,
                status="PUBLISHED",
                ledger_snapshot_hash=f"clone-{digest}",
                total_score=total,
                max_total_score=template.max_total_score,
                published_at=datetime.now(UTC),
            )
            db.add(pr)
            await db.flush()
            created.append(pr.id)

        await db.commit()
    return created


@pytest.mark.asyncio
async def test_b17_psychometrics_insufficient_sample() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)

        run = await client.post(
            "/api/v1/quality/psychometrics/runs",
            headers=headers,
            json={"assessment_version_id": data["version_id"]},
        )
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["status"] == "INSUFFICIENT_SAMPLE"
        assert body["source_result_count"] == 1
        assert body["algorithm_version"] == "B17_PSYCHOMETRICS_V1"
        assert body["min_cohort_size"] == 20

        items = await client.get(
            f"/api/v1/quality/psychometrics/runs/{body['id']}/items",
            headers=headers,
        )
        assert items.status_code == 200, items.text
        assert items.json()["items"] == []


@pytest.mark.asyncio
async def test_b17_psychometrics_completed_cohort_idempotent_and_bands() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        template_id = uuid.UUID(prid)

        # Build varied scores across 19 clones + 1 template = 20.
        async with async_session_factory() as db:
            qes = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.assessment_version_id
                            == uuid.UUID(data["version_id"]),
                            QuestionEvaluation.final_human_approved_score.is_not(None),
                        )
                    )
                ).all()
            )
            qv_ids = sorted({qe.question_version_id for qe in qes}, key=str)
            assert len(qv_ids) >= 2

        overrides: list[dict[uuid.UUID, Decimal]] = []
        for i in range(19):
            overrides.append(
                {
                    qv_ids[0]: Decimal(str(i % 6)),  # 0..5 of max 5
                    qv_ids[1]: Decimal(str((i * 2) % 6)),
                }
            )
        await _clone_published_cohort(
            template_pr_id=template_id, extra_count=19, score_overrides=overrides
        )

        run1 = await client.post(
            "/api/v1/quality/psychometrics/runs",
            headers=headers,
            json={"assessment_version_id": data["version_id"]},
        )
        assert run1.status_code == 200, run1.text
        body1 = run1.json()
        assert body1["status"] == "COMPLETED"
        assert body1["source_result_count"] == 20

        run2 = await client.post(
            "/api/v1/quality/psychometrics/runs",
            headers=headers,
            json={"assessment_version_id": data["version_id"]},
        )
        assert run2.status_code == 200, run2.text
        assert run2.json()["id"] == body1["id"]

        items = await client.get(
            f"/api/v1/quality/psychometrics/runs/{body1['id']}/items",
            headers=headers,
        )
        assert items.status_code == 200, items.text
        item_rows = items.json()["items"]
        assert len(item_rows) >= 2
        for row in item_rows:
            assert row["attempt_count"] == 20
            assert row["difficulty_band"] in {"HARD", "MODERATE", "EASY"}
            assert row["discrimination_method"] == "CORRECTED_ITEM_TOTAL_PEARSON_V1"
            if row["discrimination_status"] == "OK":
                assert row["discrimination_index"] is not None
                assert row["discrimination_band"] in {"LOW", "MODERATE", "HIGH"}

        latest = await client.get(
            "/api/v1/quality/psychometrics/latest",
            headers=headers,
            params={"assessment_version_id": data["version_id"]},
        )
        assert latest.status_code == 200, latest.text
        assert latest.json()["id"] == body1["id"]

        listed = await client.get(
            "/api/v1/quality/psychometrics/runs",
            headers=headers,
            params={"assessment_version_id": data["version_id"]},
        )
        assert listed.status_code == 200
        assert any(r["id"] == body1["id"] for r in listed.json()["items"])


@pytest.mark.asyncio
async def test_b17_psychometrics_excludes_superseded_and_unpublished() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        await _clone_published_cohort(
            template_pr_id=uuid.UUID(prid), extra_count=19
        )

        # Mark one clone SUPERSEDED — must not count as an additional attempt.
        async with async_session_factory() as db:
            clones = list(
                (
                    await db.scalars(
                        select(PublishedResult).where(
                            PublishedResult.assessment_version_id
                            == uuid.UUID(data["version_id"]),
                            PublishedResult.status == "PUBLISHED",
                            PublishedResult.id != uuid.UUID(prid),
                        )
                    )
                ).all()
            )
            assert clones
            clones[0].status = "SUPERSEDED"
            await db.commit()

        run = await client.post(
            "/api/v1/quality/psychometrics/runs",
            headers=headers,
            json={"assessment_version_id": data["version_id"]},
        )
        assert run.status_code == 200, run.text
        assert run.json()["source_result_count"] == 19
        assert run.json()["status"] == "INSUFFICIENT_SAMPLE"

        # Unpublished APPROVED only (separate assessment path) excluded.
        data2 = await _ready_assessment_with_curriculum(client, headers)
        await _to_approved(client, headers, data2)
        run_unpub = await client.post(
            "/api/v1/quality/psychometrics/runs",
            headers=headers,
            json={"assessment_version_id": data2["version_id"]},
        )
        assert run_unpub.status_code == 200, run_unpub.text
        assert run_unpub.json()["source_result_count"] == 0
        assert run_unpub.json()["status"] == "INSUFFICIENT_SAMPLE"


@pytest.mark.asyncio
async def test_b17_psychometrics_does_not_mutate_ledger() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        gold = await _eligible_qe(client, headers, prid)

        async with async_session_factory() as db:
            qe_before = await db.scalar(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.id == uuid.UUID(gold["question_evaluation_id"])
                )
            )
            assert qe_before is not None
            score_before = qe_before.final_human_approved_score
            state_before = qe_before.workflow_state
            review_count_before = await db.scalar(select(func.count()).select_from(ReviewAction))

        await client.post(
            "/api/v1/quality/psychometrics/runs",
            headers=headers,
            json={"assessment_version_id": data["version_id"]},
        )

        async with async_session_factory() as db:
            qe_after = await db.scalar(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.id == uuid.UUID(gold["question_evaluation_id"])
                )
            )
            assert qe_after is not None
            assert qe_after.final_human_approved_score == score_before
            assert qe_after.workflow_state == state_before
            review_count_after = await db.scalar(select(func.count()).select_from(ReviewAction))
            assert review_count_after == review_count_before


@pytest.mark.asyncio
async def test_b17_psychometrics_tenant_isolation_and_rbac() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        run = await client.post(
            "/api/v1/quality/psychometrics/runs",
            headers=headers,
            json={"assessment_version_id": data["version_id"]},
        )
        assert run.status_code == 200, run.text
        run_id = run.json()["id"]

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
                f"/api/v1/quality/psychometrics/runs/{run_id}",
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
            await client.get(
                "/api/v1/quality/psychometrics/runs", headers=denied_headers
            )
        ).status_code == 403
