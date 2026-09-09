"""B14 reassessment instantiation and mastery delta materialization (PEV-043)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Assessment,
    AssessmentVersion,
    Curriculum,
    ImprovementAssessment,
    ImprovementAssessmentItem,
    LearningPlanRun,
    MasteryState,
    MasteryStateSnapshot,
    PublishedResult,
    Question,
    QuestionCurriculumMapping,
    QuestionVersion,
    Reassessment,
    ReassessmentItem,
    ReassessmentMasteryDelta,
    Student,
    Submission,
)
from app.db.models.mastery import ALGORITHM_VERSION_B12_V1
from app.db.models.reassessment import ALGORITHM_VERSION_B14_V1
from app.services.audit import add_audit_event
from app.services.reassessment_mastery import compute_delta

__all__ = [
    "ReassessmentError",
    "compute_delta",
    "instantiate_reassessment",
    "get_reassessment",
    "list_reassessments_for_student",
    "bind_submission_if_reassessment",
    "materialize_b14_for_published_result",
    "rebuild_b14",
    "serialize_reassessment",
]

MARKS_QUANT = Decimal("0.01")


class ReassessmentError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_float_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _parse_positive_marks(raw: Any, *, field: str = "max_marks") -> Decimal:
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ReassessmentError(
            "REASSESSMENT_INVALID_MARKS",
            f"{field} must be a positive decimal",
        ) from exc
    value = value.quantize(MARKS_QUANT, rounding=ROUND_HALF_UP)
    if value <= 0:
        raise ReassessmentError(
            "REASSESSMENT_INVALID_MARKS",
            f"{field} must be greater than zero",
        )
    return value


def _instantiation_hash(normalized_items: list[dict[str, Any]]) -> str:
    payload = [
        {
            "item_id": row["item_id"],
            "prompt_text": row["prompt_text"],
            "max_marks": row["max_marks_str"],
            "question_type": row["question_type"],
            "instructions": row["instructions"],
        }
        for row in sorted(normalized_items, key=lambda r: r["item_id"])
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _stable_code_for_item(item: ImprovementAssessmentItem) -> str:
    if item.item_code:
        return f"RA-{item.item_code}"[:100]
    return f"RA-{str(item.id).replace('-', '')[:16]}"


async def serialize_reassessment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reassessment: Reassessment,
) -> dict[str, Any]:
    blueprint = await db.scalar(
        select(ImprovementAssessment).where(
            ImprovementAssessment.id == reassessment.improvement_assessment_id,
            ImprovementAssessment.tenant_id == tenant_id,
        )
    )
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == reassessment.assessment_id,
            Assessment.tenant_id == tenant_id,
        )
    )
    items = list(
        (
            await db.scalars(
                select(ReassessmentItem)
                .where(
                    ReassessmentItem.tenant_id == tenant_id,
                    ReassessmentItem.reassessment_id == reassessment.id,
                )
                .order_by(ReassessmentItem.created_at.asc(), ReassessmentItem.id.asc())
            )
        ).all()
    )
    deltas = list(
        (
            await db.scalars(
                select(ReassessmentMasteryDelta)
                .where(
                    ReassessmentMasteryDelta.tenant_id == tenant_id,
                    ReassessmentMasteryDelta.reassessment_id == reassessment.id,
                    ReassessmentMasteryDelta.algorithm_version
                    == ALGORITHM_VERSION_B14_V1,
                )
                .order_by(ReassessmentMasteryDelta.curriculum_node_id.asc())
            )
        ).all()
    )
    return {
        "id": str(reassessment.id),
        "improvement_assessment_id": str(reassessment.improvement_assessment_id),
        "blueprint_title": blueprint.title if blueprint else "",
        "blueprint_version_number": blueprint.version_number if blueprint else 1,
        "student_id": str(reassessment.student_id),
        "curriculum_id": str(reassessment.curriculum_id),
        "assessment_id": str(reassessment.assessment_id),
        "assessment_status": assessment.status if assessment else "DRAFT",
        "assessment_version_id": str(reassessment.assessment_version_id),
        "submission_id": (
            str(reassessment.submission_id) if reassessment.submission_id else None
        ),
        "published_result_id": (
            str(reassessment.published_result_id)
            if reassessment.published_result_id
            else None
        ),
        "status": reassessment.status,
        "algorithm_version": reassessment.algorithm_version,
        "instantiation_hash": reassessment.instantiation_hash,
        "baseline_captured_at": reassessment.baseline_captured_at.isoformat(),
        "created_at": reassessment.created_at.isoformat(),
        "updated_at": reassessment.updated_at.isoformat(),
        "items": [
            {
                "id": str(item.id),
                "improvement_assessment_item_id": str(
                    item.improvement_assessment_item_id
                ),
                "question_version_id": str(item.question_version_id),
                "curriculum_node_id": str(item.curriculum_node_id),
                "item_code_snapshot": item.item_code_snapshot,
                "template_kind_snapshot": item.template_kind_snapshot,
                "question_template_ref_snapshot": item.question_template_ref_snapshot,
            }
            for item in items
        ],
        "mastery_deltas": [
            {
                "curriculum_node_id": str(delta.curriculum_node_id),
                "baseline_concept_mastery": _as_float_or_none(
                    delta.baseline_concept_mastery
                ),
                "baseline_execution_accuracy": _as_float_or_none(
                    delta.baseline_execution_accuracy
                ),
                "baseline_concept_decisive_count": delta.baseline_concept_decisive_count,
                "baseline_execution_decisive_count": (
                    delta.baseline_execution_decisive_count
                ),
                "baseline_concept_inconclusive_count": (
                    delta.baseline_concept_inconclusive_count
                ),
                "baseline_execution_inconclusive_count": (
                    delta.baseline_execution_inconclusive_count
                ),
                "baseline_evidence_count": delta.baseline_evidence_count,
                "baseline_source_evidence_hash": delta.baseline_source_evidence_hash,
                "post_snapshot_id": (
                    str(delta.post_snapshot_id) if delta.post_snapshot_id else None
                ),
                "post_published_result_id": (
                    str(delta.post_published_result_id)
                    if delta.post_published_result_id
                    else None
                ),
                "post_concept_mastery": _as_float_or_none(delta.post_concept_mastery),
                "post_execution_accuracy": _as_float_or_none(
                    delta.post_execution_accuracy
                ),
                "post_concept_decisive_count": delta.post_concept_decisive_count,
                "post_execution_decisive_count": delta.post_execution_decisive_count,
                "post_concept_inconclusive_count": (
                    delta.post_concept_inconclusive_count
                ),
                "post_execution_inconclusive_count": (
                    delta.post_execution_inconclusive_count
                ),
                "post_evidence_count": delta.post_evidence_count,
                "post_source_evidence_hash": delta.post_source_evidence_hash,
                "concept_delta": _as_float_or_none(delta.concept_delta),
                "execution_delta": _as_float_or_none(delta.execution_delta),
                "materialized_at": (
                    delta.materialized_at.isoformat() if delta.materialized_at else None
                ),
                "algorithm_version": delta.algorithm_version,
            }
            for delta in deltas
        ],
    }


async def get_reassessment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reassessment_id: uuid.UUID,
) -> dict[str, Any]:
    reassessment = await db.scalar(
        select(Reassessment).where(
            Reassessment.id == reassessment_id,
            Reassessment.tenant_id == tenant_id,
        )
    )
    if reassessment is None:
        raise ReassessmentError("NOT_FOUND", "Reassessment not found")
    return await serialize_reassessment(
        db, tenant_id=tenant_id, reassessment=reassessment
    )


async def list_reassessments_for_student(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    q = select(Reassessment).where(
        Reassessment.tenant_id == tenant_id,
        Reassessment.student_id == student_id,
    )
    if curriculum_id is not None:
        q = q.where(Reassessment.curriculum_id == curriculum_id)
    rows = list(
        (
            await db.scalars(
                q.order_by(Reassessment.created_at.desc(), Reassessment.id.desc())
            )
        ).all()
    )
    return [
        await serialize_reassessment(db, tenant_id=tenant_id, reassessment=row)
        for row in rows
    ]


async def instantiate_reassessment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    blueprint_id: uuid.UUID,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    blueprint = await db.scalar(
        select(ImprovementAssessment).where(
            ImprovementAssessment.id == blueprint_id,
            ImprovementAssessment.tenant_id == tenant_id,
        )
    )
    if blueprint is None:
        raise ReassessmentError("NOT_FOUND", "Improvement assessment not found")
    if blueprint.status != "APPROVED":
        raise ReassessmentError(
            "REASSESSMENT_BLUEPRINT_NOT_APPROVED",
            "Only APPROVED blueprints can be instantiated",
        )

    student = await db.scalar(
        select(Student).where(
            Student.id == blueprint.student_id, Student.tenant_id == tenant_id
        )
    )
    if student is None:
        raise ReassessmentError("NOT_FOUND", "Student not found")
    curriculum = await db.scalar(
        select(Curriculum).where(
            Curriculum.id == blueprint.curriculum_id, Curriculum.tenant_id == tenant_id
        )
    )
    if curriculum is None:
        raise ReassessmentError("NOT_FOUND", "Curriculum not found")

    run = await db.scalar(
        select(LearningPlanRun).where(
            LearningPlanRun.id == blueprint.learning_plan_run_id,
            LearningPlanRun.tenant_id == tenant_id,
        )
    )
    if run is None or run.status != "READY":
        raise ReassessmentError(
            "LEARNING_PLAN_NOT_READY",
            "Source learning plan must be READY",
        )

    from app.services.learning import _compute_current_hashes

    _s, _g, current_input, _ = await _compute_current_hashes(
        db,
        tenant_id=tenant_id,
        student_id=blueprint.student_id,
        curriculum_id=blueprint.curriculum_id,
    )
    if current_input != blueprint.input_hash or current_input != run.input_hash:
        raise ReassessmentError(
            "REASSESSMENT_BLUEPRINT_STALE",
            "Blueprint is stale relative to current learning evidence",
        )

    blueprint_items = list(
        (
            await db.scalars(
                select(ImprovementAssessmentItem)
                .where(
                    ImprovementAssessmentItem.improvement_assessment_id == blueprint.id,
                    ImprovementAssessmentItem.tenant_id == tenant_id,
                )
                .order_by(
                    ImprovementAssessmentItem.sort_order.asc(),
                    ImprovementAssessmentItem.id.asc(),
                )
            )
        ).all()
    )
    if not blueprint_items:
        raise ReassessmentError(
            "REASSESSMENT_ITEMS_INVALID",
            "Blueprint has no items to instantiate",
        )

    expected_ids = {item.id for item in blueprint_items}
    if not items:
        raise ReassessmentError(
            "REASSESSMENT_ITEMS_INVALID",
            "Request must include every blueprint item exactly once",
        )

    seen: set[uuid.UUID] = set()
    normalized: list[dict[str, Any]] = []
    by_id = {item.id: item for item in blueprint_items}

    for raw in items:
        try:
            item_id = uuid.UUID(str(raw["improvement_assessment_item_id"]))
        except (KeyError, ValueError, TypeError) as exc:
            raise ReassessmentError(
                "REASSESSMENT_ITEMS_INVALID",
                "improvement_assessment_item_id must be a UUID",
            ) from exc
        if item_id not in expected_ids:
            raise ReassessmentError(
                "REASSESSMENT_ITEMS_INVALID",
                "Request contains an unknown blueprint item",
            )
        if item_id in seen:
            raise ReassessmentError(
                "REASSESSMENT_ITEMS_INVALID",
                "Request contains a duplicate blueprint item",
            )
        seen.add(item_id)

        prompt_text = str(raw.get("prompt_text") or "").strip()
        if not prompt_text:
            raise ReassessmentError(
                "REASSESSMENT_INVALID_PROMPT",
                "prompt_text must be non-empty",
            )
        marks = _parse_positive_marks(raw.get("max_marks"))
        question_type = raw.get("question_type")
        if question_type is not None:
            question_type = str(question_type).strip() or None
        instructions = raw.get("instructions")
        if instructions is not None:
            instructions = str(instructions).strip() or None

        bp_item = by_id[item_id]
        normalized.append(
            {
                "item_id": str(item_id),
                "item": bp_item,
                "prompt_text": prompt_text,
                "max_marks": marks,
                "max_marks_str": format(marks, "f"),
                "question_type": question_type or "SHORT",
                "instructions": instructions,
            }
        )

    if seen != expected_ids:
        raise ReassessmentError(
            "REASSESSMENT_ITEMS_INVALID",
            "Request must cover every blueprint item exactly once",
        )

    inst_hash = _instantiation_hash(normalized)

    existing = await db.scalar(
        select(Reassessment).where(
            Reassessment.tenant_id == tenant_id,
            Reassessment.improvement_assessment_id == blueprint.id,
        )
    )
    if existing is not None:
        if existing.instantiation_hash == inst_hash:
            return await serialize_reassessment(
                db, tenant_id=tenant_id, reassessment=existing
            )
        raise ReassessmentError(
            "REASSESSMENT_ALREADY_INSTANTIATED",
            "Blueprint already instantiated with different content",
        )

    total_marks = sum((row["max_marks"] for row in normalized), Decimal("0.00"))
    total_marks = total_marks.quantize(MARKS_QUANT, rounding=ROUND_HALF_UP)
    short = str(blueprint.id).replace("-", "")[:8]
    assessment_code = f"RA-{blueprint.version_number}-{short}"[:100]
    now = _utcnow()

    try:
        async with db.begin_nested():
            assessment = Assessment(
                tenant_id=tenant_id,
                curriculum_id=blueprint.curriculum_id,
                code=assessment_code,
                title=blueprint.title,
                description=None,
                assessment_type="IMPROVEMENT_REASSESSMENT",
                max_marks=total_marks,
                duration_minutes=None,
                status="DRAFT",
                created_by=actor_user_id,
            )
            db.add(assessment)
            await db.flush()

            version = AssessmentVersion(
                tenant_id=tenant_id,
                assessment_id=assessment.id,
                version_number=1,
                title=blueprint.title,
                instructions=None,
                max_marks=total_marks,
                status="DRAFT",
                created_by=actor_user_id,
            )
            db.add(version)
            await db.flush()

            reassessment = Reassessment(
                tenant_id=tenant_id,
                improvement_assessment_id=blueprint.id,
                student_id=blueprint.student_id,
                curriculum_id=blueprint.curriculum_id,
                assessment_id=assessment.id,
                assessment_version_id=version.id,
                submission_id=None,
                published_result_id=None,
                status="CREATED",
                instantiation_hash=inst_hash,
                baseline_captured_at=now,
                algorithm_version=ALGORITHM_VERSION_B14_V1,
                created_by=actor_user_id,
            )
            db.add(reassessment)
            await db.flush()

            # Preserve blueprint sort order for questions.
            ordered = sorted(
                normalized,
                key=lambda row: (
                    row["item"].sort_order,
                    str(row["item"].id),
                ),
            )
            node_ids: set[uuid.UUID] = set()
            for sequence, row in enumerate(ordered, start=1):
                blueprint_item: ImprovementAssessmentItem = row["item"]
                node_ids.add(blueprint_item.curriculum_node_id)
                stable_code = _stable_code_for_item(blueprint_item)
                question = Question(
                    tenant_id=tenant_id,
                    assessment_id=assessment.id,
                    stable_code=stable_code,
                )
                db.add(question)
                await db.flush()

                qv = QuestionVersion(
                    tenant_id=tenant_id,
                    assessment_version_id=version.id,
                    question_id=question.id,
                    parent_question_version_id=None,
                    display_label=blueprint_item.item_code or str(sequence),
                    sequence=sequence,
                    prompt_text=row["prompt_text"],
                    max_marks=row["max_marks"],
                    question_type=row["question_type"],
                    scoring_mode="LEAF_SCORABLE",
                    instructions=row["instructions"],
                )
                db.add(qv)
                await db.flush()

                db.add(
                    QuestionCurriculumMapping(
                        tenant_id=tenant_id,
                        question_version_id=qv.id,
                        curriculum_node_id=blueprint_item.curriculum_node_id,
                        mapping_type="PRIMARY",
                        weight=Decimal("1.00"),
                    )
                )
                db.add(
                    ReassessmentItem(
                        tenant_id=tenant_id,
                        reassessment_id=reassessment.id,
                        improvement_assessment_item_id=blueprint_item.id,
                        question_version_id=qv.id,
                        curriculum_node_id=blueprint_item.curriculum_node_id,
                        item_code_snapshot=blueprint_item.item_code,
                        template_kind_snapshot=blueprint_item.template_kind,
                        question_template_ref_snapshot=blueprint_item.question_template_ref
                        or None,
                    )
                )

            for node_id in sorted(node_ids, key=str):
                state = await db.scalar(
                    select(MasteryState).where(
                        MasteryState.tenant_id == tenant_id,
                        MasteryState.student_id == blueprint.student_id,
                        MasteryState.curriculum_node_id == node_id,
                        MasteryState.algorithm_version == ALGORITHM_VERSION_B12_V1,
                    )
                )
                db.add(
                    ReassessmentMasteryDelta(
                        tenant_id=tenant_id,
                        reassessment_id=reassessment.id,
                        curriculum_node_id=node_id,
                        baseline_concept_mastery=(
                            state.concept_mastery if state else None
                        ),
                        baseline_execution_accuracy=(
                            state.execution_accuracy if state else None
                        ),
                        baseline_concept_decisive_count=(
                            state.concept_decisive_count if state else 0
                        ),
                        baseline_execution_decisive_count=(
                            state.execution_decisive_count if state else 0
                        ),
                        baseline_concept_inconclusive_count=(
                            state.concept_inconclusive_count if state else 0
                        ),
                        baseline_execution_inconclusive_count=(
                            state.execution_inconclusive_count if state else 0
                        ),
                        baseline_evidence_count=state.evidence_count if state else 0,
                        baseline_source_evidence_hash=(
                            state.source_evidence_hash if state else ""
                        ),
                        algorithm_version=ALGORITHM_VERSION_B14_V1,
                    )
                )

            await db.flush()
    except IntegrityError as exc:
        raced = await db.scalar(
            select(Reassessment).where(
                Reassessment.tenant_id == tenant_id,
                Reassessment.improvement_assessment_id == blueprint.id,
            )
        )
        if raced is not None and raced.instantiation_hash == inst_hash:
            return await serialize_reassessment(
                db, tenant_id=tenant_id, reassessment=raced
            )
        raise ReassessmentError(
            "REASSESSMENT_ALREADY_INSTANTIATED",
            "Blueprint already instantiated",
        ) from exc

    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="Reassessment",
        entity_id=reassessment.id,
        action="reassessment_instantiated",
        after={
            "improvement_assessment_id": str(blueprint.id),
            "assessment_id": str(assessment.id),
            "instantiation_hash": inst_hash,
            "status": "CREATED",
        },
    )
    await db.flush()
    return await serialize_reassessment(
        db, tenant_id=tenant_id, reassessment=reassessment
    )


async def bind_submission_if_reassessment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    reassessment = await db.scalar(
        select(Reassessment).where(
            Reassessment.tenant_id == tenant_id,
            Reassessment.assessment_id == submission.assessment_id,
        )
    )
    if reassessment is None:
        return
    if submission.student_id is None:
        return
    if submission.student_id != reassessment.student_id:
        raise ReassessmentError(
            "REASSESSMENT_STUDENT_MISMATCH",
            "Submission student does not match reassessment student",
        )
    if (
        reassessment.submission_id is not None
        and reassessment.submission_id != submission.id
    ):
        raise ReassessmentError(
            "REASSESSMENT_ATTEMPT_BOUND",
            "Reassessment already bound to a different submission",
        )
    if reassessment.submission_id is None:
        reassessment.submission_id = submission.id
        reassessment.status = "SUBMITTED"
        reassessment.updated_at = _utcnow()
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="Reassessment",
            entity_id=reassessment.id,
            action="reassessment_submission_bound",
            after={
                "submission_id": str(submission.id),
                "status": "SUBMITTED",
            },
        )
        await db.flush()


def _apply_post_from_snapshot(
    delta: ReassessmentMasteryDelta,
    *,
    snapshot: MasteryStateSnapshot,
    published_result_id: uuid.UUID,
    now: datetime,
) -> None:
    delta.post_snapshot_id = snapshot.id
    delta.post_published_result_id = published_result_id
    delta.post_concept_mastery = snapshot.concept_mastery
    delta.post_execution_accuracy = snapshot.execution_accuracy
    delta.post_concept_decisive_count = snapshot.concept_decisive_count
    delta.post_execution_decisive_count = snapshot.execution_decisive_count
    delta.post_concept_inconclusive_count = snapshot.concept_inconclusive_count
    delta.post_execution_inconclusive_count = snapshot.execution_inconclusive_count
    delta.post_evidence_count = snapshot.evidence_count
    delta.post_source_evidence_hash = snapshot.source_evidence_hash
    delta.concept_delta = compute_delta(
        delta.baseline_concept_mastery, delta.post_concept_mastery
    )
    delta.execution_delta = compute_delta(
        delta.baseline_execution_accuracy, delta.post_execution_accuracy
    )
    delta.materialized_at = now
    delta.algorithm_version = ALGORITHM_VERSION_B14_V1


async def materialize_b14_for_published_result(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published: PublishedResult,
    actor_user_id: uuid.UUID | None = None,
    require_snapshots: bool = False,
) -> dict[str, Any] | None:
    if published.student_id is None:
        return None

    reassessment = await db.scalar(
        select(Reassessment).where(
            Reassessment.tenant_id == tenant_id,
            Reassessment.assessment_id == published.assessment_id,
            Reassessment.student_id == published.student_id,
        )
    )
    if reassessment is None:
        return None

    if reassessment.submission_id is None:
        # Require prior identity bind; do not auto-bind here.
        return None
    if reassessment.submission_id != published.submission_id:
        return None

    deltas = list(
        (
            await db.scalars(
                select(ReassessmentMasteryDelta).where(
                    ReassessmentMasteryDelta.tenant_id == tenant_id,
                    ReassessmentMasteryDelta.reassessment_id == reassessment.id,
                    ReassessmentMasteryDelta.algorithm_version
                    == ALGORITHM_VERSION_B14_V1,
                )
            )
        ).all()
    )
    now = _utcnow()
    filled = 0
    for delta in deltas:
        snapshot = await db.scalar(
            select(MasteryStateSnapshot).where(
                MasteryStateSnapshot.tenant_id == tenant_id,
                MasteryStateSnapshot.student_id == published.student_id,
                MasteryStateSnapshot.curriculum_node_id == delta.curriculum_node_id,
                MasteryStateSnapshot.published_result_id == published.id,
                MasteryStateSnapshot.algorithm_version == ALGORITHM_VERSION_B12_V1,
            )
        )
        if snapshot is None:
            if require_snapshots:
                raise ReassessmentError(
                    "REASSESSMENT_B14_SNAPSHOT_MISSING",
                    "B12 mastery snapshot missing for reassessment node",
                )
            continue
        _apply_post_from_snapshot(
            delta,
            snapshot=snapshot,
            published_result_id=published.id,
            now=now,
        )
        filled += 1

    reassessment.published_result_id = published.id
    reassessment.status = "PUBLISHED"
    reassessment.updated_at = now
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="Reassessment",
        entity_id=reassessment.id,
        action="reassessment_mastery_materialized",
        after={
            "published_result_id": str(published.id),
            "delta_count": filled,
            "status": "PUBLISHED",
        },
    )
    await db.flush()
    return {
        "reassessment_id": str(reassessment.id),
        "algorithm_version": ALGORITHM_VERSION_B14_V1,
        "delta_count": filled,
        "published_result_id": str(published.id),
        "source": "MASTERY_STATE_SNAPSHOT",
    }


async def rebuild_b14(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    reassessment_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, Any]:
    reassessment = await db.scalar(
        select(Reassessment).where(
            Reassessment.id == reassessment_id,
            Reassessment.tenant_id == tenant_id,
        )
    )
    if reassessment is None:
        raise ReassessmentError("NOT_FOUND", "Reassessment not found")

    published: PublishedResult | None = None
    if reassessment.published_result_id is not None:
        published = await db.scalar(
            select(PublishedResult).where(
                PublishedResult.id == reassessment.published_result_id,
                PublishedResult.tenant_id == tenant_id,
                PublishedResult.status == "PUBLISHED",
            )
        )
    if published is None and reassessment.submission_id is not None:
        published = await db.scalar(
            select(PublishedResult).where(
                PublishedResult.tenant_id == tenant_id,
                PublishedResult.submission_id == reassessment.submission_id,
                PublishedResult.status == "PUBLISHED",
            )
        )

    if published is None:
        raise ReassessmentError(
            "REASSESSMENT_B14_NOT_READY",
            "No PUBLISHED result available to rebuild B14 deltas",
        )

    # Capture baseline fingerprint for audit/tests (never mutate baselines).
    baseline_before = list(
        (
            await db.scalars(
                select(ReassessmentMasteryDelta).where(
                    ReassessmentMasteryDelta.tenant_id == tenant_id,
                    ReassessmentMasteryDelta.reassessment_id == reassessment.id,
                )
            )
        ).all()
    )
    baseline_hashes = {
        str(d.curriculum_node_id): (
            d.baseline_source_evidence_hash,
            str(d.baseline_concept_mastery),
            str(d.baseline_execution_accuracy),
        )
        for d in baseline_before
    }

    result = await materialize_b14_for_published_result(
        db,
        tenant_id=tenant_id,
        published=published,
        actor_user_id=actor_user_id,
        require_snapshots=True,
    )
    if result is None:
        raise ReassessmentError(
            "REASSESSMENT_B14_NOT_READY",
            "Reassessment is not bound to this published attempt",
        )

    after = list(
        (
            await db.scalars(
                select(ReassessmentMasteryDelta).where(
                    ReassessmentMasteryDelta.tenant_id == tenant_id,
                    ReassessmentMasteryDelta.reassessment_id == reassessment.id,
                )
            )
        ).all()
    )
    for d in after:
        key = str(d.curriculum_node_id)
        expected = baseline_hashes.get(key)
        actual = (
            d.baseline_source_evidence_hash,
            str(d.baseline_concept_mastery),
            str(d.baseline_execution_accuracy),
        )
        if expected is None or expected != actual:
            raise ReassessmentError(
                "REASSESSMENT_BASELINE_MUTATED",
                "B14 rebuild must never change baseline mastery fields",
            )

    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="Reassessment",
        entity_id=reassessment.id,
        action="reassessment_mastery_rebuilt",
        after={
            "published_result_id": str(published.id),
            "delta_count": result["delta_count"],
        },
    )
    await db.flush()
    return result
