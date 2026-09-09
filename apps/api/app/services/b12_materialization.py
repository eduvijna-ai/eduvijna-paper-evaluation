"""B12 longitudinal mastery state, snapshots, and mistake notebook materialization."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, nulls_last, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Assessment,
    CriterionEvaluation,
    CurriculumNode,
    LearningRecommendation,
    MasteryEvidence,
    MasteryState,
    MasteryStateSnapshot,
    MistakeNotebookEntry,
    PublishedResult,
    Question,
    QuestionEvaluation,
    QuestionVersion,
    Student,
)
from app.db.models.mastery import ALGORITHM_VERSION_B8_V1, ALGORITHM_VERSION_B12_V1
from app.services.analytics import AnalyticsError
from app.services.audit import add_audit_event
from app.services.b12_algorithm import (
    RECOVERABLE_DISCLAIMER,
    RECURRENCE_THRESHOLD,
    compute_node_state,
    is_academic_error,
    is_review_condition,
    practice_kind_for_error,
    source_evidence_hash,
)

B12Error = AnalyticsError

_PRACTICE_TO_REC_KINDS: dict[str, frozenset[str]] = {
    "CONCEPT_CHECK": frozenset({"TARGET_CONCEPT"}),
    "EXECUTION_PRACTICE": frozenset({"EXECUTION_PRACTICE"}),
    "PROCEDURE_PRACTICE": frozenset({"PROCEDURE_PRACTICE"}),
}


def _decimal_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.0001")), "f")


def _as_float_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _effective_at(pr: PublishedResult) -> datetime:
    return pr.published_at or pr.created_at


def _states_from_evidence(
    evidence_rows: list[MasteryEvidence],
) -> dict[uuid.UUID, dict[str, Any]]:
    by_node: dict[uuid.UUID, list[MasteryEvidence]] = defaultdict(list)
    for row in evidence_rows:
        by_node[row.curriculum_node_id].append(row)

    out: dict[uuid.UUID, dict[str, Any]] = {}
    for node_id, rows in by_node.items():
        concept_exec = [r for r in rows if r.evidence_type in {"CONCEPT", "EXECUTION"}]
        if not concept_exec:
            continue
        concept = [r.strength for r in concept_exec if r.evidence_type == "CONCEPT"]
        execution = [r.strength for r in concept_exec if r.evidence_type == "EXECUTION"]
        state = compute_node_state(concept, execution)
        ids = [r.id for r in concept_exec]
        out[node_id] = {
            **state,
            "curriculum_id": concept_exec[0].curriculum_id,
            "source_evidence_hash": source_evidence_hash(ids),
            "evidence_ids": ids,
        }
    return out


async def materialize_b12_for_student(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
    source_published_result_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise B12Error("NOT_FOUND", "Student not found")

    now = datetime.now(UTC)

    evidence = list(
        (
            await db.scalars(
                select(MasteryEvidence)
                .join(
                    PublishedResult,
                    PublishedResult.id == MasteryEvidence.published_result_id,
                )
                .where(
                    MasteryEvidence.tenant_id == tenant_id,
                    MasteryEvidence.student_id == student_id,
                    MasteryEvidence.algorithm_version == ALGORITHM_VERSION_B8_V1,
                    PublishedResult.status == "PUBLISHED",
                    PublishedResult.tenant_id == tenant_id,
                )
            )
        ).all()
    )

    overall_hash = source_evidence_hash(e.id for e in evidence)

    # --- Current MasteryState from ALL evidence ---
    current_states = _states_from_evidence(evidence)
    mastery_state_count = 0
    for node_id, computed in current_states.items():
        stmt = pg_insert(MasteryState).values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            student_id=student_id,
            curriculum_id=computed["curriculum_id"],
            curriculum_node_id=node_id,
            concept_mastery=computed["concept_mastery"],
            execution_accuracy=computed["execution_accuracy"],
            concept_decisive_count=computed["concept_decisive_count"],
            execution_decisive_count=computed["execution_decisive_count"],
            concept_inconclusive_count=computed["concept_inconclusive_count"],
            execution_inconclusive_count=computed["execution_inconclusive_count"],
            evidence_count=computed["evidence_count"],
            source_evidence_hash=computed["source_evidence_hash"],
            algorithm_version=ALGORITHM_VERSION_B12_V1,
            last_updated_at=now,
            created_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_mastery_states_student_node_algo",
            set_={
                "curriculum_id": stmt.excluded.curriculum_id,
                "concept_mastery": stmt.excluded.concept_mastery,
                "execution_accuracy": stmt.excluded.execution_accuracy,
                "concept_decisive_count": stmt.excluded.concept_decisive_count,
                "execution_decisive_count": stmt.excluded.execution_decisive_count,
                "concept_inconclusive_count": stmt.excluded.concept_inconclusive_count,
                "execution_inconclusive_count": stmt.excluded.execution_inconclusive_count,
                "evidence_count": stmt.excluded.evidence_count,
                "source_evidence_hash": stmt.excluded.source_evidence_hash,
                "last_updated_at": now,
            },
        )
        await db.execute(stmt)
        mastery_state_count += 1

    # Drop stale current-state rows no longer backed by PUBLISHED evidence.
    # Historical snapshots/evidence remain for audit; only current MasteryState
    # is pruned so superseded-only nodes do not remain visible.
    stale_filter = [
        MasteryState.tenant_id == tenant_id,
        MasteryState.student_id == student_id,
        MasteryState.algorithm_version == ALGORITHM_VERSION_B12_V1,
    ]
    if current_states:
        stale_filter.append(
            MasteryState.curriculum_node_id.notin_(list(current_states.keys()))
        )
    await db.execute(delete(MasteryState).where(*stale_filter))

    # --- Historical snapshots per published result (cumulative) ---
    pr_ids = {e.published_result_id for e in evidence}
    published_results: list[PublishedResult] = []
    if pr_ids:
        published_results = list(
            (
                await db.scalars(
                    select(PublishedResult)
                    .where(
                        PublishedResult.tenant_id == tenant_id,
                        PublishedResult.id.in_(pr_ids),
                        PublishedResult.status == "PUBLISHED",
                    )
                    .order_by(
                        nulls_last(PublishedResult.published_at.asc()),
                        PublishedResult.created_at.asc(),
                        PublishedResult.id.asc(),
                    )
                )
            ).all()
        )

    evidence_by_pr: dict[uuid.UUID, list[MasteryEvidence]] = defaultdict(list)
    for e in evidence:
        evidence_by_pr[e.published_result_id].append(e)

    snapshot_count = 0
    cumulative: list[MasteryEvidence] = []
    for pr in published_results:
        cumulative.extend(evidence_by_pr.get(pr.id, []))
        states = _states_from_evidence(cumulative)
        effective = _effective_at(pr)
        for node_id, computed in states.items():
            stmt = pg_insert(MasteryStateSnapshot).values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                student_id=student_id,
                curriculum_id=computed["curriculum_id"],
                curriculum_node_id=node_id,
                published_result_id=pr.id,
                assessment_id=pr.assessment_id,
                concept_mastery=computed["concept_mastery"],
                execution_accuracy=computed["execution_accuracy"],
                concept_decisive_count=computed["concept_decisive_count"],
                execution_decisive_count=computed["execution_decisive_count"],
                concept_inconclusive_count=computed["concept_inconclusive_count"],
                execution_inconclusive_count=computed["execution_inconclusive_count"],
                evidence_count=computed["evidence_count"],
                source_evidence_hash=computed["source_evidence_hash"],
                algorithm_version=ALGORITHM_VERSION_B12_V1,
                effective_at=effective,
                created_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_mastery_state_snapshots_grain",
                set_={
                    "curriculum_id": stmt.excluded.curriculum_id,
                    "assessment_id": stmt.excluded.assessment_id,
                    "concept_mastery": stmt.excluded.concept_mastery,
                    "execution_accuracy": stmt.excluded.execution_accuracy,
                    "concept_decisive_count": stmt.excluded.concept_decisive_count,
                    "execution_decisive_count": stmt.excluded.execution_decisive_count,
                    "concept_inconclusive_count": stmt.excluded.concept_inconclusive_count,
                    "execution_inconclusive_count": stmt.excluded.execution_inconclusive_count,
                    "evidence_count": stmt.excluded.evidence_count,
                    "source_evidence_hash": stmt.excluded.source_evidence_hash,
                    "effective_at": stmt.excluded.effective_at,
                },
            )
            await db.execute(stmt)
            snapshot_count += 1

    # --- Mistake notebook ---
    notebook_entry_count = await _materialize_mistake_notebook(
        db,
        tenant_id=tenant_id,
        student_id=student_id,
        evidence=evidence,
        published_by_id={p.id: p for p in published_results},
        now=now,
    )

    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="Student",
        entity_id=student_id,
        action="b12_materialized",
        after={
            "student_id": str(student_id),
            "source_published_result_id": (
                str(source_published_result_id) if source_published_result_id else None
            ),
            "algorithm_version": ALGORITHM_VERSION_B12_V1,
            "mastery_state_count": mastery_state_count,
            "snapshot_count": snapshot_count,
            "notebook_entry_count": notebook_entry_count,
            "source_evidence_hash": overall_hash,
        },
    )
    await db.flush()

    return {
        "student_id": str(student_id),
        "algorithm_version": ALGORITHM_VERSION_B12_V1,
        "mastery_state_count": mastery_state_count,
        "snapshot_count": snapshot_count,
        "notebook_entry_count": notebook_entry_count,
        "source_evidence_hash": overall_hash,
        "source": "MASTERY_EVIDENCE",
    }


async def _materialize_mistake_notebook(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    evidence: list[MasteryEvidence],
    published_by_id: dict[uuid.UUID, PublishedResult],
    now: datetime,
) -> int:
    # Grain: published_result × question_evaluation × academic_error_code
    grains: dict[tuple[uuid.UUID, uuid.UUID, str], list[MasteryEvidence]] = defaultdict(
        list
    )
    for e in evidence:
        for code in e.academic_error_codes or []:
            code_s = str(code)
            if is_review_condition(code_s) or not is_academic_error(code_s):
                continue
            key = (e.published_result_id, e.question_evaluation_id, code_s)
            grains[key].append(e)

    if not grains:
        return 0

    qe_ids = {qe_id for _, qe_id, _ in grains}
    qes = {
        q.id: q
        for q in (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.id.in_(qe_ids),
                )
            )
        ).all()
    }

    # ACTIVE learning recommendations for student
    recs = list(
        (
            await db.scalars(
                select(LearningRecommendation).where(
                    LearningRecommendation.tenant_id == tenant_id,
                    LearningRecommendation.student_id == student_id,
                    LearningRecommendation.status == "ACTIVE",
                )
            )
        ).all()
    )

    count = 0
    for (pr_id, qe_id, code), rows in grains.items():
        qe = qes.get(qe_id)
        if qe is None or qe.final_human_approved_score is None:
            continue
        pr = published_by_id.get(pr_id)
        if pr is None:
            continue

        node_ids = sorted({str(r.curriculum_node_id) for r in rows})
        practice = practice_kind_for_error(code)
        allowed_kinds = _PRACTICE_TO_REC_KINDS.get(practice, frozenset())
        linked = sorted(
            {
                str(r.id)
                for r in recs
                if str(r.target_node_id) in set(node_ids)
                and r.recommendation_kind in allowed_kinds
            }
        )
        evidence_ids = sorted({str(r.id) for r in rows})
        first_div = (
            str(qe.first_divergence_step)
            if qe.first_divergence_step is not None
            else None
        )
        stmt = pg_insert(MistakeNotebookEntry).values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            student_id=student_id,
            published_result_id=pr_id,
            assessment_id=rows[0].assessment_id,
            submission_id=rows[0].submission_id,
            question_evaluation_id=qe_id,
            question_version_id=rows[0].question_version_id,
            academic_error_code=code,
            final_score=Decimal(qe.final_human_approved_score),
            max_mark=Decimal(qe.max_mark),
            deduction_reasons=list(qe.deduction_reasons or []),
            first_divergence_step=first_div,
            curriculum_node_ids=node_ids,
            recommended_practice_kind=practice,
            linked_learning_recommendation_ids=linked,
            source_ledger_snapshot_hash=rows[0].source_ledger_snapshot_hash,
            source_mastery_evidence_ids=evidence_ids,
            algorithm_version=ALGORITHM_VERSION_B12_V1,
            materialized_at=now,
            effective_at=_effective_at(pr),
            created_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_mistake_notebook_entries_grain",
            set_={
                "assessment_id": stmt.excluded.assessment_id,
                "submission_id": stmt.excluded.submission_id,
                "question_version_id": stmt.excluded.question_version_id,
                "final_score": stmt.excluded.final_score,
                "max_mark": stmt.excluded.max_mark,
                "deduction_reasons": stmt.excluded.deduction_reasons,
                "first_divergence_step": stmt.excluded.first_divergence_step,
                "curriculum_node_ids": stmt.excluded.curriculum_node_ids,
                "recommended_practice_kind": stmt.excluded.recommended_practice_kind,
                "linked_learning_recommendation_ids": (
                    stmt.excluded.linked_learning_recommendation_ids
                ),
                "source_ledger_snapshot_hash": stmt.excluded.source_ledger_snapshot_hash,
                "source_mastery_evidence_ids": stmt.excluded.source_mastery_evidence_ids,
                "materialized_at": now,
                "effective_at": stmt.excluded.effective_at,
            },
        )
        await db.execute(stmt)
        count += 1
    return count


async def get_student_mastery_state(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
) -> dict[str, Any]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise B12Error("NOT_FOUND", "Student not found")

    states = list(
        (
            await db.scalars(
                select(MasteryState).where(
                    MasteryState.tenant_id == tenant_id,
                    MasteryState.student_id == student_id,
                    MasteryState.algorithm_version == ALGORITHM_VERSION_B12_V1,
                )
            )
        ).all()
    )
    node_ids = [s.curriculum_node_id for s in states]
    nodes = {
        n.id: n
        for n in (
            await db.scalars(
                select(CurriculumNode).where(
                    CurriculumNode.tenant_id == tenant_id,
                    CurriculumNode.id.in_(node_ids),
                )
            )
        ).all()
    } if node_ids else {}

    items: list[dict[str, Any]] = []
    for state in sorted(
        states,
        key=lambda s: (nodes[s.curriculum_node_id].code if s.curriculum_node_id in nodes else ""),
    ):
        node = nodes.get(state.curriculum_node_id)
        if node is None:
            continue
        items.append(
            {
                "id": str(state.id),
                "curriculum_node_id": str(state.curriculum_node_id),
                "curriculum_id": str(state.curriculum_id),
                "code": node.code,
                "title": node.name,
                "node_type": node.node_type,
                "concept_mastery": _as_float_or_none(state.concept_mastery),
                "execution_accuracy": _as_float_or_none(state.execution_accuracy),
                "concept_decisive_count": state.concept_decisive_count,
                "execution_decisive_count": state.execution_decisive_count,
                "concept_inconclusive_count": state.concept_inconclusive_count,
                "execution_inconclusive_count": state.execution_inconclusive_count,
                "evidence_count": state.evidence_count,
                "insufficient_concept_evidence": state.concept_mastery is None,
                "insufficient_execution_evidence": state.execution_accuracy is None,
                "source_evidence_hash": state.source_evidence_hash,
                "algorithm_version": ALGORITHM_VERSION_B12_V1,
                "last_updated_at": state.last_updated_at.isoformat(),
            }
        )

    return {
        "student_id": str(student_id),
        "items": items,
        "algorithm_version": ALGORITHM_VERSION_B12_V1,
        "source": "MASTERY_EVIDENCE",
        "as_of": datetime.now(UTC).isoformat(),
    }


async def get_student_mastery_trend(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_node_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise B12Error("NOT_FOUND", "Student not found")

    q = (
        select(MasteryStateSnapshot)
        .join(
            PublishedResult,
            PublishedResult.id == MasteryStateSnapshot.published_result_id,
        )
        .where(
            MasteryStateSnapshot.tenant_id == tenant_id,
            MasteryStateSnapshot.student_id == student_id,
            MasteryStateSnapshot.algorithm_version == ALGORITHM_VERSION_B12_V1,
            PublishedResult.tenant_id == tenant_id,
            PublishedResult.status == "PUBLISHED",
        )
    )
    if curriculum_node_id is not None:
        q = q.where(MasteryStateSnapshot.curriculum_node_id == curriculum_node_id)
    snapshots = list((await db.scalars(q)).all())

    node_ids = list({s.curriculum_node_id for s in snapshots})
    assessment_ids = list({s.assessment_id for s in snapshots})
    nodes = {
        n.id: n
        for n in (
            await db.scalars(
                select(CurriculumNode).where(
                    CurriculumNode.tenant_id == tenant_id,
                    CurriculumNode.id.in_(node_ids),
                )
            )
        ).all()
    } if node_ids else {}
    assessments = {
        a.id: a
        for a in (
            await db.scalars(
                select(Assessment).where(
                    Assessment.tenant_id == tenant_id,
                    Assessment.id.in_(assessment_ids),
                )
            )
        ).all()
    } if assessment_ids else {}

    points: list[dict[str, Any]] = []
    for snap in sorted(
        snapshots,
        key=lambda s: (
            s.effective_at,
            nodes[s.curriculum_node_id].code if s.curriculum_node_id in nodes else "",
        ),
    ):
        node = nodes.get(snap.curriculum_node_id)
        asm = assessments.get(snap.assessment_id)
        if node is None or asm is None:
            continue
        points.append(
            {
                "curriculum_node_id": str(snap.curriculum_node_id),
                "curriculum_id": str(snap.curriculum_id),
                "code": node.code,
                "title": node.name,
                "published_result_id": str(snap.published_result_id),
                "assessment_id": str(snap.assessment_id),
                "assessment_code": asm.code,
                "effective_at": snap.effective_at.isoformat(),
                "concept_mastery": _as_float_or_none(snap.concept_mastery),
                "execution_accuracy": _as_float_or_none(snap.execution_accuracy),
                "concept_decisive_count": snap.concept_decisive_count,
                "execution_decisive_count": snap.execution_decisive_count,
                "evidence_count": snap.evidence_count,
                "insufficient_concept_evidence": snap.concept_mastery is None,
                "insufficient_execution_evidence": snap.execution_accuracy is None,
                "source_evidence_hash": snap.source_evidence_hash,
                "algorithm_version": ALGORITHM_VERSION_B12_V1,
            }
        )

    return {
        "student_id": str(student_id),
        "curriculum_node_id": str(curriculum_node_id) if curriculum_node_id else None,
        "points": points,
        "algorithm_version": ALGORITHM_VERSION_B12_V1,
        "source": "MASTERY_EVIDENCE",
        "as_of": datetime.now(UTC).isoformat(),
    }


async def get_student_repeated_errors(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
) -> dict[str, Any]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise B12Error("NOT_FOUND", "Student not found")

    evidence = list(
        (
            await db.scalars(
                select(MasteryEvidence)
                .join(
                    PublishedResult,
                    PublishedResult.id == MasteryEvidence.published_result_id,
                )
                .where(
                    MasteryEvidence.tenant_id == tenant_id,
                    MasteryEvidence.student_id == student_id,
                    MasteryEvidence.algorithm_version == ALGORITHM_VERSION_B8_V1,
                    PublishedResult.status == "PUBLISHED",
                    PublishedResult.tenant_id == tenant_id,
                )
            )
        ).all()
    )

    pr_ids = {e.published_result_id for e in evidence}
    published = {
        p.id: p
        for p in (
            await db.scalars(
                select(PublishedResult).where(
                    PublishedResult.tenant_id == tenant_id,
                    PublishedResult.id.in_(pr_ids),
                )
            )
        ).all()
    } if pr_ids else {}

    # Dedupe grain: published_result × QE × error_code
    grains: dict[tuple[uuid.UUID, uuid.UUID, str], MasteryEvidence] = {}
    node_by_grain: dict[tuple[uuid.UUID, uuid.UUID, str], set[uuid.UUID]] = defaultdict(
        set
    )
    for e in evidence:
        for code in e.academic_error_codes or []:
            code_s = str(code)
            if is_review_condition(code_s) or not is_academic_error(code_s):
                continue
            key = (e.published_result_id, e.question_evaluation_id, code_s)
            if key not in grains:
                grains[key] = e
            node_by_grain[key].add(e.curriculum_node_id)

    by_code: dict[str, list[tuple[uuid.UUID, uuid.UUID, str]]] = defaultdict(list)
    for key in grains:
        by_code[key[2]].append(key)

    items: list[dict[str, Any]] = []
    for code, keys in by_code.items():
        pr_set = {k[0] for k in keys}
        if len(pr_set) < RECURRENCE_THRESHOLD:
            continue
        assessment_set = {grains[k].assessment_id for k in keys}
        seen_ats = [
            _effective_at(published[k[0]])
            for k in keys
            if k[0] in published
        ]
        if not seen_ats:
            continue
        affected = [
            {
                "published_result_id": str(k[0]),
                "assessment_id": str(grains[k].assessment_id),
                "question_evaluation_id": str(k[1]),
                "question_version_id": str(grains[k].question_version_id),
            }
            for k in sorted(keys, key=lambda x: (str(x[0]), str(x[1])))
        ]
        nodes = sorted({str(n) for k in keys for n in node_by_grain[k]})
        items.append(
            {
                "error_code": code,
                "occurrence_count": len(keys),
                "distinct_published_result_count": len(pr_set),
                "distinct_assessment_count": len(assessment_set),
                "first_seen_at": min(seen_ats).isoformat(),
                "last_seen_at": max(seen_ats).isoformat(),
                "affected_question_evaluations": affected,
                "curriculum_node_ids": nodes,
            }
        )

    items.sort(
        key=lambda i: (
            -i["distinct_published_result_count"],
            -i["occurrence_count"],
            i["error_code"],
        )
    )

    return {
        "student_id": str(student_id),
        "items": items,
        "recurrence_threshold": RECURRENCE_THRESHOLD,
        "algorithm_version": ALGORITHM_VERSION_B12_V1,
        "source": "MASTERY_EVIDENCE",
        "as_of": datetime.now(UTC).isoformat(),
    }


async def get_student_recoverable_marks(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
) -> dict[str, Any]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise B12Error("NOT_FOUND", "Student not found")

    published = list(
        (
            await db.scalars(
                select(PublishedResult).where(
                    PublishedResult.tenant_id == tenant_id,
                    PublishedResult.student_id == student_id,
                    PublishedResult.status == "PUBLISHED",
                )
            )
        ).all()
    )
    if not published:
        return {
            "student_id": str(student_id),
            "total_lost_marks": "0.0000",
            "attributed_potentially_recoverable_marks": "0.0000",
            "unattributed_lost_marks": "0.0000",
            "items": [],
            "disclaimer": RECOVERABLE_DISCLAIMER,
            "algorithm_version": ALGORITHM_VERSION_B12_V1,
            "source": "PUBLISHED_LEDGER",
            "as_of": datetime.now(UTC).isoformat(),
        }

    run_ids = [p.evaluation_run_id for p in published]
    pr_by_run = {p.evaluation_run_id: p for p in published}

    qes = list(
        (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id.in_(run_ids),
                )
            )
        ).all()
    )
    qe_ids = [q.id for q in qes]
    qe_by_id = {q.id: q for q in qes}

    criteria = list(
        (
            await db.scalars(
                select(CriterionEvaluation).where(
                    CriterionEvaluation.tenant_id == tenant_id,
                    CriterionEvaluation.question_evaluation_id.in_(qe_ids),
                    CriterionEvaluation.final_marks.is_not(None),
                )
            )
        ).all()
    ) if qe_ids else []

    total_lost = Decimal("0")
    attributed = Decimal("0")
    by_code: dict[str, dict[str, Any]] = {}

    for ce in criteria:
        qe = qe_by_id.get(ce.question_evaluation_id)
        if qe is None:
            continue
        pr = pr_by_run.get(qe.evaluation_run_id)
        if pr is None:
            continue
        lost = Decimal(ce.max_marks) - Decimal(ce.final_marks)  # type: ignore[arg-type]
        if lost < 0:
            lost = Decimal("0")
        total_lost += lost
        code = ce.error_code
        if code and is_academic_error(code) and not is_review_condition(code) and lost > 0:
            attributed += lost
            bucket = by_code.setdefault(
                code,
                {
                    "error_code": code,
                    "potentially_recoverable_marks": Decimal("0"),
                    "occurrence_count": 0,
                    "affected_references": [],
                },
            )
            bucket["potentially_recoverable_marks"] += lost
            bucket["occurrence_count"] += 1
            bucket["affected_references"].append(
                {
                    "published_result_id": str(pr.id),
                    "assessment_id": str(pr.assessment_id),
                    "question_evaluation_id": str(qe.id),
                    "criterion_evaluation_id": str(ce.id),
                }
            )

    if attributed > total_lost:
        attributed = total_lost
    unattributed = total_lost - attributed
    if unattributed < 0:
        unattributed = Decimal("0")

    items: list[dict[str, Any]] = []
    for code in sorted(
        by_code.keys(),
        key=lambda c: (-by_code[c]["potentially_recoverable_marks"], c),
    ):
        bucket = by_code[code]
        marks = bucket["potentially_recoverable_marks"]
        pct: float | None
        if total_lost > 0:
            pct = float((marks / total_lost) * Decimal("100"))
        else:
            pct = None
        items.append(
            {
                "error_code": code,
                "potentially_recoverable_marks": _decimal_str(marks),
                "occurrence_count": bucket["occurrence_count"],
                "percent_of_total_lost": pct,
                "affected_references": bucket["affected_references"],
            }
        )

    return {
        "student_id": str(student_id),
        "total_lost_marks": _decimal_str(total_lost),
        "attributed_potentially_recoverable_marks": _decimal_str(attributed),
        "unattributed_lost_marks": _decimal_str(unattributed),
        "items": items,
        "disclaimer": RECOVERABLE_DISCLAIMER,
        "algorithm_version": ALGORITHM_VERSION_B12_V1,
        "source": "PUBLISHED_LEDGER",
        "as_of": datetime.now(UTC).isoformat(),
    }


async def get_student_mistake_notebook(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
) -> dict[str, Any]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise B12Error("NOT_FOUND", "Student not found")

    entries = list(
        (
            await db.scalars(
                select(MistakeNotebookEntry)
                .join(
                    PublishedResult,
                    PublishedResult.id == MistakeNotebookEntry.published_result_id,
                )
                .where(
                    MistakeNotebookEntry.tenant_id == tenant_id,
                    MistakeNotebookEntry.student_id == student_id,
                    MistakeNotebookEntry.algorithm_version == ALGORITHM_VERSION_B12_V1,
                    PublishedResult.tenant_id == tenant_id,
                    PublishedResult.status == "PUBLISHED",
                )
                .order_by(
                    MistakeNotebookEntry.effective_at.desc(),
                    MistakeNotebookEntry.id.desc(),
                )
            )
        ).all()
    )

    assessment_ids = list({e.assessment_id for e in entries})
    qv_ids = list({e.question_version_id for e in entries})
    node_id_set: set[uuid.UUID] = set()
    for e in entries:
        for nid in e.curriculum_node_ids or []:
            node_id_set.add(uuid.UUID(str(nid)))

    assessments = {
        a.id: a
        for a in (
            await db.scalars(
                select(Assessment).where(
                    Assessment.tenant_id == tenant_id,
                    Assessment.id.in_(assessment_ids),
                )
            )
        ).all()
    } if assessment_ids else {}

    qvs = {
        qv.id: qv
        for qv in (
            await db.scalars(
                select(QuestionVersion).where(
                    QuestionVersion.tenant_id == tenant_id,
                    QuestionVersion.id.in_(qv_ids),
                )
            )
        ).all()
    } if qv_ids else {}
    question_ids = list({qv.question_id for qv in qvs.values()})
    questions = {
        q.id: q
        for q in (
            await db.scalars(
                select(Question).where(
                    Question.tenant_id == tenant_id,
                    Question.id.in_(question_ids),
                )
            )
        ).all()
    } if question_ids else {}

    nodes = {
        n.id: n
        for n in (
            await db.scalars(
                select(CurriculumNode).where(
                    CurriculumNode.tenant_id == tenant_id,
                    CurriculumNode.id.in_(list(node_id_set)),
                )
            )
        ).all()
    } if node_id_set else {}

    out_entries: list[dict[str, Any]] = []
    for e in entries:
        asm = assessments.get(e.assessment_id)
        qv = qvs.get(e.question_version_id)
        question = questions.get(qv.question_id) if qv else None
        curriculum_nodes = []
        for nid in e.curriculum_node_ids or []:
            node = nodes.get(uuid.UUID(str(nid)))
            if node is None:
                continue
            curriculum_nodes.append(
                {
                    "id": str(node.id),
                    "code": node.code,
                    "title": node.name,
                    "node_type": node.node_type,
                }
            )
        out_entries.append(
            {
                "id": str(e.id),
                "published_result_id": str(e.published_result_id),
                "assessment_id": str(e.assessment_id),
                "assessment_code": asm.code if asm else "",
                "submission_id": str(e.submission_id),
                "question_evaluation_id": str(e.question_evaluation_id),
                "question_version_id": str(e.question_version_id),
                "question_code": (
                    question.stable_code
                    if question
                    else (qv.display_label if qv else "")
                ),
                "academic_error_code": e.academic_error_code,
                "final_score": _decimal_str(Decimal(e.final_score)),
                "max_mark": _decimal_str(Decimal(e.max_mark)),
                "deduction_reasons": list(e.deduction_reasons or []),
                "first_divergence_step": e.first_divergence_step,
                "curriculum_nodes": curriculum_nodes,
                "recommended_practice_kind": e.recommended_practice_kind,
                "linked_learning_recommendation_ids": list(
                    e.linked_learning_recommendation_ids or []
                ),
                "source_ledger_snapshot_hash": e.source_ledger_snapshot_hash,
                "algorithm_version": ALGORITHM_VERSION_B12_V1,
                "materialized_at": e.materialized_at.isoformat(),
                "effective_at": e.effective_at.isoformat(),
            }
        )

    return {
        "student_id": str(student_id),
        "entries": out_entries,
        "algorithm_version": ALGORITHM_VERSION_B12_V1,
        "source": "PUBLISHED_LEDGER",
        "as_of": datetime.now(UTC).isoformat(),
    }
