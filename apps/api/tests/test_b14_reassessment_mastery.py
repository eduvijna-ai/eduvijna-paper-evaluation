"""B14 reassessment instantiation + mastery delta coverage (PEV-043)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import (
    AnswerKey,
    Assessment,
    AssessmentVersion,
    LearningRecommendation,
    MasteryEvidence,
    MasteryStateSnapshot,
    PublishedResult,
    Question,
    QuestionCurriculumMapping,
    QuestionVersion,
    Reassessment,
    ReassessmentItem,
    ReassessmentMasteryDelta,
    Rubric,
    Submission,
)
from app.db.session import async_session_factory
from app.services.readiness import ensure_assessment_ready
from app.services.reassessment import materialize_b14_for_published_result
from app.services.reassessment_mastery import compute_delta
from tests.test_b3_submission_ingestion import _headers, _pdf_bytes
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
from tests.test_b9_learning_blueprint import _force_concept_weak


def test_compute_delta_null_semantics() -> None:
    assert compute_delta(None, None) is None
    assert compute_delta(Decimal("0.5"), None) is None
    assert compute_delta(None, Decimal("0.5")) is None
    assert compute_delta(Decimal("0.40"), Decimal("0.70")) == Decimal("0.300000")
    assert compute_delta(Decimal("0.80"), Decimal("0.50")) == Decimal("-0.300000")
    assert compute_delta(Decimal("0"), Decimal("0")) == Decimal("0.000000")


async def _approve_blueprint_flow(
    client,
    headers: dict[str, str],
) -> dict:
    data = await _ready_assessment_with_curriculum(client, headers)
    sid, student_id = await _to_approved(client, headers, data)
    await _publish_approved(client, headers, sid)
    curriculum_id = data["curriculum"]["id"]
    node_id = data["node"]["id"]
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

    bp_prep = await client.post(
        f"/api/v1/learning/plan-runs/{run_id}/improvement-blueprints/prepare",
        headers=headers,
    )
    assert bp_prep.status_code == 200, bp_prep.text
    bp_id = bp_prep.json()["improvement_assessment_id"]

    approve = await client.post(
        f"/api/v1/improvement-assessments/{bp_id}/approve",
        headers=headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"

    bp = await client.get(
        f"/api/v1/improvement-assessments/{bp_id}", headers=headers
    )
    assert bp.status_code == 200, bp.text
    return {
        "data": data,
        "student_id": student_id,
        "curriculum_id": curriculum_id,
        "node_id": node_id,
        "run_id": run_id,
        "bp_id": bp_id,
        "bp": bp.json(),
        "source_assessment_id": data["assessment"]["id"],
    }


def _instantiate_payload(bp_body: dict, *, prompt_suffix: str = "") -> dict:
    return {
        "items": [
            {
                "improvement_assessment_item_id": item["id"],
                "prompt_text": f"Reassessment prompt {item['item_code']}{prompt_suffix}",
                "max_marks": "5.00",
                "question_type": "SHORT",
                "instructions": None,
            }
            for item in bp_body["items"]
        ]
    }


@pytest.mark.asyncio
async def test_b14_instantiate_success_and_idempotent() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _approve_blueprint_flow(client, headers)
        bp_id = ctx["bp_id"]
        bp_body = ctx["bp"]
        payload = _instantiate_payload(bp_body)

        async with async_session_factory() as db:
            tenant_id = (
                await db.scalar(
                    select(Assessment.tenant_id).where(
                        Assessment.id == uuid.UUID(ctx["source_assessment_id"])
                    )
                )
            )
            assert tenant_id is not None
            before_assessments = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Assessment)
                    .where(Assessment.tenant_id == tenant_id)
                )
                or 0
            )
            before_questions = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Question)
                    .where(Question.tenant_id == tenant_id)
                )
                or 0
            )
            before_ak = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AnswerKey)
                    .where(AnswerKey.tenant_id == tenant_id)
                )
                or 0
            )
            before_rubric = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Rubric)
                    .where(Rubric.tenant_id == tenant_id)
                )
                or 0
            )
            before_submissions = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Submission)
                    .where(Submission.tenant_id == tenant_id)
                )
                or 0
            )
            before_evidence = int(
                await db.scalar(
                    select(func.count())
                    .select_from(MasteryEvidence)
                    .where(MasteryEvidence.tenant_id == tenant_id)
                )
                or 0
            )
            before_recs = list(
                (
                    await db.scalars(
                        select(LearningRecommendation).where(
                            LearningRecommendation.tenant_id == tenant_id,
                            LearningRecommendation.student_id
                            == uuid.UUID(ctx["student_id"]),
                        )
                    )
                ).all()
            )
            before_rec_status = {str(r.id): r.status for r in before_recs}

        created = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json=payload,
        )
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["status"] == "CREATED"
        assert body["algorithm_version"] == "B14_V1"
        assert body["submission_id"] is None
        assert body["published_result_id"] is None
        assert body["assessment_status"] == "DRAFT"
        assert len(body["items"]) == len(bp_body["items"])
        assert body["mastery_deltas"]
        for delta in body["mastery_deltas"]:
            assert delta["algorithm_version"] == "B14_V1"
            assert delta["post_snapshot_id"] is None
            assert delta["concept_delta"] is None
            assert delta["execution_delta"] is None

        reused = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json=payload,
        )
        assert reused.status_code == 200, reused.text
        assert reused.json()["id"] == body["id"]
        assert reused.json()["instantiation_hash"] == body["instantiation_hash"]

        different = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json=_instantiate_payload(bp_body, prompt_suffix=" changed"),
        )
        assert different.status_code == 409, different.text
        assert (
            different.json()["error"]["code"] == "REASSESSMENT_ALREADY_INSTANTIATED"
        )

        detail = await client.get(
            f"/api/v1/reassessments/{body['id']}", headers=headers
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["id"] == body["id"]

        workspace = await client.get(
            f"/api/v1/learning/students/{ctx['student_id']}",
            headers=headers,
            params={"curriculum_id": ctx["curriculum_id"]},
        )
        assert workspace.status_code == 200, workspace.text
        ras = workspace.json().get("reassessments") or []
        assert any(r["id"] == body["id"] for r in ras)

        async with async_session_factory() as db:
            after_assessments = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Assessment)
                    .where(Assessment.tenant_id == tenant_id)
                )
                or 0
            )
            after_questions = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Question)
                    .where(Question.tenant_id == tenant_id)
                )
                or 0
            )
            after_ak = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AnswerKey)
                    .where(AnswerKey.tenant_id == tenant_id)
                )
                or 0
            )
            after_rubric = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Rubric)
                    .where(Rubric.tenant_id == tenant_id)
                )
                or 0
            )
            after_submissions = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Submission)
                    .where(Submission.tenant_id == tenant_id)
                )
                or 0
            )
            after_evidence = int(
                await db.scalar(
                    select(func.count())
                    .select_from(MasteryEvidence)
                    .where(MasteryEvidence.tenant_id == tenant_id)
                )
                or 0
            )
            after_published = int(
                await db.scalar(
                    select(func.count())
                    .select_from(PublishedResult)
                    .where(PublishedResult.tenant_id == tenant_id)
                )
                or 0
            )
            ra = await db.scalar(
                select(Reassessment).where(Reassessment.id == uuid.UUID(body["id"]))
            )
            assert ra is not None
            assert ra.assessment_id == uuid.UUID(body["assessment_id"])
            asm = await db.scalar(
                select(Assessment).where(Assessment.id == ra.assessment_id)
            )
            assert asm is not None
            assert asm.assessment_type == "IMPROVEMENT_REASSESSMENT"
            assert asm.status == "DRAFT"
            item_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(ReassessmentItem)
                    .where(ReassessmentItem.reassessment_id == ra.id)
                )
                or 0
            )
            assert item_count == len(bp_body["items"])
            maps = list(
                (
                    await db.scalars(
                        select(QuestionCurriculumMapping)
                        .join(
                            QuestionVersion,
                            QuestionVersion.id
                            == QuestionCurriculumMapping.question_version_id,
                        )
                        .join(
                            AssessmentVersion,
                            AssessmentVersion.id
                            == QuestionVersion.assessment_version_id,
                        )
                        .where(AssessmentVersion.assessment_id == ra.assessment_id)
                    )
                ).all()
            )
            assert maps
            assert all(m.mapping_type == "PRIMARY" for m in maps)
            after_recs = list(
                (
                    await db.scalars(
                        select(LearningRecommendation).where(
                            LearningRecommendation.tenant_id == tenant_id,
                            LearningRecommendation.student_id
                            == uuid.UUID(ctx["student_id"]),
                        )
                    )
                ).all()
            )
            after_rec_status = {str(r.id): r.status for r in after_recs}

        assert after_assessments == before_assessments + 1
        assert after_questions == before_questions + len(bp_body["items"])
        assert after_ak == before_ak
        assert after_rubric == before_rubric
        assert after_submissions == before_submissions
        assert after_evidence == before_evidence
        assert after_published >= 1
        assert after_rec_status == before_rec_status

        # Idempotent second call did not create another assessment row.
        async with async_session_factory() as db:
            ra_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(Reassessment)
                    .where(
                        Reassessment.tenant_id == tenant_id,
                        Reassessment.improvement_assessment_id == uuid.UUID(bp_id),
                    )
                )
                or 0
            )
        assert ra_count == 1


@pytest.mark.asyncio
async def test_b14_rejects_non_approved_and_stale_and_foreign() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]
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
        bp_prep = await client.post(
            f"/api/v1/learning/plan-runs/{run_id}/improvement-blueprints/prepare",
            headers=headers,
        )
        assert bp_prep.status_code == 200, bp_prep.text
        bp_id = bp_prep.json()["improvement_assessment_id"]
        bp = await client.get(
            f"/api/v1/improvement-assessments/{bp_id}", headers=headers
        )
        assert bp.status_code == 200, bp.text
        payload = _instantiate_payload(bp.json())

        # PENDING_APPROVAL rejected
        pending = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json=payload,
        )
        assert pending.status_code == 409, pending.text
        assert (
            pending.json()["error"]["code"] == "REASSESSMENT_BLUEPRINT_NOT_APPROVED"
        )

        approve = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/approve",
            headers=headers,
        )
        assert approve.status_code == 200, approve.text

        # Stale: mutate blueprint input_hash after approve
        async with async_session_factory() as db:
            from app.db.models import ImprovementAssessment

            bp_row = await db.scalar(
                select(ImprovementAssessment).where(
                    ImprovementAssessment.id == uuid.UUID(bp_id)
                )
            )
            assert bp_row is not None
            bp_row.input_hash = "0" * 64
            await db.commit()

        stale = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json=payload,
        )
        assert stale.status_code == 409, stale.text
        assert stale.json()["error"]["code"] == "REASSESSMENT_BLUEPRINT_STALE"

        foreign = await client.post(
            f"/api/v1/improvement-assessments/{uuid.uuid4()}/reassessment",
            headers=headers,
            json=payload,
        )
        assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_b14_item_validation_422() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _approve_blueprint_flow(client, headers)
        bp_id = ctx["bp_id"]
        items = ctx["bp"]["items"]
        assert items

        missing = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json={"items": []},
        )
        assert missing.status_code == 422

        unknown = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json={
                "items": [
                    {
                        "improvement_assessment_item_id": str(uuid.uuid4()),
                        "prompt_text": "x",
                        "max_marks": "5.00",
                    }
                ]
            },
        )
        assert unknown.status_code == 422, unknown.text

        first = items[0]
        duplicate_items = [
            {
                "improvement_assessment_item_id": item["id"],
                "prompt_text": f"prompt {item['item_code']}",
                "max_marks": "5.00",
            }
            for item in items
        ] + [
            {
                "improvement_assessment_item_id": first["id"],
                "prompt_text": "dup",
                "max_marks": "5.00",
            }
        ]
        dup = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json={"items": duplicate_items},
        )
        assert dup.status_code == 422, dup.text

        empty_prompt = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json={
                "items": [
                    {
                        "improvement_assessment_item_id": item["id"],
                        "prompt_text": " ",
                        "max_marks": "5.00",
                    }
                    for item in items
                ]
            },
        )
        assert empty_prompt.status_code == 422, empty_prompt.text

        zero_marks = await client.post(
            f"/api/v1/improvement-assessments/{bp_id}/reassessment",
            headers=headers,
            json={
                "items": [
                    {
                        "improvement_assessment_item_id": item["id"],
                        "prompt_text": f"ok {item['item_code']}",
                        "max_marks": "0.00",
                    }
                    for item in items
                ]
            },
        )
        assert zero_marks.status_code == 422, zero_marks.text


@pytest.mark.asyncio
async def test_b14_ensure_ready_requires_ak_rubric() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _approve_blueprint_flow(client, headers)
        created = await client.post(
            f"/api/v1/improvement-assessments/{ctx['bp_id']}/reassessment",
            headers=headers,
            json=_instantiate_payload(ctx["bp"]),
        )
        assert created.status_code == 200, created.text
        version_id = created.json()["assessment_version_id"]

        async with async_session_factory() as db:
            version = await db.scalar(
                select(AssessmentVersion).where(
                    AssessmentVersion.id == uuid.UUID(version_id)
                )
            )
            assert version is not None
            with pytest.raises(Exception) as exc:
                await ensure_assessment_ready(
                    db, tenant_id=version.tenant_id, assessment_version=version
                )
            text = str(exc.value).lower()
            assert "answer key" in text or "rubric" in text or "409" in text


@pytest.mark.asyncio
async def test_b14_identity_bind_and_mismatch() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _approve_blueprint_flow(client, headers)
        created = await client.post(
            f"/api/v1/improvement-assessments/{ctx['bp_id']}/reassessment",
            headers=headers,
            json=_instantiate_payload(ctx["bp"]),
        )
        assert created.status_code == 200, created.text
        ra = created.json()
        assessment_id = ra["assessment_id"]
        expected_student = ctx["student_id"]

        # Force ACTIVE so upload is allowed without AK/rubric (bind-only coverage).
        async with async_session_factory() as db:
            asm = await db.scalar(
                select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
            )
            assert asm is not None
            asm.status = "ACTIVE"
            await db.commit()

        other = await client.post(
            "/api/v1/students",
            headers=headers,
            json={
                "student_code": f"B14-{uuid.uuid4().hex[:6]}",
                "full_name": "Other Student",
                "academic_year_id": None,
                "class_section_id": None,
                "status": "active",
            },
        )
        assert other.status_code == 201, other.text
        other_id = other.json()["id"]

        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": assessment_id},
            files={"file": ("b14.pdf", _pdf_bytes(1), "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        submission_id = upload.json()["id"]

        wrong = await client.post(
            f"/api/v1/submissions/{submission_id}/identity/confirm",
            headers=headers,
            json={"student_id": other_id},
        )
        assert wrong.status_code == 409, wrong.text
        assert wrong.json()["error"]["code"] == "REASSESSMENT_STUDENT_MISMATCH"

        ok = await client.post(
            f"/api/v1/submissions/{submission_id}/identity/confirm",
            headers=headers,
            json={"student_id": expected_student},
        )
        assert ok.status_code == 200, ok.text

        detail = await client.get(
            f"/api/v1/reassessments/{ra['id']}", headers=headers
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "SUBMITTED"
        assert detail.json()["submission_id"] == submission_id

        upload2 = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": assessment_id},
            files={"file": ("b14b.pdf", _pdf_bytes(1), "application/pdf")},
        )
        assert upload2.status_code == 201, upload2.text
        second = await client.post(
            f"/api/v1/submissions/{upload2.json()['id']}/identity/confirm",
            headers=headers,
            json={"student_id": expected_student},
        )
        assert second.status_code == 409, second.text
        assert second.json()["error"]["code"] == "REASSESSMENT_ATTEMPT_BOUND"


@pytest.mark.asyncio
async def test_b14_materialize_rebuild_and_permissions() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _approve_blueprint_flow(client, headers)
        created = await client.post(
            f"/api/v1/improvement-assessments/{ctx['bp_id']}/reassessment",
            headers=headers,
            json=_instantiate_payload(ctx["bp"]),
        )
        assert created.status_code == 200, created.text
        ra_body = created.json()
        ra_id = ra_body["id"]

        from datetime import UTC, datetime

        from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD

        async with async_session_factory() as db:
            ra = await db.scalar(
                select(Reassessment).where(Reassessment.id == uuid.UUID(ra_id))
            )
            assert ra is not None
            tenant_id = ra.tenant_id
            baseline_before = {
                str(d.curriculum_node_id): (
                    d.baseline_source_evidence_hash,
                    d.baseline_concept_mastery,
                    d.baseline_execution_accuracy,
                )
                for d in (
                    await db.scalars(
                        select(ReassessmentMasteryDelta).where(
                            ReassessmentMasteryDelta.reassessment_id == ra.id
                        )
                    )
                ).all()
            }
            evidence_before = int(
                await db.scalar(
                    select(func.count())
                    .select_from(MasteryEvidence)
                    .where(MasteryEvidence.tenant_id == tenant_id)
                )
                or 0
            )

            existing_pr = await db.scalar(select(PublishedResult).limit(1))
            assert existing_pr is not None
            now = datetime.now(UTC)

            submission = Submission(
                tenant_id=tenant_id,
                assessment_id=ra.assessment_id,
                assessment_version_id=ra.assessment_version_id,
                student_id=ra.student_id,
                workflow_state="APPROVED",
                student_match_state="CONFIRMED",
                source_storage_key=f"synthetic/{uuid.uuid4().hex}",
                source_content_sha256=uuid.uuid4().hex + uuid.uuid4().hex[:32],
                original_filename="synthetic.pdf",
                mime_type="application/pdf",
                byte_size=10,
                storage_status="AVAILABLE",
                page_count=1,
                uploaded_by=ra.created_by or existing_pr.generated_by,
                uploaded_at=now,
            )
            # uploaded_by is required; fall back to any user from existing PR
            if submission.uploaded_by is None:
                submission.uploaded_by = existing_pr.published_by or existing_pr.generated_by
            assert submission.uploaded_by is not None
            db.add(submission)
            await db.flush()

            published = PublishedResult(
                tenant_id=tenant_id,
                submission_id=submission.id,
                student_id=ra.student_id,
                assessment_id=ra.assessment_id,
                assessment_version_id=ra.assessment_version_id,
                evaluation_run_id=existing_pr.evaluation_run_id,
                version_number=1,
                status="PUBLISHED",
                ledger_snapshot_hash="b" * 64,
                total_score=Decimal("5.0000"),
                max_total_score=Decimal("5.0000"),
                generated_by=submission.uploaded_by,
                generated_at=now,
                published_by=submission.uploaded_by,
                published_at=now,
            )
            db.add(published)
            await db.flush()

            for node_id_str in baseline_before:
                node_id = uuid.UUID(node_id_str)
                snap = MasteryStateSnapshot(
                    tenant_id=tenant_id,
                    student_id=ra.student_id,
                    curriculum_id=ra.curriculum_id,
                    curriculum_node_id=node_id,
                    published_result_id=published.id,
                    assessment_id=ra.assessment_id,
                    concept_mastery=Decimal("0.900000"),
                    execution_accuracy=Decimal("0.800000"),
                    concept_decisive_count=2,
                    execution_decisive_count=2,
                    concept_inconclusive_count=0,
                    execution_inconclusive_count=0,
                    evidence_count=4,
                    source_evidence_hash="c" * 64,
                    algorithm_version="B12_V1",
                    effective_at=now,
                )
                db.add(snap)

            ra.submission_id = submission.id
            ra.status = "SUBMITTED"
            await db.commit()
            published_id = published.id

        async with async_session_factory() as db:
            published = await db.scalar(
                select(PublishedResult).where(PublishedResult.id == published_id)
            )
            assert published is not None
            result = await materialize_b14_for_published_result(
                db, tenant_id=published.tenant_id, published=published
            )
            assert result is not None
            assert result["algorithm_version"] == "B14_V1"
            assert result["source"] == "MASTERY_STATE_SNAPSHOT"
            await db.commit()

        rebuilt = await client.post(
            f"/api/v1/reassessments/{ra_id}/b14/rebuild",
            headers=headers,
        )
        assert rebuilt.status_code == 200, rebuilt.text
        assert rebuilt.json()["reassessment_id"] == ra_id
        assert rebuilt.json()["delta_count"] >= 1

        detail = await client.get(f"/api/v1/reassessments/{ra_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "PUBLISHED"
        assert detail.json()["published_result_id"] == str(published_id)
        for delta in detail.json()["mastery_deltas"]:
            if delta["post_snapshot_id"] is not None:
                assert delta["concept_delta"] is not None or (
                    delta["baseline_concept_mastery"] is None
                )

        async with async_session_factory() as db:
            baselines_after = {
                str(d.curriculum_node_id): (
                    d.baseline_source_evidence_hash,
                    d.baseline_concept_mastery,
                    d.baseline_execution_accuracy,
                )
                for d in (
                    await db.scalars(
                        select(ReassessmentMasteryDelta).where(
                            ReassessmentMasteryDelta.reassessment_id
                            == uuid.UUID(ra_id)
                        )
                    )
                ).all()
            }
            evidence_after = int(
                await db.scalar(
                    select(func.count())
                    .select_from(MasteryEvidence)
                    .where(MasteryEvidence.tenant_id == tenant_id)
                )
                or 0
            )
        assert baselines_after == baseline_before
        assert evidence_after == evidence_before

        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "tenant_slug": "demo",
            },
        )
        assert login.status_code == 200, login.text
        context = JwtAuthProvider(get_settings()).verify_access_token(
            login.json()["access_token"]
        )
        denied, _ = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"STUDENT"}),
                permissions=frozenset(),
            )
        )
        denied_headers = {"Authorization": f"Bearer {denied}"}
        assert (
            await client.post(
                f"/api/v1/improvement-assessments/{ctx['bp_id']}/reassessment",
                headers=denied_headers,
                json=_instantiate_payload(ctx["bp"]),
            )
        ).status_code == 403
        assert (
            await client.get(
                f"/api/v1/reassessments/{ra_id}", headers=denied_headers
            )
        ).status_code == 403
        assert (
            await client.post(
                f"/api/v1/reassessments/{ra_id}/b14/rebuild",
                headers=denied_headers,
            )
        ).status_code == 403


@pytest.mark.asyncio
async def test_b14_materialize_skips_unbound_or_mismatched_attempt() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _approve_blueprint_flow(client, headers)
        created = await client.post(
            f"/api/v1/improvement-assessments/{ctx['bp_id']}/reassessment",
            headers=headers,
            json=_instantiate_payload(ctx["bp"]),
        )
        assert created.status_code == 200, created.text
        ra_id = created.json()["id"]

        async with async_session_factory() as db:
            ra = await db.scalar(
                select(Reassessment).where(Reassessment.id == uuid.UUID(ra_id))
            )
            assert ra is not None
            existing_pr = await db.scalar(select(PublishedResult).limit(1))
            assert existing_pr is not None
            fake = PublishedResult(
                tenant_id=ra.tenant_id,
                submission_id=existing_pr.submission_id,
                student_id=ra.student_id,
                assessment_id=ra.assessment_id,
                assessment_version_id=ra.assessment_version_id,
                evaluation_run_id=existing_pr.evaluation_run_id,
                version_number=99,
                status="PUBLISHED",
                ledger_snapshot_hash="d" * 64,
                total_score=Decimal("1.0000"),
                max_total_score=Decimal("5.0000"),
            )
            db.add(fake)
            await db.flush()
            skipped = await materialize_b14_for_published_result(
                db, tenant_id=ra.tenant_id, published=fake
            )
            assert skipped is None
            await db.rollback()

