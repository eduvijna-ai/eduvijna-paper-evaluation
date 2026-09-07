"""B9 learning plan + improvement blueprint service."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import get_learning_provider
from app.ai.tracing import canonical_input_hash, record_ai_execution, redacted_request_summary
from app.ai.types import (
    ImprovementBlueprintAIInput,
    ImprovementBlueprintItemContext,
    LearningPlanAIInput,
    LearningPlanPathStepContext,
    LearningPlanRecommendationContext,
    ProviderUnavailable,
)
from app.db.models import (
    Assessment,
    AuditEvent,
    Curriculum,
    CurriculumNode,
    CurriculumPrerequisite,
    ImprovementAssessment,
    ImprovementAssessmentItem,
    LearningPathStep,
    LearningPlanRun,
    LearningRecommendation,
    LearningRecommendationEvidence,
    LearningRecommendationPrerequisite,
    MasteryEvidence,
    Student,
)
from app.services.analytics import materialization_status_for_student
from app.services.learning_algorithm import (
    ALGORITHM_VERSION,
    EvidenceFact,
    LearningError,
    LearningPlanStructure,
    NodeMeta,
    PrerequisiteEdge,
    build_learning_plan_structure,
    reject_provider_urls,
)
from app.services.storage import ObjectStorage, learning_blueprint_export_key

logger = logging.getLogger(__name__)

MAX_BLUEPRINT_ITEMS = 40
MAX_RATIONALE_LEN = 2000

TEMPLATE_KIND_BY_RECOMMENDATION = {
    "PREREQUISITE_REPAIR": "PREREQUISITE_CHECK",
    "TARGET_CONCEPT": "CONCEPT_CHECK",
    "PROCEDURE_PRACTICE": "PROCEDURE_PRACTICE",
    "EXECUTION_PRACTICE": "EXECUTION_PRACTICE",
}

TEMPLATE_REF_BY_KIND = {
    "CONCEPT_CHECK": "CVB:CONCEPT_CHECK:v1",
    "PREREQUISITE_CHECK": "CVB:PREREQUISITE_CHECK:v1",
    "PROCEDURE_PRACTICE": "CVB:PROCEDURE_PRACTICE:v1",
    "EXECUTION_PRACTICE": "CVB:EXECUTION_PRACTICE:v1",
    "TRANSFER_CHECK": "CVB:TRANSFER_CHECK:v1",
}

__all__ = ["LearningError"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _get_student(
    db: AsyncSession, *, tenant_id: uuid.UUID, student_id: uuid.UUID
) -> Student:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise LearningError("NOT_FOUND", "Student not found")
    return student


async def _get_curriculum(
    db: AsyncSession, *, tenant_id: uuid.UUID, curriculum_id: uuid.UUID
) -> Curriculum:
    curriculum = await db.scalar(
        select(Curriculum).where(
            Curriculum.id == curriculum_id, Curriculum.tenant_id == tenant_id
        )
    )
    if curriculum is None:
        raise LearningError("NOT_FOUND", "Curriculum not found")
    return curriculum


async def _load_curriculum_graph(
    db: AsyncSession, *, tenant_id: uuid.UUID, curriculum_id: uuid.UUID
) -> tuple[list[NodeMeta], list[PrerequisiteEdge]]:
    nodes = list(
        (
            await db.scalars(
                select(CurriculumNode).where(
                    CurriculumNode.tenant_id == tenant_id,
                    CurriculumNode.curriculum_id == curriculum_id,
                )
            )
        ).all()
    )
    edges = list(
        (
            await db.scalars(
                select(CurriculumPrerequisite).where(
                    CurriculumPrerequisite.tenant_id == tenant_id,
                    CurriculumPrerequisite.curriculum_id == curriculum_id,
                )
            )
        ).all()
    )
    node_metas = [
        NodeMeta(
            id=n.id,
            code=n.code,
            title=n.name,
            node_type=n.node_type,
            status=n.status,
        )
        for n in nodes
    ]
    edge_metas = [
        PrerequisiteEdge(
            id=e.id,
            prerequisite_node_id=e.prerequisite_node_id,
            dependent_node_id=e.dependent_node_id,
            relationship_type=e.relationship_type,  # type: ignore[arg-type]
        )
        for e in edges
    ]
    return node_metas, edge_metas


async def _load_evidence_facts(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_id: uuid.UUID,
) -> list[EvidenceFact]:
    rows = list(
        (
            await db.scalars(
                select(MasteryEvidence).where(
                    MasteryEvidence.tenant_id == tenant_id,
                    MasteryEvidence.student_id == student_id,
                    MasteryEvidence.curriculum_id == curriculum_id,
                    MasteryEvidence.algorithm_version == "B8_V1",
                )
            )
        ).all()
    )
    return [
        EvidenceFact(
            id=r.id,
            published_result_id=r.published_result_id,
            question_evaluation_id=r.question_evaluation_id,
            curriculum_node_id=r.curriculum_node_id,
            evidence_type=r.evidence_type,
            strength=r.strength,
            score_ratio=Decimal(r.score_ratio),
            academic_error_codes=list(r.academic_error_codes or []),
            review_condition_codes=list(r.review_condition_codes or []),
            reason_codes=list(r.reason_codes or []),
            source_ledger_snapshot_hash=r.source_ledger_snapshot_hash,
            algorithm_version=r.algorithm_version,
        )
        for r in rows
    ]


async def _compute_current_hashes(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_id: uuid.UUID,
) -> tuple[str, str, str, LearningPlanStructure | None]:
    nodes, edges = await _load_curriculum_graph(
        db, tenant_id=tenant_id, curriculum_id=curriculum_id
    )
    facts = await _load_evidence_facts(
        db, tenant_id=tenant_id, student_id=student_id, curriculum_id=curriculum_id
    )
    structure = build_learning_plan_structure(
        curriculum_id=curriculum_id, nodes=nodes, edges=edges, facts=facts
    )
    return (
        structure.source_evidence_hash,
        structure.curriculum_graph_hash,
        structure.input_hash,
        structure,
    )


async def _ensure_evidence_ready(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_id: uuid.UUID,
) -> dict[str, Any]:
    mat = await materialization_status_for_student(
        db, tenant_id=tenant_id, student_id=student_id
    )
    status = mat.get("materialization_status")
    if status != "READY":
        raise LearningError(
            "LEARNING_EVIDENCE_NOT_READY",
            f"B8 mastery evidence materialization is {status}",
        )
    # Also require some B8 evidence for this curriculum (or allow empty READY?).
    # Spec: READY with no WEAK → empty plan OK; READY with zero evidence rows also OK
    # if published results exist for student. Curriculum-scoped evidence may be empty
    # if publications are for another curriculum — still READY gate passes.
    _ = curriculum_id
    return mat


async def _available_curricula(
    db: AsyncSession, *, tenant_id: uuid.UUID, student_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(
                    MasteryEvidence.curriculum_id,
                    Curriculum.code,
                    Curriculum.name,
                    func.count(MasteryEvidence.id),
                )
                .join(Curriculum, Curriculum.id == MasteryEvidence.curriculum_id)
                .where(
                    MasteryEvidence.tenant_id == tenant_id,
                    MasteryEvidence.student_id == student_id,
                    MasteryEvidence.algorithm_version == "B8_V1",
                    Curriculum.tenant_id == tenant_id,
                )
                .group_by(MasteryEvidence.curriculum_id, Curriculum.code, Curriculum.name)
                .order_by(Curriculum.code)
            )
        ).all()
    )
    return [
        {
            "id": str(cid),
            "curriculum_id": str(cid),
            "code": code,
            "name": name,
            "evidence_count": int(cnt),
        }
        for cid, code, name, cnt in rows
    ]


def _recommendation_key(rec_kind: str, node_id: uuid.UUID, priority: int) -> str:
    return f"{priority}:{rec_kind}:{node_id}"


def _step_key(kind: str, node_id: uuid.UUID, sequence: int) -> str:
    return f"{sequence}:{kind}:{node_id}"


async def prepare_learning_plan(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_id: uuid.UUID,
    requested_by: uuid.UUID,
) -> LearningPlanRun:
    await _get_student(db, tenant_id=tenant_id, student_id=student_id)
    await _get_curriculum(db, tenant_id=tenant_id, curriculum_id=curriculum_id)
    await _ensure_evidence_ready(
        db, tenant_id=tenant_id, student_id=student_id, curriculum_id=curriculum_id
    )

    source_hash, graph_hash, input_hash, _structure = await _compute_current_hashes(
        db, tenant_id=tenant_id, student_id=student_id, curriculum_id=curriculum_id
    )

    existing = await db.scalar(
        select(LearningPlanRun).where(
            LearningPlanRun.tenant_id == tenant_id,
            LearningPlanRun.student_id == student_id,
            LearningPlanRun.curriculum_id == curriculum_id,
            LearningPlanRun.input_hash == input_hash,
            LearningPlanRun.algorithm_version == ALGORITHM_VERSION,
            LearningPlanRun.status.in_(("QUEUED", "RUNNING", "READY")),
        )
    )
    if existing is not None:
        return existing

    max_version = await db.scalar(
        select(func.max(LearningPlanRun.version_number)).where(
            LearningPlanRun.tenant_id == tenant_id,
            LearningPlanRun.student_id == student_id,
            LearningPlanRun.curriculum_id == curriculum_id,
        )
    )
    version = int(max_version or 0) + 1

    run = LearningPlanRun(
        tenant_id=tenant_id,
        student_id=student_id,
        curriculum_id=curriculum_id,
        version_number=version,
        status="QUEUED",
        source_evidence_hash=source_hash,
        curriculum_graph_hash=graph_hash,
        input_hash=input_hash,
        algorithm_version=ALGORITHM_VERSION,
        requested_by=requested_by,
        requested_at=_utcnow(),
    )
    db.add(run)
    await db.flush()
    return run


async def run_learning_plan_pipeline(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> None:
    run = await db.scalar(
        select(LearningPlanRun).where(
            LearningPlanRun.id == run_id, LearningPlanRun.tenant_id == tenant_id
        )
    )
    if run is None:
        raise LearningError("NOT_FOUND", "Learning plan run not found")
    if run.status in {"READY", "SUPERSEDED"}:
        return
    if run.status == "FAILED":
        return

    run.status = "RUNNING"
    run.started_at = _utcnow()
    await db.flush()

    try:
        await _ensure_evidence_ready(
            db,
            tenant_id=tenant_id,
            student_id=run.student_id,
            curriculum_id=run.curriculum_id,
        )
        source_hash, graph_hash, input_hash, structure = await _compute_current_hashes(
            db,
            tenant_id=tenant_id,
            student_id=run.student_id,
            curriculum_id=run.curriculum_id,
        )
        if input_hash != run.input_hash:
            run.status = "FAILED"
            run.failure_code = "LEARNING_INPUT_CHANGED"
            run.failure_detail = (
                "Canonical learning input changed before generation completed"
            )
            run.finished_at = _utcnow()
            await db.commit()
            return

        assert structure is not None
        student = await _get_student(
            db, tenant_id=tenant_id, student_id=run.student_id
        )
        curriculum = await _get_curriculum(
            db, tenant_id=tenant_id, curriculum_id=run.curriculum_id
        )

        # Apply optional provider wording over server structure.
        rec_contexts = [
            LearningPlanRecommendationContext(
                recommendation_key=_recommendation_key(
                    r.recommendation_kind, r.target_node_id, r.priority
                ),
                target_node_id=r.target_node_id,
                target_node_code=r.target_node_code,
                target_node_title=r.target_node_title,
                recommendation_kind=r.recommendation_kind,
                priority=r.priority,
                concept_signal=r.concept_signal,
                execution_signal=r.execution_signal,
                procedure_signal=r.procedure_signal,
                default_rationale=r.rationale[:MAX_RATIONALE_LEN],
            )
            for r in structure.recommendations
        ]
        step_contexts = [
            LearningPlanPathStepContext(
                step_key=_step_key(s.kind, s.curriculum_node_id, s.sequence),
                curriculum_node_id=s.curriculum_node_id,
                kind=s.kind,
                title=s.title,
                default_description=(s.description or "")[:MAX_RATIONALE_LEN],
            )
            for s in structure.path_steps
        ]
        ai_input = LearningPlanAIInput(
            student_display_name=getattr(student, "full_name", None)
            or getattr(student, "display_name", None)
            or str(student.id),
            curriculum_name=curriculum.name,
            recommendations=rec_contexts,
            path_steps=step_contexts,
        )

        generation_source = "RULES_FALLBACK"
        provider_name: str | None = None
        model_name: str | None = None
        rationale_by_key = {
            c.recommendation_key: c.default_rationale for c in rec_contexts
        }
        desc_by_key = {c.step_key: c.default_description for c in step_contexts}

        provider = get_learning_provider()
        if provider is not None:
            started = _utcnow()
            try:
                result = await provider.generate_learning_plan(ai_input)
                for rec_prose in result.recommendation_prose:
                    reject_provider_urls(rec_prose.rationale)
                    if rec_prose.recommendation_key in rationale_by_key:
                        rationale_by_key[rec_prose.recommendation_key] = (
                            rec_prose.rationale[:MAX_RATIONALE_LEN]
                        )
                for step_prose in result.path_step_prose:
                    reject_provider_urls(step_prose.description)
                    if step_prose.step_key in desc_by_key:
                        desc_by_key[step_prose.step_key] = step_prose.description[
                            :MAX_RATIONALE_LEN
                        ]
                generation_source = (
                    "FIXED" if provider.provider_name == "fixed" else "AI"
                )
                provider_name = provider.provider_name
                await record_ai_execution(
                    db,
                    tenant_id=tenant_id,
                    operation="generate_learning_plan",
                    provider=provider.provider_name,
                    status="SUCCEEDED",
                    request_summary=redacted_request_summary(
                        operation="generate_learning_plan",
                        entity_ids={
                            "learning_plan_run_id": str(run.id),
                            "student_id": str(run.student_id),
                            "curriculum_id": str(run.curriculum_id),
                        },
                    ),
                    response_summary={
                        "recommendation_count": len(result.recommendation_prose),
                        "path_step_count": len(result.path_step_prose),
                    },
                    learning_plan_run_id=run.id,
                    input_hash=canonical_input_hash(ai_input.model_dump(mode="json")),
                    started_at=started,
                    finished_at=_utcnow(),
                )
            except (ProviderUnavailable, LearningError, Exception) as exc:  # noqa: BLE001
                logger.warning("learning provider failed; using rules fallback: %s", exc)
                generation_source = "RULES_FALLBACK"
                await record_ai_execution(
                    db,
                    tenant_id=tenant_id,
                    operation="generate_learning_plan",
                    provider=getattr(provider, "provider_name", "unknown"),
                    status="FAILED",
                    request_summary=redacted_request_summary(
                        operation="generate_learning_plan",
                        entity_ids={"learning_plan_run_id": str(run.id)},
                    ),
                    response_summary={},
                    learning_plan_run_id=run.id,
                    error_class=type(exc).__name__,
                    started_at=started,
                    finished_at=_utcnow(),
                )

        # Persist recommendations
        rec_by_node_kind: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
        for planned in structure.recommendations:
            key = _recommendation_key(
                planned.recommendation_kind, planned.target_node_id, planned.priority
            )
            rationale = rationale_by_key.get(key, planned.rationale)
            reject_provider_urls(rationale)
            row = LearningRecommendation(
                tenant_id=tenant_id,
                learning_plan_run_id=run.id,
                student_id=run.student_id,
                curriculum_id=run.curriculum_id,
                target_node_id=planned.target_node_id,
                recommendation_kind=planned.recommendation_kind,
                priority=planned.priority,
                rationale=rationale,
                concept_signal=planned.concept_signal,
                execution_signal=planned.execution_signal,
                procedure_signal=planned.procedure_signal,
                evidence_count=planned.evidence_count,
                mean_evidence_score_ratio=planned.mean_evidence_score_ratio,
                status="ACTIVE",
                target_node_code_snapshot=planned.target_node_code,
                target_node_title_snapshot=planned.target_node_title,
                target_node_type_snapshot=planned.target_node_type,
            )
            db.add(row)
            await db.flush()
            rec_by_node_kind[(planned.target_node_id, planned.recommendation_kind)] = (
                row.id
            )

            for prereq in planned.prerequisites:
                db.add(
                    LearningRecommendationPrerequisite(
                        tenant_id=tenant_id,
                        learning_recommendation_id=row.id,
                        curriculum_node_id=prereq.node_id,
                        relationship_type=prereq.relationship_type,
                        sequence=prereq.sequence,
                    )
                )
            for eid in planned.evidence_ids:
                db.add(
                    LearningRecommendationEvidence(
                        tenant_id=tenant_id,
                        learning_recommendation_id=row.id,
                        mastery_evidence_id=eid,
                    )
                )

        for step in structure.path_steps:
            skey = _step_key(step.kind, step.curriculum_node_id, step.sequence)
            description = desc_by_key.get(skey, step.description)
            reject_provider_urls(description)
            rec_id = None
            if step.recommendation_key is not None:
                kind = str(step.recommendation_key[2])
                rec_id = rec_by_node_kind.get((step.curriculum_node_id, kind))
            db.add(
                LearningPathStep(
                    tenant_id=tenant_id,
                    learning_plan_run_id=run.id,
                    learning_recommendation_id=rec_id,
                    curriculum_node_id=step.curriculum_node_id,
                    kind=step.kind,
                    sequence=step.sequence,
                    title=step.title,
                    description=description,
                    evidence_basis=step.evidence_basis,
                    relationship_type=step.relationship_type,
                )
            )

        # Supersede older READY runs for same student/curriculum
        older = list(
            (
                await db.scalars(
                    select(LearningPlanRun).where(
                        LearningPlanRun.tenant_id == tenant_id,
                        LearningPlanRun.student_id == run.student_id,
                        LearningPlanRun.curriculum_id == run.curriculum_id,
                        LearningPlanRun.id != run.id,
                        LearningPlanRun.status == "READY",
                    )
                )
            ).all()
        )
        for old in older:
            old.status = "SUPERSEDED"
            old.updated_at = _utcnow()

        run.status = "READY"
        run.generation_source = generation_source
        run.provider = provider_name
        run.model = model_name
        run.source_evidence_hash = source_hash
        run.curriculum_graph_hash = graph_hash
        run.finished_at = _utcnow()
        run.updated_at = _utcnow()
        await db.commit()
    except LearningError as exc:
        await db.rollback()
        run = await db.scalar(
            select(LearningPlanRun).where(LearningPlanRun.id == run_id)
        )
        if run is not None:
            run.status = "FAILED"
            run.failure_code = exc.code
            run.failure_detail = exc.message[:500]
            run.finished_at = _utcnow()
            await db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        run = await db.scalar(
            select(LearningPlanRun).where(LearningPlanRun.id == run_id)
        )
        if run is not None:
            run.status = "FAILED"
            run.failure_code = "LEARNING_PIPELINE_FAILED"
            run.failure_detail = str(exc)[:500]
            run.finished_at = _utcnow()
            await db.commit()
        raise


def _serialize_recommendation(
    rec: LearningRecommendation,
    prereqs: list[LearningRecommendationPrerequisite],
    evidence_ids: list[uuid.UUID],
) -> dict[str, Any]:
    return {
        "id": str(rec.id),
        "target_node_id": str(rec.target_node_id),
        "curriculum_node_id": str(rec.target_node_id),
        "recommendation_kind": rec.recommendation_kind,
        "priority": rec.priority,
        "rationale": rec.rationale,
        "concept_signal": rec.concept_signal,
        "execution_signal": rec.execution_signal,
        "procedure_signal": rec.procedure_signal,
        "evidence_count": rec.evidence_count,
        "mean_evidence_score_ratio": (
            float(rec.mean_evidence_score_ratio)
            if rec.mean_evidence_score_ratio is not None
            else None
        ),
        "status": rec.status,
        "code": rec.target_node_code_snapshot,
        "title": rec.target_node_title_snapshot,
        "node_type": rec.target_node_type_snapshot,
        "target_node_code": rec.target_node_code_snapshot,
        "target_node_title": rec.target_node_title_snapshot,
        "target_node_type": rec.target_node_type_snapshot,
        "target_node_code_snapshot": rec.target_node_code_snapshot,
        "target_node_title_snapshot": rec.target_node_title_snapshot,
        "target_node_type_snapshot": rec.target_node_type_snapshot,
        "prerequisites": [
            {
                "curriculum_node_id": str(p.curriculum_node_id),
                "relationship_type": p.relationship_type,
                "sequence": p.sequence,
            }
            for p in sorted(prereqs, key=lambda x: x.sequence)
        ],
        "mastery_evidence_ids": [str(e) for e in evidence_ids],
    }


async def _serialize_plan_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run: LearningPlanRun,
    is_stale: bool,
) -> dict[str, Any]:
    recs = list(
        (
            await db.scalars(
                select(LearningRecommendation)
                .where(
                    LearningRecommendation.tenant_id == tenant_id,
                    LearningRecommendation.learning_plan_run_id == run.id,
                )
                .order_by(
                    LearningRecommendation.priority,
                    LearningRecommendation.target_node_code_snapshot,
                )
            )
        ).all()
    )
    steps = list(
        (
            await db.scalars(
                select(LearningPathStep)
                .where(
                    LearningPathStep.tenant_id == tenant_id,
                    LearningPathStep.learning_plan_run_id == run.id,
                )
                .order_by(LearningPathStep.sequence)
            )
        ).all()
    )
    node_ids = {s.curriculum_node_id for s in steps}
    nodes_by_id: dict[uuid.UUID, CurriculumNode] = {}
    if node_ids:
        for curriculum_node in (
            await db.scalars(
                select(CurriculumNode).where(
                    CurriculumNode.tenant_id == tenant_id,
                    CurriculumNode.id.in_(node_ids),
                )
            )
        ).all():
            nodes_by_id[curriculum_node.id] = curriculum_node

    serialized_recs = []
    for rec in recs:
        prereqs = list(
            (
                await db.scalars(
                    select(LearningRecommendationPrerequisite).where(
                        LearningRecommendationPrerequisite.learning_recommendation_id
                        == rec.id
                    )
                )
            ).all()
        )
        ev = list(
            (
                await db.scalars(
                    select(LearningRecommendationEvidence).where(
                        LearningRecommendationEvidence.learning_recommendation_id
                        == rec.id
                    )
                )
            ).all()
        )
        serialized_recs.append(
            _serialize_recommendation(rec, prereqs, [e.mastery_evidence_id for e in ev])
        )

    serialized_path = []
    for step in steps:
        path_node = nodes_by_id.get(step.curriculum_node_id)
        serialized_path.append(
            {
                "id": str(step.id),
                "curriculum_node_id": str(step.curriculum_node_id),
                "learning_recommendation_id": (
                    str(step.learning_recommendation_id)
                    if step.learning_recommendation_id
                    else None
                ),
                "kind": step.kind,
                "sequence": step.sequence,
                "title": step.title,
                "description": step.description,
                "evidence_basis": step.evidence_basis,
                "relationship_type": step.relationship_type,
                "node_code": path_node.code if path_node is not None else None,
                "node_title": path_node.name if path_node is not None else None,
            }
        )

    return {
        "id": str(run.id),
        "run_id": str(run.id),
        "student_id": str(run.student_id),
        "curriculum_id": str(run.curriculum_id),
        "version_number": run.version_number,
        "status": run.status,
        "algorithm_version": run.algorithm_version,
        "generation_source": run.generation_source,
        "provider": run.provider,
        "model": run.model,
        "source_evidence_hash": run.source_evidence_hash,
        "curriculum_graph_hash": run.curriculum_graph_hash,
        "input_hash": run.input_hash,
        "is_stale": is_stale,
        "failure_code": run.failure_code,
        "failure_detail": run.failure_detail,
        "requested_at": run.requested_at.isoformat() if run.requested_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "recommendations": serialized_recs,
        "learning_path": serialized_path,
        "path": serialized_path,
        "no_gap_message": (
            "No evidence-backed learning gaps were identified from currently "
            "published results."
            if run.status == "READY" and not serialized_recs
            else None
        ),
    }


async def get_plan_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> dict[str, Any]:
    run = await db.scalar(
        select(LearningPlanRun).where(
            LearningPlanRun.id == run_id, LearningPlanRun.tenant_id == tenant_id
        )
    )
    if run is None:
        raise LearningError("NOT_FOUND", "Learning plan run not found")
    _source, _graph, current_input, _ = await _compute_current_hashes(
        db,
        tenant_id=tenant_id,
        student_id=run.student_id,
        curriculum_id=run.curriculum_id,
    )
    is_stale = current_input != run.input_hash
    return await _serialize_plan_run(
        db, tenant_id=tenant_id, run=run, is_stale=is_stale
    )


async def get_learning_workspace(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    student = await _get_student(db, tenant_id=tenant_id, student_id=student_id)
    available = await _available_curricula(
        db, tenant_id=tenant_id, student_id=student_id
    )
    mat = await materialization_status_for_student(
        db, tenant_id=tenant_id, student_id=student_id
    )

    selected_id: uuid.UUID | None = curriculum_id
    if selected_id is not None:
        await _get_curriculum(db, tenant_id=tenant_id, curriculum_id=selected_id)
    elif len(available) == 1:
        selected_id = uuid.UUID(str(available[0]["id"]))
    else:
        selected_id = None

    latest_run = None
    latest_plan = None
    is_stale = False
    latest_blueprint = None
    evidence_coverage = {
        "evidence_count": 0,
        "node_count": 0,
        "evidence_row_count": 0,
        "curriculum_node_count": 0,
    }
    selected_curriculum: dict[str, Any] | None = None

    if selected_id is not None:
        match = next(
            (row for row in available if str(row["id"]) == str(selected_id)),
            None,
        )
        if match is not None:
            selected_curriculum = {
                "id": str(match["id"]),
                "code": match["code"],
                "name": match["name"],
            }
        else:
            curriculum = await _get_curriculum(
                db, tenant_id=tenant_id, curriculum_id=selected_id
            )
            selected_curriculum = {
                "id": str(curriculum.id),
                "code": curriculum.code,
                "name": curriculum.name,
            }
        facts = await _load_evidence_facts(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            curriculum_id=selected_id,
        )
        node_count = len({f.curriculum_node_id for f in facts})
        evidence_coverage = {
            "evidence_count": len(facts),
            "node_count": node_count,
            "evidence_row_count": len(facts),
            "curriculum_node_count": node_count,
        }
        run = await db.scalar(
            select(LearningPlanRun)
            .where(
                LearningPlanRun.tenant_id == tenant_id,
                LearningPlanRun.student_id == student_id,
                LearningPlanRun.curriculum_id == selected_id,
                LearningPlanRun.status.in_(("QUEUED", "RUNNING", "READY", "FAILED")),
            )
            .order_by(LearningPlanRun.version_number.desc())
            .limit(1)
        )
        if run is not None:
            _s, _g, current_input, _ = await _compute_current_hashes(
                db,
                tenant_id=tenant_id,
                student_id=student_id,
                curriculum_id=selected_id,
            )
            is_stale = current_input != run.input_hash
            latest_plan = await _serialize_plan_run(
                db, tenant_id=tenant_id, run=run, is_stale=is_stale
            )
            latest_run = {
                "id": str(run.id),
                "version_number": run.version_number,
                "status": run.status,
                "input_hash": run.input_hash,
                "is_stale": is_stale,
            }
            bp = await db.scalar(
                select(ImprovementAssessment)
                .where(
                    ImprovementAssessment.tenant_id == tenant_id,
                    ImprovementAssessment.learning_plan_run_id == run.id,
                )
                .order_by(ImprovementAssessment.version_number.desc())
                .limit(1)
            )
            if bp is not None:
                latest_blueprint = {
                    "id": str(bp.id),
                    "version_number": bp.version_number,
                    "status": bp.status,
                    "title": bp.title,
                }

    display = (
        getattr(student, "full_name", None)
        or getattr(student, "display_name", None)
        or str(student.id)
    )
    return {
        "student": {"id": str(student.id), "display_name": display},
        "available_curricula": available,
        "selected_curriculum_id": str(selected_id) if selected_id else None,
        "selected_curriculum": selected_curriculum,
        "materialization_status": mat.get("materialization_status"),
        "materialization": mat,
        "evidence_coverage": evidence_coverage,
        "latest_run": latest_run,
        "latest_plan": latest_plan,
        "is_stale": is_stale,
        "latest_improvement_blueprint": latest_blueprint,
        "selection_required": selected_id is None and len(available) > 1,
    }


def _template_for_recommendation(kind: str) -> tuple[str, str]:
    template_kind = TEMPLATE_KIND_BY_RECOMMENDATION[kind]
    return template_kind, TEMPLATE_REF_BY_KIND[template_kind]


async def prepare_improvement_blueprint(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    generated_by: uuid.UUID,
) -> ImprovementAssessment:
    run = await db.scalar(
        select(LearningPlanRun).where(
            LearningPlanRun.id == run_id, LearningPlanRun.tenant_id == tenant_id
        )
    )
    if run is None:
        raise LearningError("NOT_FOUND", "Learning plan run not found")
    if run.status != "READY":
        raise LearningError(
            "LEARNING_PLAN_NOT_READY",
            "Improvement blueprint requires a READY learning plan",
        )

    _s, _g, current_input, _ = await _compute_current_hashes(
        db,
        tenant_id=tenant_id,
        student_id=run.student_id,
        curriculum_id=run.curriculum_id,
    )
    if current_input != run.input_hash:
        raise LearningError(
            "LEARNING_BLUEPRINT_STALE",
            "Learning plan is stale; regenerate before creating a blueprint",
        )

    active = list(
        (
            await db.scalars(
                select(LearningRecommendation).where(
                    LearningRecommendation.tenant_id == tenant_id,
                    LearningRecommendation.learning_plan_run_id == run.id,
                    LearningRecommendation.status == "ACTIVE",
                )
            )
        ).all()
    )
    if not active:
        raise LearningError(
            "LEARNING_NO_TARGETS",
            "No evidence-backed targets are available for an improvement blueprint",
        )

    # Idempotent reuse for same run+input while in-flight or pending
    existing = await db.scalar(
        select(ImprovementAssessment).where(
            ImprovementAssessment.tenant_id == tenant_id,
            ImprovementAssessment.learning_plan_run_id == run.id,
            ImprovementAssessment.input_hash == run.input_hash,
            ImprovementAssessment.status.in_(
                ("DRAFT", "GENERATING", "PENDING_APPROVAL", "APPROVED")
            ),
        )
    )
    if existing is not None:
        return existing

    max_version = await db.scalar(
        select(func.max(ImprovementAssessment.version_number)).where(
            ImprovementAssessment.tenant_id == tenant_id,
            ImprovementAssessment.learning_plan_run_id == run.id,
        )
    )
    version = int(max_version or 0) + 1
    curriculum = await _get_curriculum(
        db, tenant_id=tenant_id, curriculum_id=run.curriculum_id
    )
    bp = ImprovementAssessment(
        tenant_id=tenant_id,
        student_id=run.student_id,
        curriculum_id=run.curriculum_id,
        learning_plan_run_id=run.id,
        version_number=version,
        title=f"Improvement blueprint — {curriculum.name}",
        status="DRAFT",
        source_evidence_hash=run.source_evidence_hash,
        curriculum_graph_hash=run.curriculum_graph_hash,
        input_hash=run.input_hash,
        generated_by=generated_by,
    )
    db.add(bp)
    await db.flush()
    return bp


async def run_blueprint_pipeline(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    blueprint_id: uuid.UUID,
    storage: ObjectStorage | None = None,
) -> None:
    bp = await db.scalar(
        select(ImprovementAssessment).where(
            ImprovementAssessment.id == blueprint_id,
            ImprovementAssessment.tenant_id == tenant_id,
        )
    )
    if bp is None:
        raise LearningError("NOT_FOUND", "Improvement assessment not found")
    if bp.status in {"PENDING_APPROVAL", "APPROVED"}:
        return

    bp.status = "GENERATING"
    await db.flush()

    try:
        run = await db.scalar(
            select(LearningPlanRun).where(
                LearningPlanRun.id == bp.learning_plan_run_id,
                LearningPlanRun.tenant_id == tenant_id,
            )
        )
        if run is None or run.status != "READY":
            raise LearningError(
                "LEARNING_PLAN_NOT_READY", "Source learning plan is not READY"
            )
        _s, _g, current_input, _ = await _compute_current_hashes(
            db,
            tenant_id=tenant_id,
            student_id=run.student_id,
            curriculum_id=run.curriculum_id,
        )
        if current_input != run.input_hash or current_input != bp.input_hash:
            raise LearningError(
                "LEARNING_BLUEPRINT_STALE",
                "Learning evidence changed; regenerate plan and blueprint",
            )

        recs = list(
            (
                await db.scalars(
                    select(LearningRecommendation)
                    .where(
                        LearningRecommendation.tenant_id == tenant_id,
                        LearningRecommendation.learning_plan_run_id == run.id,
                        LearningRecommendation.status == "ACTIVE",
                    )
                    .order_by(
                        LearningRecommendation.priority,
                        LearningRecommendation.target_node_code_snapshot,
                    )
                )
            ).all()
        )
        if not recs:
            raise LearningError("LEARNING_NO_TARGETS", "No active recommendations")
        if len(recs) > MAX_BLUEPRINT_ITEMS:
            raise LearningError(
                "LEARNING_BLUEPRINT_TOO_LARGE",
                f"Plan exceeds max blueprint items ({MAX_BLUEPRINT_ITEMS})",
            )

        student = await _get_student(
            db, tenant_id=tenant_id, student_id=bp.student_id
        )
        curriculum = await _get_curriculum(
            db, tenant_id=tenant_id, curriculum_id=bp.curriculum_id
        )

        item_contexts: list[ImprovementBlueprintItemContext] = []
        for idx, rec in enumerate(recs, start=1):
            template_kind, template_ref = _template_for_recommendation(
                rec.recommendation_kind
            )
            item_contexts.append(
                ImprovementBlueprintItemContext(
                    item_key=f"item-{idx}",
                    learning_recommendation_id=rec.id,
                    curriculum_node_id=rec.target_node_id,
                    node_code=rec.target_node_code_snapshot,
                    node_title=rec.target_node_title_snapshot,
                    recommendation_kind=cast(
                        Literal[
                            "PREREQUISITE_REPAIR",
                            "TARGET_CONCEPT",
                            "PROCEDURE_PRACTICE",
                            "EXECUTION_PRACTICE",
                        ],
                        rec.recommendation_kind,
                    ),
                    priority=cast(Literal[1, 2, 3], rec.priority),
                    template_kind=cast(
                        Literal[
                            "CONCEPT_CHECK",
                            "PREREQUISITE_CHECK",
                            "PROCEDURE_PRACTICE",
                            "EXECUTION_PRACTICE",
                            "TRANSFER_CHECK",
                        ],
                        template_kind,
                    ),
                    question_template_ref=template_ref,
                    default_focus=(
                        f"Target {rec.target_node_title_snapshot} "
                        f"({rec.recommendation_kind})"
                    )[:MAX_RATIONALE_LEN],
                    difficulty="MEDIUM",
                )
            )

        ai_input = ImprovementBlueprintAIInput(
            student_display_name=getattr(student, "full_name", None)
            or str(student.id),
            curriculum_name=curriculum.name,
            title=bp.title,
            items=item_contexts,
        )
        focus_by_key = {c.item_key: c.default_focus for c in item_contexts}
        title = bp.title
        generation_source = "RULES_FALLBACK"
        provider_name: str | None = None

        provider = get_learning_provider()
        if provider is not None:
            started = _utcnow()
            try:
                result = await provider.generate_improvement_blueprint(ai_input)
                reject_provider_urls(result.title)
                if result.title:
                    title = result.title[:255]
                for prose in result.item_prose:
                    reject_provider_urls(prose.focus)
                    if prose.item_key in focus_by_key:
                        focus_by_key[prose.item_key] = prose.focus[:MAX_RATIONALE_LEN]
                generation_source = (
                    "FIXED" if provider.provider_name == "fixed" else "AI"
                )
                provider_name = provider.provider_name
                await record_ai_execution(
                    db,
                    tenant_id=tenant_id,
                    operation="generate_improvement_blueprint",
                    provider=provider.provider_name,
                    status="SUCCEEDED",
                    request_summary=redacted_request_summary(
                        operation="generate_improvement_blueprint",
                        entity_ids={
                            "improvement_assessment_id": str(bp.id),
                            "learning_plan_run_id": str(run.id),
                        },
                    ),
                    response_summary={"item_count": len(result.item_prose)},
                    learning_plan_run_id=run.id,
                    improvement_assessment_id=bp.id,
                    input_hash=canonical_input_hash(ai_input.model_dump(mode="json")),
                    started_at=started,
                    finished_at=_utcnow(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("blueprint provider failed; rules fallback: %s", exc)
                generation_source = "RULES_FALLBACK"

        # Priority-1 coverage guarantee
        priority1_ids = {r.id for r in recs if r.priority == 1}
        covered: set[uuid.UUID] = set()

        for idx, ctx in enumerate(item_contexts, start=1):
            focus = focus_by_key[ctx.item_key]
            reject_provider_urls(focus, ctx.question_template_ref)
            if "://" in ctx.question_template_ref or ctx.question_template_ref.startswith(
                "www."
            ):
                raise LearningError(
                    "LEARNING_PROVIDER_URL_REJECTED",
                    "question_template_ref must be an internal template ref",
                )
            item = ImprovementAssessmentItem(
                tenant_id=tenant_id,
                improvement_assessment_id=bp.id,
                learning_recommendation_id=ctx.learning_recommendation_id,
                curriculum_node_id=ctx.curriculum_node_id,
                item_code=f"IB-{bp.version_number:02d}-{idx:02d}",
                template_kind=ctx.template_kind,
                question_template_ref=ctx.question_template_ref,
                focus=focus,
                difficulty=ctx.difficulty,
                suggested_marks=None,
                sort_order=idx,
            )
            db.add(item)
            covered.add(ctx.learning_recommendation_id)

        missing = priority1_ids - covered
        if missing:
            raise LearningError(
                "LEARNING_BLUEPRINT_COVERAGE",
                "Blueprint must cover every Priority-1 recommendation",
            )

        await db.flush()
        items = list(
            (
                await db.scalars(
                    select(ImprovementAssessmentItem)
                    .where(
                        ImprovementAssessmentItem.improvement_assessment_id == bp.id
                    )
                    .order_by(ImprovementAssessmentItem.sort_order)
                )
            ).all()
        )
        artifact = {
            "schema": "improvement-assessment-blueprint",
            "algorithm_version": ALGORITHM_VERSION,
            "improvement_assessment_id": str(bp.id),
            "learning_plan_run_id": str(run.id),
            "student_id": str(bp.student_id),
            "curriculum_id": str(bp.curriculum_id),
            "version_number": bp.version_number,
            "title": title,
            "source_evidence_hash": bp.source_evidence_hash,
            "curriculum_graph_hash": bp.curriculum_graph_hash,
            "input_hash": bp.input_hash,
            "generation_source": generation_source,
            "items": [
                {
                    "item_code": i.item_code,
                    "learning_recommendation_id": str(i.learning_recommendation_id),
                    "curriculum_node_id": str(i.curriculum_node_id),
                    "template_kind": i.template_kind,
                    "question_template_ref": i.question_template_ref,
                    "focus": i.focus,
                    "difficulty": i.difficulty,
                    "suggested_marks": (
                        float(i.suggested_marks)
                        if i.suggested_marks is not None
                        else None
                    ),
                    "sort_order": i.sort_order,
                }
                for i in items
            ],
        }
        body = json.dumps(
            artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        key = learning_blueprint_export_key(
            tenant_id, bp.student_id, bp.curriculum_id, bp.version_number
        )
        store = storage or ObjectStorage()
        store.put_export_bytes(key=key, body=body, content_type="application/json")

        bp.title = title
        bp.status = "PENDING_APPROVAL"
        bp.generation_source = generation_source
        bp.provider = provider_name
        bp.blueprint_storage_key = key
        bp.blueprint_sha256 = digest
        bp.blueprint_byte_size = len(body)
        bp.generated_at = _utcnow()
        bp.updated_at = _utcnow()
        await db.commit()
    except LearningError as exc:
        await db.rollback()
        bp = await db.scalar(
            select(ImprovementAssessment).where(ImprovementAssessment.id == blueprint_id)
        )
        if bp is not None:
            bp.status = "FAILED"
            bp.failure_code = exc.code
            bp.failure_detail = exc.message[:500]
            bp.updated_at = _utcnow()
            await db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        bp = await db.scalar(
            select(ImprovementAssessment).where(ImprovementAssessment.id == blueprint_id)
        )
        if bp is not None:
            bp.status = "FAILED"
            bp.failure_code = "LEARNING_BLUEPRINT_FAILED"
            bp.failure_detail = str(exc)[:500]
            bp.updated_at = _utcnow()
            await db.commit()
        raise


async def get_improvement_assessment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    blueprint_id: uuid.UUID,
) -> dict[str, Any]:
    bp = await db.scalar(
        select(ImprovementAssessment).where(
            ImprovementAssessment.id == blueprint_id,
            ImprovementAssessment.tenant_id == tenant_id,
        )
    )
    if bp is None:
        raise LearningError("NOT_FOUND", "Improvement assessment not found")
    items = list(
        (
            await db.scalars(
                select(ImprovementAssessmentItem)
                .where(
                    ImprovementAssessmentItem.improvement_assessment_id == bp.id,
                    ImprovementAssessmentItem.tenant_id == tenant_id,
                )
                .order_by(ImprovementAssessmentItem.sort_order)
            )
        ).all()
    )
    return {
        "id": str(bp.id),
        "student_id": str(bp.student_id),
        "curriculum_id": str(bp.curriculum_id),
        "learning_plan_run_id": str(bp.learning_plan_run_id),
        "version_number": bp.version_number,
        "title": bp.title,
        "status": bp.status,
        "source_evidence_hash": bp.source_evidence_hash,
        "curriculum_graph_hash": bp.curriculum_graph_hash,
        "input_hash": bp.input_hash,
        "generation_source": bp.generation_source,
        "provider": bp.provider,
        "model": bp.model,
        "blueprint_storage_key": bp.blueprint_storage_key,
        "blueprint_sha256": bp.blueprint_sha256,
        "blueprint_byte_size": bp.blueprint_byte_size,
        "generated_at": bp.generated_at.isoformat() if bp.generated_at else None,
        "approved_at": bp.approved_at.isoformat() if bp.approved_at else None,
        "rejected_at": bp.rejected_at.isoformat() if bp.rejected_at else None,
        "rejection_reason": bp.rejection_reason,
        "failure_code": bp.failure_code,
        "failure_detail": bp.failure_detail,
        "items": [
            {
                "id": str(i.id),
                "learning_recommendation_id": str(i.learning_recommendation_id),
                "curriculum_node_id": str(i.curriculum_node_id),
                "item_code": i.item_code,
                "template_kind": i.template_kind,
                "question_template_ref": i.question_template_ref,
                "focus": i.focus,
                "difficulty": i.difficulty,
                "suggested_marks": (
                    float(i.suggested_marks) if i.suggested_marks is not None else None
                ),
                "sort_order": i.sort_order,
            }
            for i in items
        ],
    }


async def approve_blueprint(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    blueprint_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    storage: ObjectStorage | None = None,
) -> dict[str, Any]:
    bp = await db.scalar(
        select(ImprovementAssessment).where(
            ImprovementAssessment.id == blueprint_id,
            ImprovementAssessment.tenant_id == tenant_id,
        )
    )
    if bp is None:
        raise LearningError("NOT_FOUND", "Improvement assessment not found")
    if bp.status != "PENDING_APPROVAL":
        raise LearningError(
            "LEARNING_BLUEPRINT_NOT_PENDING",
            "Only PENDING_APPROVAL blueprints can be approved",
        )

    run = await db.scalar(
        select(LearningPlanRun).where(
            LearningPlanRun.id == bp.learning_plan_run_id,
            LearningPlanRun.tenant_id == tenant_id,
        )
    )
    if run is None or run.status != "READY":
        raise LearningError(
            "LEARNING_PLAN_NOT_READY", "Source learning plan must be READY"
        )

    _s, _g, current_input, _ = await _compute_current_hashes(
        db,
        tenant_id=tenant_id,
        student_id=bp.student_id,
        curriculum_id=bp.curriculum_id,
    )
    if current_input != bp.input_hash or current_input != run.input_hash:
        raise LearningError(
            "LEARNING_BLUEPRINT_STALE",
            "Blueprint is stale relative to current learning evidence",
        )

    if not bp.blueprint_storage_key or not bp.blueprint_sha256:
        raise LearningError(
            "LEARNING_BLUEPRINT_ARTIFACT_MISSING", "Blueprint artifact is missing"
        )
    store = storage or ObjectStorage()
    data = store.get_bytes(bp.blueprint_storage_key)
    digest = hashlib.sha256(data).hexdigest()
    if digest != bp.blueprint_sha256 or len(data) != (bp.blueprint_byte_size or -1):
        raise LearningError(
            "LEARNING_BLUEPRINT_ARTIFACT_CORRUPT",
            "Blueprint artifact hash/size mismatch",
        )

    items = list(
        (
            await db.scalars(
                select(ImprovementAssessmentItem).where(
                    ImprovementAssessmentItem.improvement_assessment_id == bp.id
                )
            )
        ).all()
    )
    for item in items:
        node = await db.scalar(
            select(CurriculumNode).where(
                CurriculumNode.id == item.curriculum_node_id,
                CurriculumNode.tenant_id == tenant_id,
                CurriculumNode.curriculum_id == bp.curriculum_id,
            )
        )
        if node is None:
            raise LearningError(
                "LEARNING_BLUEPRINT_FOREIGN_NODE",
                "Blueprint item node is not in the selected curriculum",
            )

    bp.status = "APPROVED"
    bp.approved_by = actor_user_id
    bp.approved_at = _utcnow()
    bp.updated_at = _utcnow()
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="ImprovementAssessment",
            entity_id=bp.id,
            action="APPROVE_BLUEPRINT",
            payload_json={"status": "APPROVED"},
        )
    )
    # Explicitly do NOT create Assessment / Question / etc.
    await db.flush()
    return await get_improvement_assessment(
        db, tenant_id=tenant_id, blueprint_id=bp.id
    )


async def reject_blueprint(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    blueprint_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str,
) -> dict[str, Any]:
    reason = (reason or "").strip()
    if not reason or len(reason) > 2000:
        raise LearningError(
            "INVALID_REJECTION_REASON",
            "Rejection reason is required (1..2000 characters)",
        )
    bp = await db.scalar(
        select(ImprovementAssessment).where(
            ImprovementAssessment.id == blueprint_id,
            ImprovementAssessment.tenant_id == tenant_id,
        )
    )
    if bp is None:
        raise LearningError("NOT_FOUND", "Improvement assessment not found")
    if bp.status != "PENDING_APPROVAL":
        raise LearningError(
            "LEARNING_BLUEPRINT_NOT_PENDING",
            "Only PENDING_APPROVAL blueprints can be rejected",
        )
    bp.status = "REJECTED"
    bp.rejected_by = actor_user_id
    bp.rejected_at = _utcnow()
    bp.rejection_reason = reason
    bp.updated_at = _utcnow()
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="ImprovementAssessment",
            entity_id=bp.id,
            action="REJECT_BLUEPRINT",
            payload_json={"reason": reason[:200]},
        )
    )
    await db.flush()
    return await get_improvement_assessment(
        db, tenant_id=tenant_id, blueprint_id=bp.id
    )


async def count_assessments_for_tenant(
    db: AsyncSession, *, tenant_id: uuid.UUID
) -> int:
    """Helper for tests asserting no reassessment creation."""
    return int(
        await db.scalar(
            select(func.count()).select_from(Assessment).where(Assessment.tenant_id == tenant_id)
        )
        or 0
    )
