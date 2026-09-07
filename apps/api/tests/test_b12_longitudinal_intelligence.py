"""B12 longitudinal mastery + mistake intelligence integration coverage."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.models import (
    CriterionEvaluation,
    MasteryEvidence,
    MasteryState,
    MasteryStateSnapshot,
    MistakeNotebookEntry,
    PublishedResult,
    QuestionEvaluation,
    Tenant,
)
from app.db.session import async_session_factory
from app.services.b12_materialization import materialize_b12_for_student
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)


async def _force_evidence(
    *,
    student_id: str,
    concept_strength: str | None = None,
    execution_strength: str | None = None,
    academic_codes: list[str] | None = None,
    review_codes: list[str] | None = None,
) -> None:
    async with async_session_factory() as db:
        rows = list(
            (
                await db.scalars(
                    select(MasteryEvidence).where(
                        MasteryEvidence.student_id == uuid.UUID(student_id),
                        MasteryEvidence.algorithm_version == "B8_V1",
                    )
                )
            ).all()
        )
        assert rows
        for r in rows:
            if concept_strength and r.evidence_type == "CONCEPT":
                r.strength = concept_strength
            if execution_strength and r.evidence_type == "EXECUTION":
                r.strength = execution_strength
            if academic_codes is not None:
                r.academic_error_codes = list(academic_codes)
            if review_codes is not None:
                r.review_condition_codes = list(review_codes)
        await db.commit()


async def _clone_published_evidence_for_same_student(
    *,
    student_id: str,
    academic_codes: list[str] | None = None,
) -> uuid.UUID:
    """Insert a second PUBLISHED result + cloned MasteryEvidence for the same student."""
    from datetime import UTC, datetime, timedelta

    async with async_session_factory() as db:
        sample = await db.scalar(
            select(MasteryEvidence).where(
                MasteryEvidence.student_id == uuid.UUID(student_id),
                MasteryEvidence.algorithm_version == "B8_V1",
            )
        )
        assert sample is not None
        source_pr = await db.scalar(
            select(PublishedResult).where(PublishedResult.id == sample.published_result_id)
        )
        assert source_pr is not None

        new_pr = PublishedResult(
            tenant_id=source_pr.tenant_id,
            submission_id=source_pr.submission_id,
            student_id=source_pr.student_id,
            assessment_id=source_pr.assessment_id,
            assessment_version_id=source_pr.assessment_version_id,
            evaluation_run_id=source_pr.evaluation_run_id,
            version_number=source_pr.version_number + 100,
            status="PUBLISHED",
            ledger_snapshot_hash=uuid.uuid4().hex + uuid.uuid4().hex,
            total_score=source_pr.total_score,
            max_total_score=source_pr.max_total_score,
            published_at=(source_pr.published_at or source_pr.created_at)
            + timedelta(days=1),
            created_at=datetime.now(UTC),
        )
        db.add(new_pr)
        await db.flush()

        source_rows = list(
            (
                await db.scalars(
                    select(MasteryEvidence).where(
                        MasteryEvidence.published_result_id == source_pr.id,
                        MasteryEvidence.student_id == uuid.UUID(student_id),
                    )
                )
            ).all()
        )
        for row in source_rows:
            db.add(
                MasteryEvidence(
                    tenant_id=row.tenant_id,
                    student_id=row.student_id,
                    curriculum_id=row.curriculum_id,
                    curriculum_node_id=row.curriculum_node_id,
                    published_result_id=new_pr.id,
                    submission_id=row.submission_id,
                    assessment_id=row.assessment_id,
                    assessment_version_id=row.assessment_version_id,
                    evaluation_run_id=row.evaluation_run_id,
                    question_evaluation_id=row.question_evaluation_id,
                    question_version_id=row.question_version_id,
                    evidence_type=row.evidence_type,
                    strength=row.strength,
                    score_ratio=row.score_ratio,
                    source_final_score=row.source_final_score,
                    source_max_mark=row.source_max_mark,
                    mapping_types=list(row.mapping_types or []),
                    mapping_weight=row.mapping_weight,
                    academic_error_codes=(
                        list(academic_codes)
                        if academic_codes is not None
                        else list(row.academic_error_codes or [])
                    ),
                    review_condition_codes=list(row.review_condition_codes or []),
                    reason_codes=list(row.reason_codes or []),
                    source_ledger_snapshot_hash=new_pr.ledger_snapshot_hash,
                    algorithm_version="B8_V1",
                )
            )
        await db.flush()
        await materialize_b12_for_student(
            db, tenant_id=new_pr.tenant_id, student_id=uuid.UUID(student_id)
        )
        await db.commit()
        return new_pr.id


@pytest.mark.asyncio
async def test_b12_unpublished_excluded_then_state_after_publish() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)

        before = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-state", headers=headers
        )
        assert before.status_code == 200, before.text
        assert before.json()["items"] == []
        assert before.json()["algorithm_version"] == "B12_V1"

        await _publish_approved(client, headers, sid)

        after = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-state", headers=headers
        )
        assert after.status_code == 200, after.text
        body = after.json()
        assert body["source"] == "MASTERY_EVIDENCE"
        assert body["items"]
        for item in body["items"]:
            assert item["algorithm_version"] == "B12_V1"
            assert "concept_mastery" in item
            assert "execution_accuracy" in item
            assert item["insufficient_concept_evidence"] == (item["concept_mastery"] is None)
            assert item["insufficient_execution_evidence"] == (
                item["execution_accuracy"] is None
            )


@pytest.mark.asyncio
async def test_b12_first_then_second_published_updates_state_and_trend() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid1, student_id = await _to_approved(
            client, headers, data, override_answered=Decimal("5")
        )
        await _publish_approved(client, headers, sid1)

        state1 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-state", headers=headers
        )
        assert state1.status_code == 200
        count1 = len(state1.json()["items"])
        assert count1 >= 1

        trend1 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-trend", headers=headers
        )
        assert trend1.status_code == 200
        points1 = len(trend1.json()["points"])
        assert points1 >= 1

        # Same student, second published result via cloned evidence (pipeline creates
        # a new student per submission — longitudinal needs one student × many PRs).
        await _clone_published_evidence_for_same_student(student_id=student_id)

        state2 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-state", headers=headers
        )
        assert state2.status_code == 200
        assert len(state2.json()["items"]) == count1

        trend2 = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-trend", headers=headers
        )
        assert trend2.status_code == 200
        assert len(trend2.json()["points"]) > points1

        async with async_session_factory() as db:
            snap_count = await db.scalar(
                select(func.count())
                .select_from(MasteryStateSnapshot)
                .where(MasteryStateSnapshot.student_id == uuid.UUID(student_id))
            )
            assert (snap_count or 0) >= 2


@pytest.mark.asyncio
async def test_b12_concept_execution_independent_and_inconclusive() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)

        await _force_evidence(
            student_id=student_id,
            concept_strength="STRONG",
            execution_strength="INCONCLUSIVE",
        )
        async with async_session_factory() as db:
            student = uuid.UUID(student_id)
            pr = await db.scalar(
                select(PublishedResult).where(
                    PublishedResult.student_id == student,
                    PublishedResult.status == "PUBLISHED",
                )
            )
            assert pr is not None
            await materialize_b12_for_student(
                db, tenant_id=pr.tenant_id, student_id=student
            )
            await db.commit()

        state = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-state", headers=headers
        )
        assert state.status_code == 200
        item = state.json()["items"][0]
        assert item["concept_mastery"] == pytest.approx(1.0)
        assert item["execution_accuracy"] is None
        assert item["insufficient_execution_evidence"] is True
        assert item["concept_decisive_count"] >= 1
        assert item["execution_decisive_count"] == 0
        assert item["execution_inconclusive_count"] >= 1


@pytest.mark.asyncio
async def test_b12_rebuild_idempotent_and_evidence_unmutated() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)

        async with async_session_factory() as db:
            evidence = list(
                (
                    await db.scalars(
                        select(MasteryEvidence).where(
                            MasteryEvidence.student_id == uuid.UUID(student_id)
                        )
                    )
                ).all()
            )
            evidence_ids = sorted(str(e.id) for e in evidence)
            evidence_count = len(evidence)
            state_count1 = await db.scalar(
                select(func.count())
                .select_from(MasteryState)
                .where(MasteryState.student_id == uuid.UUID(student_id))
            )
            snap_count1 = await db.scalar(
                select(func.count())
                .select_from(MasteryStateSnapshot)
                .where(MasteryStateSnapshot.student_id == uuid.UUID(student_id))
            )
            nb_count1 = await db.scalar(
                select(func.count())
                .select_from(MistakeNotebookEntry)
                .where(MistakeNotebookEntry.student_id == uuid.UUID(student_id))
            )

        rebuild1 = await client.post(
            f"/api/v1/analytics/students/{student_id}/b12/rebuild", headers=headers
        )
        assert rebuild1.status_code == 200, rebuild1.text
        body1 = rebuild1.json()
        assert body1["algorithm_version"] == "B12_V1"
        assert body1["source"] == "MASTERY_EVIDENCE"
        assert body1["mastery_state_count"] >= 1

        rebuild2 = await client.post(
            f"/api/v1/analytics/students/{student_id}/b12/rebuild", headers=headers
        )
        assert rebuild2.status_code == 200, rebuild2.text
        assert rebuild2.json()["mastery_state_count"] == body1["mastery_state_count"]
        assert rebuild2.json()["snapshot_count"] == body1["snapshot_count"]
        assert rebuild2.json()["notebook_entry_count"] == body1["notebook_entry_count"]
        assert rebuild2.json()["source_evidence_hash"] == body1["source_evidence_hash"]

        async with async_session_factory() as db:
            evidence2 = list(
                (
                    await db.scalars(
                        select(MasteryEvidence).where(
                            MasteryEvidence.student_id == uuid.UUID(student_id)
                        )
                    )
                ).all()
            )
            assert len(evidence2) == evidence_count
            assert sorted(str(e.id) for e in evidence2) == evidence_ids

            state_count2 = await db.scalar(
                select(func.count())
                .select_from(MasteryState)
                .where(MasteryState.student_id == uuid.UUID(student_id))
            )
            snap_count2 = await db.scalar(
                select(func.count())
                .select_from(MasteryStateSnapshot)
                .where(MasteryStateSnapshot.student_id == uuid.UUID(student_id))
            )
            nb_count2 = await db.scalar(
                select(func.count())
                .select_from(MistakeNotebookEntry)
                .where(MistakeNotebookEntry.student_id == uuid.UUID(student_id))
            )
            assert state_count2 == state_count1
            assert snap_count2 == snap_count1
            assert nb_count2 == nb_count1


@pytest.mark.asyncio
async def test_b12_repeated_errors_threshold_dedupe_and_review_excluded() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid1, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid1)

        # Single PR with CALCULATION across multiple evidence types → not recurring
        await _force_evidence(
            student_id=student_id,
            academic_codes=["CALCULATION", "UNREADABLE"],
        )
        async with async_session_factory() as db:
            pr = await db.scalar(
                select(PublishedResult).where(
                    PublishedResult.student_id == uuid.UUID(student_id),
                    PublishedResult.status == "PUBLISHED",
                )
            )
            assert pr is not None
            await materialize_b12_for_student(
                db, tenant_id=pr.tenant_id, student_id=uuid.UUID(student_id)
            )
            await db.commit()

        one = await client.get(
            f"/api/v1/analytics/students/{student_id}/repeated-errors", headers=headers
        )
        assert one.status_code == 200
        assert one.json()["recurrence_threshold"] == 2
        assert one.json()["items"] == []

        # Second published result for SAME student with same academic code → recurring
        await _clone_published_evidence_for_same_student(
            student_id=student_id, academic_codes=["CALCULATION"]
        )

        two = await client.get(
            f"/api/v1/analytics/students/{student_id}/repeated-errors", headers=headers
        )
        assert two.status_code == 200, two.text
        items = two.json()["items"]
        calc = next((i for i in items if i["error_code"] == "CALCULATION"), None)
        assert calc is not None
        assert calc["distinct_published_result_count"] >= 2
        assert calc["occurrence_count"] >= 2
        assert "UNREADABLE" not in {i["error_code"] for i in items}


@pytest.mark.asyncio
async def test_b12_recoverable_marks_final_only_decimal_and_cap() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(
            client, headers, data, override_answered=Decimal("3.5")
        )
        await _publish_approved(client, headers, sid)

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
            assert qes
            # proposed_ai must not drive recoverable; stamp criteria with academic codes
            for qe in qes:
                assert qe.proposed_ai_score is not None or qe.final_human_approved_score is not None
                criteria = list(
                    (
                        await db.scalars(
                            select(CriterionEvaluation).where(
                                CriterionEvaluation.question_evaluation_id == qe.id
                            )
                        )
                    ).all()
                )
                for ce in criteria:
                    # Inflate proposed so a buggy implementation would over-count
                    if ce.final_marks is not None:
                        ce.proposed_marks = Decimal(ce.max_marks)
                        if Decimal(ce.final_marks) < Decimal(ce.max_marks):
                            ce.error_code = "CALCULATION"
                        else:
                            ce.error_code = None
            await db.commit()

        resp = await client.get(
            f"/api/v1/analytics/students/{student_id}/recoverable-marks",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["algorithm_version"] == "B12_V1"
        assert body["source"] == "PUBLISHED_LEDGER"
        assert "analytical estimate" in body["disclaimer"]
        total = Decimal(body["total_lost_marks"])
        attributed = Decimal(body["attributed_potentially_recoverable_marks"])
        unattributed = Decimal(body["unattributed_lost_marks"])
        assert attributed <= total
        assert attributed + unattributed == total
        for item in body["items"]:
            assert Decimal(item["potentially_recoverable_marks"]) >= 0
            assert item["occurrence_count"] >= 1


@pytest.mark.asyncio
async def test_b12_mistake_notebook_links_no_duplicates_no_review() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)

        await _force_evidence(
            student_id=student_id,
            academic_codes=["CONCEPT", "UNREADABLE"],
        )
        async with async_session_factory() as db:
            pr = await db.scalar(
                select(PublishedResult).where(
                    PublishedResult.student_id == uuid.UUID(student_id),
                    PublishedResult.status == "PUBLISHED",
                )
            )
            assert pr is not None
            await materialize_b12_for_student(
                db, tenant_id=pr.tenant_id, student_id=uuid.UUID(student_id)
            )
            await db.commit()

        nb = await client.get(
            f"/api/v1/analytics/students/{student_id}/mistake-notebook",
            headers=headers,
        )
        assert nb.status_code == 200, nb.text
        body = nb.json()
        assert body["source"] == "PUBLISHED_LEDGER"
        entries = body["entries"]
        assert entries
        codes = {e["academic_error_code"] for e in entries}
        assert "CONCEPT" in codes
        assert "UNREADABLE" not in codes
        grains = {
            (
                e["published_result_id"],
                e["question_evaluation_id"],
                e["academic_error_code"],
            )
            for e in entries
        }
        assert len(grains) == len(entries)
        for e in entries:
            assert e["source_ledger_snapshot_hash"]
            assert e["recommended_practice_kind"] in {
                "CONCEPT_CHECK",
                "EXECUTION_PRACTICE",
                "PROCEDURE_PRACTICE",
            }
            assert isinstance(e["final_score"], str)
            assert isinstance(e["max_mark"], str)

        # Idempotent rematerialize → same entry count
        async with async_session_factory() as db:
            before = await db.scalar(
                select(func.count())
                .select_from(MistakeNotebookEntry)
                .where(MistakeNotebookEntry.student_id == uuid.UUID(student_id))
            )
            pr = await db.scalar(
                select(PublishedResult).where(
                    PublishedResult.student_id == uuid.UUID(student_id),
                    PublishedResult.status == "PUBLISHED",
                )
            )
            assert pr is not None
            await materialize_b12_for_student(
                db, tenant_id=pr.tenant_id, student_id=uuid.UUID(student_id)
            )
            await db.commit()
            after = await db.scalar(
                select(func.count())
                .select_from(MistakeNotebookEntry)
                .where(MistakeNotebookEntry.student_id == uuid.UUID(student_id))
            )
            assert after == before


@pytest.mark.asyncio
async def test_b12_tenant_isolation_and_rebuild_permission() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)

        foreign = await client.get(
            f"/api/v1/analytics/students/{uuid.uuid4()}/mastery-state",
            headers=headers,
        )
        assert foreign.status_code == 404

        # Retarget student to another tenant → 404 for original tenant caller
        async with async_session_factory() as db:
            from app.db.models import Student

            other = Tenant(slug=f"b12-other-{uuid.uuid4().hex[:8]}", name="Other")
            db.add(other)
            await db.flush()
            student = await db.scalar(
                select(Student).where(Student.id == uuid.UUID(student_id))
            )
            assert student is not None
            student.tenant_id = other.id
            await db.commit()

        stolen = await client.get(
            f"/api/v1/analytics/students/{student_id}/mastery-state",
            headers=headers,
        )
        assert stolen.status_code == 404

        rebuild = await client.post(
            f"/api/v1/analytics/students/{student_id}/b12/rebuild",
            headers=headers,
        )
        assert rebuild.status_code == 404
