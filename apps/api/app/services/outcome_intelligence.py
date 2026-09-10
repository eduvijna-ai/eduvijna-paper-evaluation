"""B18 answer clustering and CO/PO outcome reporting (PEV-050/051).

Does not mutate QuestionEvaluation, ReviewAction, PublishedResult, Rubric,
or mastery. Cluster reviews are advisory QA observations only.
ACTIVE mapping sets are immutable; changes require a new version.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import get_embedding_provider
from app.ai.types import EmbeddingInput
from app.db.models import (
    AnswerCluster,
    AnswerClusterMember,
    AnswerClusterReview,
    AnswerClusterRun,
    AnswerRegionTranscription,
    AssessmentVersion,
    OutcomeAttainmentMetric,
    OutcomeAttainmentReportRun,
    OutcomeDefinition,
    OutcomeMappingSet,
    PublishedResult,
    Question,
    QuestionEvaluation,
    QuestionOutcomeMapping,
    QuestionVersion,
    ReviewAction,
    RubricVersion,
)
from app.db.models.outcome_intelligence import (
    ALGORITHM_COSINE_GRAPH_V1,
    ALGORITHM_MARKS_WEIGHTED_V1,
    DEFAULT_SIMILARITY_THRESHOLD,
)
from app.services.audit import add_audit_event
from app.services.cluster_math import connected_components

MIN_CLUSTER_COHORT_SIZE = 2
ELIGIBLE_WORKFLOW_STATES = frozenset({"ACCEPTED", "OVERRIDDEN"})
WEIGHT_QUANTUM = Decimal("0.0001")


class OutcomeIntelligenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _dec(value: Decimal | float | int | str | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)))


def _as_decimal(value: float | Decimal | int | str) -> Decimal:
    return Decimal(str(value))


def _normalize_weight(weight: Decimal) -> Decimal:
    return _as_decimal(weight).quantize(WEIGHT_QUANTUM)


def _stable_json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compute_mapping_activation_hash(
    *,
    tenant_id: uuid.UUID,
    assessment_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    mapping_set_id: uuid.UUID,
    version_number: int,
    mappings: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID, Decimal]],
) -> str:
    """Deterministic SHA-256 for an activated mapping set (order-independent).

    Canonical line format (migration-safe; not JSON):
      tenant_id=<uuid>
      assessment_id=<uuid>
      assessment_version_id=<uuid>
      mapping_set_id=<uuid>
      version_number=<int>
      mapping=<question_id>|<question_version_id>|<outcome_id>|<weight>
    Mappings are sorted lexicographically by the mapping line.
    Weights are quantized to 4 decimal places.
    """
    lines = [
        f"tenant_id={tenant_id}",
        f"assessment_id={assessment_id}",
        f"assessment_version_id={assessment_version_id}",
        f"mapping_set_id={mapping_set_id}",
        f"version_number={int(version_number)}",
    ]
    mapping_lines = [
        f"mapping={question_id}|{question_version_id}|{outcome_id}|{_normalize_weight(weight)}"
        for question_id, question_version_id, outcome_id, weight in mappings
    ]
    mapping_lines.sort()
    lines.extend(mapping_lines)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def serialize_cluster_run(run: AnswerClusterRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "assessment_id": str(run.assessment_id),
        "assessment_version_id": str(run.assessment_version_id),
        "question_id": str(run.question_id),
        "question_version_id": str(run.question_version_id),
        "cohort_definition": run.cohort_definition or {},
        "algorithm_version": run.algorithm_version,
        "similarity_threshold": _dec(run.similarity_threshold),
        "source_set_hash": run.source_set_hash,
        "source_result_count": run.source_result_count,
        "source_published_result_ids": [str(x) for x in (run.source_published_result_ids or [])],
        "embedding_provider": run.embedding_provider,
        "embedding_model": run.embedding_model,
        "embedding_model_version": run.embedding_model_version,
        "embedding_dim": run.embedding_dim,
        "cluster_count": run.cluster_count,
        "status": run.status,
        "requested_by": str(run.requested_by) if run.requested_by else None,
        "requested_at": run.requested_at.isoformat() if run.requested_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "failure_code": run.failure_code,
        "failure_detail": run.failure_detail,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def serialize_cluster(cluster: AnswerCluster) -> dict[str, Any]:
    return {
        "id": str(cluster.id),
        "run_id": str(cluster.run_id),
        "cluster_index": cluster.cluster_index,
        "member_count": cluster.member_count,
        "label": cluster.label,
        "created_at": cluster.created_at.isoformat() if cluster.created_at else None,
    }


def serialize_cluster_member(member: AnswerClusterMember) -> dict[str, Any]:
    return {
        "id": str(member.id),
        "run_id": str(member.run_id),
        "cluster_id": str(member.cluster_id),
        "published_result_id": str(member.published_result_id),
        "evaluation_run_id": str(member.evaluation_run_id),
        "question_evaluation_id": str(member.question_evaluation_id),
        "submission_id": str(member.submission_id),
        "transcription_text": member.transcription_text,
        "transcription_hash": member.transcription_hash,
        "embedding": member.embedding or [],
        "final_human_approved_score": _dec(member.final_human_approved_score),
        "created_at": member.created_at.isoformat() if member.created_at else None,
    }


def serialize_cluster_review(review: AnswerClusterReview) -> dict[str, Any]:
    return {
        "id": str(review.id),
        "run_id": str(review.run_id),
        "cluster_id": str(review.cluster_id),
        "reviewer_user_id": str(review.reviewer_user_id),
        "observation": review.observation,
        "suggested_rubric_refinement": review.suggested_rubric_refinement,
        "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


def serialize_outcome_definition(row: OutcomeDefinition) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "outcome_type": row.outcome_type,
        "code": row.code,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "created_by": str(row.created_by) if row.created_by else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_mapping_set(
    row: OutcomeMappingSet, *, mapping_count: int | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(row.id),
        "assessment_id": str(row.assessment_id),
        "assessment_version_id": str(row.assessment_version_id),
        "version_number": row.version_number,
        "title": row.title,
        "status": row.status,
        "created_by": str(row.created_by) if row.created_by else None,
        "activated_by": str(row.activated_by) if row.activated_by else None,
        "activated_at": row.activated_at.isoformat() if row.activated_at else None,
        "retired_by": str(row.retired_by) if row.retired_by else None,
        "retired_at": row.retired_at.isoformat() if row.retired_at else None,
        "activation_hash": row.activation_hash,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if mapping_count is not None:
        payload["mapping_count"] = mapping_count
    return payload


def serialize_question_mapping(row: QuestionOutcomeMapping) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "mapping_set_id": str(row.mapping_set_id),
        "question_id": str(row.question_id),
        "question_version_id": str(row.question_version_id),
        "outcome_definition_id": str(row.outcome_definition_id),
        "weight": _dec(row.weight),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_attainment_run(run: OutcomeAttainmentReportRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "assessment_id": str(run.assessment_id),
        "assessment_version_id": str(run.assessment_version_id),
        "mapping_set_id": str(run.mapping_set_id),
        "mapping_set_version_number": run.mapping_set_version_number,
        "mapping_activation_hash": run.mapping_activation_hash,
        "cohort_definition": run.cohort_definition or {},
        "algorithm_version": run.algorithm_version,
        "source_set_hash": run.source_set_hash,
        "source_result_count": run.source_result_count,
        "source_published_result_ids": [str(x) for x in (run.source_published_result_ids or [])],
        "status": run.status,
        "requested_by": str(run.requested_by) if run.requested_by else None,
        "requested_at": run.requested_at.isoformat() if run.requested_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "failure_code": run.failure_code,
        "failure_detail": run.failure_detail,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def serialize_attainment_metric(row: OutcomeAttainmentMetric) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "report_run_id": str(row.report_run_id),
        "outcome_definition_id": str(row.outcome_definition_id),
        "outcome_type": row.outcome_type,
        "outcome_code": row.outcome_code,
        "outcome_title": row.outcome_title,
        "weighted_earned": _dec(row.weighted_earned),
        "weighted_max": _dec(row.weighted_max),
        "attainment_pct": _dec(row.attainment_pct),
        "denom_status": row.denom_status,
        "mapped_question_count": row.mapped_question_count,
        "contribution_count": row.contribution_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def _get_assessment_version(
    db: AsyncSession, *, tenant_id: uuid.UUID, assessment_version_id: uuid.UUID
) -> AssessmentVersion:
    version = await db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.tenant_id == tenant_id,
            AssessmentVersion.id == assessment_version_id,
        )
    )
    if version is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Assessment version not found")
    return version


async def _load_published_cohort(
    db: AsyncSession, *, tenant_id: uuid.UUID, assessment_version_id: uuid.UUID
) -> list[PublishedResult]:
    """Current effective PUBLISHED results only (SUPERSEDED excluded)."""
    rows = list(
        (
            await db.scalars(
                select(PublishedResult)
                .where(
                    PublishedResult.tenant_id == tenant_id,
                    PublishedResult.assessment_version_id == assessment_version_id,
                    PublishedResult.status == "PUBLISHED",
                )
                .order_by(PublishedResult.id.asc())
            )
        ).all()
    )
    by_submission: dict[uuid.UUID, PublishedResult] = {}
    for row in rows:
        by_submission[row.submission_id] = row
    return sorted(by_submission.values(), key=lambda r: str(r.id))


async def _resolve_transcription_text(
    db: AsyncSession, *, tenant_id: uuid.UUID, qe: QuestionEvaluation
) -> str:
    """Resolve transcription text for clustering.

    Priority:
    1) Inline ``text`` on transcription_refs entries
    2) AnswerRegionTranscription rows referenced by transcription_id (prefer CONFIRMED)
    3) evidence_metadata.transcription_text
    4) empty string
    """
    texts: list[str] = []
    for ref in qe.transcription_refs or []:
        if not isinstance(ref, dict):
            continue
        inline = ref.get("text")
        if isinstance(inline, str) and inline.strip():
            texts.append(inline.strip())
            continue
        tx_id = ref.get("transcription_id")
        if not tx_id:
            continue
        try:
            tid = uuid.UUID(str(tx_id))
        except ValueError:
            continue
        row = await db.scalar(
            select(AnswerRegionTranscription).where(
                AnswerRegionTranscription.tenant_id == tenant_id,
                AnswerRegionTranscription.id == tid,
            )
        )
        if row is not None and row.text and row.status != "SUPERSEDED":
            texts.append(row.text.strip())
    if texts:
        return "\n".join(texts)
    meta = qe.evidence_metadata or {}
    fallback = meta.get("transcription_text")
    if isinstance(fallback, str):
        return fallback.strip()
    return ""


# --- Clustering -------------------------------------------------------------


async def create_cluster_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    question_id: uuid.UUID,
    similarity_threshold: Decimal | float | None = None,
) -> dict[str, Any]:
    version = await _get_assessment_version(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )
    question = await db.scalar(
        select(Question).where(Question.tenant_id == tenant_id, Question.id == question_id)
    )
    if question is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Question not found")

    qv = await db.scalar(
        select(QuestionVersion).where(
            QuestionVersion.tenant_id == tenant_id,
            QuestionVersion.question_id == question_id,
            QuestionVersion.assessment_version_id == assessment_version_id,
        )
    )
    if qv is None:
        raise OutcomeIntelligenceError(
            "NOT_FOUND", "Question version not found for assessment version"
        )

    threshold = _as_decimal(
        similarity_threshold if similarity_threshold is not None else DEFAULT_SIMILARITY_THRESHOLD
    )
    if threshold <= 0 or threshold > 1:
        raise OutcomeIntelligenceError(
            "INVALID_THRESHOLD", "similarity_threshold must be in (0, 1]"
        )

    # Resolve embedding identity BEFORE idempotency lookup (B18.1 Blocker A).
    provider = get_embedding_provider()
    embedding_provider = provider.provider_name
    embedding_model = provider.model
    embedding_model_version = provider.model_version
    embedding_dim = int(getattr(provider, "embedding_dim", 32) or 32)

    published = await _load_published_cohort(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )
    run_ids = [pr.evaluation_run_id for pr in published]
    all_qes: list[QuestionEvaluation] = []
    if run_ids:
        all_qes = list(
            (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.tenant_id == tenant_id,
                        QuestionEvaluation.evaluation_run_id.in_(run_ids),
                        QuestionEvaluation.question_id == question_id,
                        QuestionEvaluation.workflow_state.in_(list(ELIGIBLE_WORKFLOW_STATES)),
                        QuestionEvaluation.final_human_approved_score.is_not(None),
                    )
                )
            ).all()
        )
    qes_by_run: dict[uuid.UUID, QuestionEvaluation] = {qe.evaluation_run_id: qe for qe in all_qes}
    eligible: list[tuple[PublishedResult, QuestionEvaluation]] = []
    for pr in published:
        qe = qes_by_run.get(pr.evaluation_run_id)
        if qe is not None:
            eligible.append((pr, qe))

    # Cohort fingerprint includes QE ids + transcription hashes for immutability.
    fingerprint_parts: list[dict[str, str]] = []
    member_payloads: list[dict[str, Any]] = []
    for pr, qe in eligible:
        text = await _resolve_transcription_text(db, tenant_id=tenant_id, qe=qe)
        th = _text_hash(text)
        fingerprint_parts.append(
            {
                "published_result_id": str(pr.id),
                "question_evaluation_id": str(qe.id),
                "transcription_hash": th,
            }
        )
        member_payloads.append(
            {
                "pr": pr,
                "qe": qe,
                "text": text,
                "transcription_hash": th,
            }
        )
    fingerprint_parts.sort(key=lambda p: (p["published_result_id"], p["question_evaluation_id"]))
    source_set_hash = _stable_json_hash(fingerprint_parts)
    source_ids = [p["published_result_id"] for p in fingerprint_parts]

    existing = await db.scalar(
        select(AnswerClusterRun).where(
            AnswerClusterRun.tenant_id == tenant_id,
            AnswerClusterRun.assessment_version_id == assessment_version_id,
            AnswerClusterRun.question_id == question_id,
            AnswerClusterRun.source_set_hash == source_set_hash,
            AnswerClusterRun.algorithm_version == ALGORITHM_COSINE_GRAPH_V1,
            AnswerClusterRun.similarity_threshold == threshold,
            AnswerClusterRun.embedding_provider == embedding_provider,
            AnswerClusterRun.embedding_model == embedding_model,
            AnswerClusterRun.embedding_model_version == embedding_model_version,
            AnswerClusterRun.embedding_dim == embedding_dim,
        )
    )
    if existing is not None:
        return serialize_cluster_run(existing)

    now = _utcnow()
    run = AnswerClusterRun(
        tenant_id=tenant_id,
        assessment_id=version.assessment_id,
        assessment_version_id=assessment_version_id,
        question_id=question_id,
        question_version_id=qv.id,
        cohort_definition={
            "scope": "assessment_version_question",
            "status_filter": ["PUBLISHED"],
            "human_final_states": sorted(ELIGIBLE_WORKFLOW_STATES),
            "exclude_superseded": True,
            "question_id": str(question_id),
        },
        algorithm_version=ALGORITHM_COSINE_GRAPH_V1,
        similarity_threshold=threshold,
        source_set_hash=source_set_hash,
        source_result_count=len(eligible),
        source_published_result_ids=source_ids,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_model_version=embedding_model_version,
        embedding_dim=embedding_dim,
        cluster_count=0,
        status="PENDING",
        requested_by=actor_user_id,
        requested_at=now,
    )
    db.add(run)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        existing = await db.scalar(
            select(AnswerClusterRun).where(
                AnswerClusterRun.tenant_id == tenant_id,
                AnswerClusterRun.assessment_version_id == assessment_version_id,
                AnswerClusterRun.question_id == question_id,
                AnswerClusterRun.source_set_hash == source_set_hash,
                AnswerClusterRun.algorithm_version == ALGORITHM_COSINE_GRAPH_V1,
                AnswerClusterRun.similarity_threshold == threshold,
                AnswerClusterRun.embedding_provider == embedding_provider,
                AnswerClusterRun.embedding_model == embedding_model,
                AnswerClusterRun.embedding_model_version == embedding_model_version,
                AnswerClusterRun.embedding_dim == embedding_dim,
            )
        )
        if run in db:
            db.expunge(run)
        if existing is not None:
            return serialize_cluster_run(existing)
        raise OutcomeIntelligenceError(
            "CLUSTER_RUN_CONFLICT", "Could not create cluster run"
        ) from exc

    if len(eligible) < MIN_CLUSTER_COHORT_SIZE:
        run.status = "INSUFFICIENT_SAMPLE"
        run.completed_at = _utcnow()
        run.failure_code = "INSUFFICIENT_SAMPLE"
        run.failure_detail = (
            f"Eligible cohort size {len(eligible)} < minimum {MIN_CLUSTER_COHORT_SIZE}"
        )
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="answer_cluster_run",
            entity_id=run.id,
            action="ANSWER_CLUSTER_RUN_INSUFFICIENT_SAMPLE",
            after=serialize_cluster_run(run),
        )
        await db.flush()
        await db.refresh(run)
        return serialize_cluster_run(run)

    texts = [m["text"] for m in member_payloads]
    embed_result = await provider.embed_texts(EmbeddingInput(texts=texts))
    if len(embed_result.vectors) != len(member_payloads):
        run.status = "FAILED"
        run.completed_at = _utcnow()
        run.failure_code = "EMBEDDING_COUNT_MISMATCH"
        run.failure_detail = "Embedding provider returned unexpected vector count"
        await db.flush()
        await db.refresh(run)
        return serialize_cluster_run(run)

    member_keys = [str(m["qe"].id) for m in member_payloads]
    components = connected_components(
        member_keys,
        embed_result.vectors,
        threshold=float(threshold),
    )
    key_to_payload = {
        str(m["qe"].id): (m, emb)
        for m, emb in zip(member_payloads, embed_result.vectors, strict=True)
    }

    for idx, component in enumerate(components):
        cluster = AnswerCluster(
            tenant_id=tenant_id,
            run_id=run.id,
            cluster_index=idx,
            member_count=len(component),
            label=f"Cluster {idx + 1}",
        )
        db.add(cluster)
        await db.flush()
        for member_key in component:
            payload, emb = key_to_payload[member_key]
            member_pr = payload["pr"]
            member_qe = payload["qe"]
            assert isinstance(member_pr, PublishedResult)
            assert isinstance(member_qe, QuestionEvaluation)
            db.add(
                AnswerClusterMember(
                    tenant_id=tenant_id,
                    run_id=run.id,
                    cluster_id=cluster.id,
                    published_result_id=member_pr.id,
                    evaluation_run_id=member_pr.evaluation_run_id,
                    question_evaluation_id=member_qe.id,
                    submission_id=member_pr.submission_id,
                    transcription_text=payload["text"],
                    transcription_hash=payload["transcription_hash"],
                    embedding=[float(x) for x in emb],
                    final_human_approved_score=member_qe.final_human_approved_score,
                )
            )

    run.cluster_count = len(components)
    run.status = "COMPLETED"
    run.completed_at = _utcnow()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="answer_cluster_run",
        entity_id=run.id,
        action="ANSWER_CLUSTER_RUN_COMPLETED",
        after=serialize_cluster_run(run),
    )
    await db.flush()
    await db.refresh(run)
    return serialize_cluster_run(run)


async def list_cluster_runs(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_version_id: uuid.UUID | None = None,
    question_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(AnswerClusterRun).where(AnswerClusterRun.tenant_id == tenant_id)
    if assessment_version_id is not None:
        stmt = stmt.where(AnswerClusterRun.assessment_version_id == assessment_version_id)
    if question_id is not None:
        stmt = stmt.where(AnswerClusterRun.question_id == question_id)
    rows = list((await db.scalars(stmt.order_by(AnswerClusterRun.requested_at.desc()))).all())
    return {"items": [serialize_cluster_run(r) for r in rows]}


async def get_cluster_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    run = await db.scalar(
        select(AnswerClusterRun).where(
            AnswerClusterRun.tenant_id == tenant_id, AnswerClusterRun.id == run_id
        )
    )
    if run is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Cluster run not found")
    return serialize_cluster_run(run)


async def list_clusters_for_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    run = await db.scalar(
        select(AnswerClusterRun).where(
            AnswerClusterRun.tenant_id == tenant_id, AnswerClusterRun.id == run_id
        )
    )
    if run is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Cluster run not found")
    rows = list(
        (
            await db.scalars(
                select(AnswerCluster)
                .where(
                    AnswerCluster.tenant_id == tenant_id,
                    AnswerCluster.run_id == run_id,
                )
                .order_by(AnswerCluster.cluster_index.asc())
            )
        ).all()
    )
    return {"items": [serialize_cluster(c) for c in rows]}


async def get_cluster_detail(
    db: AsyncSession, *, tenant_id: uuid.UUID, cluster_id: uuid.UUID
) -> dict[str, Any]:
    cluster = await db.scalar(
        select(AnswerCluster).where(
            AnswerCluster.tenant_id == tenant_id, AnswerCluster.id == cluster_id
        )
    )
    if cluster is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Cluster not found")
    members = list(
        (
            await db.scalars(
                select(AnswerClusterMember)
                .where(
                    AnswerClusterMember.tenant_id == tenant_id,
                    AnswerClusterMember.cluster_id == cluster_id,
                )
                .order_by(AnswerClusterMember.question_evaluation_id.asc())
            )
        ).all()
    )
    reviews = list(
        (
            await db.scalars(
                select(AnswerClusterReview)
                .where(
                    AnswerClusterReview.tenant_id == tenant_id,
                    AnswerClusterReview.cluster_id == cluster_id,
                )
                .order_by(AnswerClusterReview.submitted_at.asc())
            )
        ).all()
    )
    return {
        **serialize_cluster(cluster),
        "members": [serialize_cluster_member(m) for m in members],
        "reviews": [serialize_cluster_review(r) for r in reviews],
    }


async def add_cluster_review(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    cluster_id: uuid.UUID,
    observation: str,
    suggested_rubric_refinement: str | None = None,
) -> dict[str, Any]:
    """Advisory-only review. Never mutates rubric/QE/ReviewAction/PublishedResult."""
    cluster = await db.scalar(
        select(AnswerCluster).where(
            AnswerCluster.tenant_id == tenant_id, AnswerCluster.id == cluster_id
        )
    )
    if cluster is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Cluster not found")
    text = (observation or "").strip()
    if not text:
        raise OutcomeIntelligenceError("INVALID_OBSERVATION", "observation is required")

    # Snapshot ledger hashes before review for non-mutation proofs.
    members = list(
        (
            await db.scalars(
                select(AnswerClusterMember).where(
                    AnswerClusterMember.tenant_id == tenant_id,
                    AnswerClusterMember.cluster_id == cluster_id,
                )
            )
        ).all()
    )
    qe_ids = [m.question_evaluation_id for m in members]
    pre_qe_hashes = await _ledger_fingerprint(db, tenant_id=tenant_id, qe_ids=qe_ids)

    review = AnswerClusterReview(
        tenant_id=tenant_id,
        run_id=cluster.run_id,
        cluster_id=cluster.id,
        reviewer_user_id=actor_user_id,
        observation=text,
        suggested_rubric_refinement=(
            suggested_rubric_refinement.strip() if suggested_rubric_refinement else None
        ),
        submitted_at=_utcnow(),
    )
    db.add(review)
    await db.flush()

    post_qe_hashes = await _ledger_fingerprint(db, tenant_id=tenant_id, qe_ids=qe_ids)
    if pre_qe_hashes != post_qe_hashes:
        raise OutcomeIntelligenceError(
            "LEDGER_MUTATION_FORBIDDEN",
            "Cluster review must not mutate evaluation ledger",
        )

    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="answer_cluster_review",
        entity_id=review.id,
        action="ANSWER_CLUSTER_REVIEW_ADDED",
        after=serialize_cluster_review(review),
    )
    await db.refresh(review)
    return serialize_cluster_review(review)


async def _ledger_fingerprint(
    db: AsyncSession, *, tenant_id: uuid.UUID, qe_ids: list[uuid.UUID]
) -> str:
    if not qe_ids:
        return _stable_json_hash([])
    qes = list(
        (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.id.in_(qe_ids),
                )
            )
        ).all()
    )
    parts = [
        {
            "id": str(qe.id),
            "score": str(qe.final_human_approved_score),
            "workflow_state": qe.workflow_state,
            "updated_at": qe.updated_at.isoformat() if qe.updated_at else None,
        }
        for qe in sorted(qes, key=lambda x: str(x.id))
    ]
    review_count = await db.scalar(
        select(func.count())
        .select_from(ReviewAction)
        .where(
            ReviewAction.tenant_id == tenant_id,
            ReviewAction.question_evaluation_id.in_(qe_ids),
        )
    )
    rubric_count = await db.scalar(
        select(func.count()).select_from(RubricVersion).where(RubricVersion.tenant_id == tenant_id)
    )
    return _stable_json_hash(
        {"qes": parts, "review_actions": review_count, "rubric_versions": rubric_count}
    )


# --- Outcomes ---------------------------------------------------------------


async def create_outcome_definition(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    outcome_type: str,
    code: str,
    title: str,
    description: str | None = None,
) -> dict[str, Any]:
    ot = (outcome_type or "").strip().upper()
    if ot not in {"CO", "PO"}:
        raise OutcomeIntelligenceError("INVALID_OUTCOME_TYPE", "outcome_type must be CO or PO")
    c = (code or "").strip()
    t = (title or "").strip()
    if not c or not t:
        raise OutcomeIntelligenceError("INVALID_DEFINITION", "code and title are required")
    row = OutcomeDefinition(
        tenant_id=tenant_id,
        outcome_type=ot,
        code=c,
        title=t,
        description=(description.strip() if description else None),
        status="ACTIVE",
        created_by=actor_user_id,
    )
    db.add(row)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise OutcomeIntelligenceError(
            "OUTCOME_DEFINITION_CONFLICT", "Outcome code already exists"
        ) from exc
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="outcome_definition",
        entity_id=row.id,
        action="OUTCOME_DEFINITION_CREATED",
        after=serialize_outcome_definition(row),
    )
    await db.refresh(row)
    return serialize_outcome_definition(row)


async def list_outcome_definitions(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    outcome_type: str | None = None,
) -> dict[str, Any]:
    stmt = select(OutcomeDefinition).where(OutcomeDefinition.tenant_id == tenant_id)
    if outcome_type:
        stmt = stmt.where(OutcomeDefinition.outcome_type == outcome_type.upper())
    rows = list((await db.scalars(stmt.order_by(OutcomeDefinition.code.asc()))).all())
    return {"items": [serialize_outcome_definition(r) for r in rows]}


async def get_outcome_definition(
    db: AsyncSession, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
) -> dict[str, Any]:
    row = await db.scalar(
        select(OutcomeDefinition).where(
            OutcomeDefinition.tenant_id == tenant_id,
            OutcomeDefinition.id == definition_id,
        )
    )
    if row is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Outcome definition not found")
    return serialize_outcome_definition(row)


async def update_outcome_definition(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    definition_id: uuid.UUID,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    row = await db.scalar(
        select(OutcomeDefinition).where(
            OutcomeDefinition.tenant_id == tenant_id,
            OutcomeDefinition.id == definition_id,
        )
    )
    if row is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Outcome definition not found")
    if title is not None:
        t = title.strip()
        if not t:
            raise OutcomeIntelligenceError("INVALID_DEFINITION", "title is required")
        row.title = t
    if description is not None:
        row.description = description.strip() or None
    if status is not None:
        s = status.strip().upper()
        if s not in {"ACTIVE", "RETIRED"}:
            raise OutcomeIntelligenceError("INVALID_STATUS", "status must be ACTIVE or RETIRED")
        row.status = s
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="outcome_definition",
        entity_id=row.id,
        action="OUTCOME_DEFINITION_UPDATED",
        after=serialize_outcome_definition(row),
    )
    await db.refresh(row)
    return serialize_outcome_definition(row)


async def create_mapping_set(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    title: str,
) -> dict[str, Any]:
    version = await _get_assessment_version(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )
    t = (title or "").strip()
    if not t:
        raise OutcomeIntelligenceError("INVALID_MAPPING_SET", "title is required")
    max_ver = await db.scalar(
        select(func.max(OutcomeMappingSet.version_number)).where(
            OutcomeMappingSet.tenant_id == tenant_id,
            OutcomeMappingSet.assessment_version_id == assessment_version_id,
        )
    )
    next_ver = int(max_ver or 0) + 1
    row = OutcomeMappingSet(
        tenant_id=tenant_id,
        assessment_id=version.assessment_id,
        assessment_version_id=assessment_version_id,
        version_number=next_ver,
        title=t,
        status="DRAFT",
        created_by=actor_user_id,
    )
    db.add(row)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="outcome_mapping_set",
        entity_id=row.id,
        action="OUTCOME_MAPPING_SET_CREATED",
        after=serialize_mapping_set(row, mapping_count=0),
    )
    await db.refresh(row)
    return serialize_mapping_set(row, mapping_count=0)


async def list_mapping_sets(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(OutcomeMappingSet).where(OutcomeMappingSet.tenant_id == tenant_id)
    if assessment_version_id is not None:
        stmt = stmt.where(OutcomeMappingSet.assessment_version_id == assessment_version_id)
    rows = list(
        (
            await db.scalars(
                stmt.order_by(
                    OutcomeMappingSet.assessment_version_id.asc(),
                    OutcomeMappingSet.version_number.desc(),
                )
            )
        ).all()
    )
    items = []
    for row in rows:
        count = await db.scalar(
            select(func.count())
            .select_from(QuestionOutcomeMapping)
            .where(
                QuestionOutcomeMapping.tenant_id == tenant_id,
                QuestionOutcomeMapping.mapping_set_id == row.id,
            )
        )
        items.append(serialize_mapping_set(row, mapping_count=int(count or 0)))
    return {"items": items}


async def get_mapping_set(
    db: AsyncSession, *, tenant_id: uuid.UUID, mapping_set_id: uuid.UUID
) -> dict[str, Any]:
    row = await db.scalar(
        select(OutcomeMappingSet).where(
            OutcomeMappingSet.tenant_id == tenant_id,
            OutcomeMappingSet.id == mapping_set_id,
        )
    )
    if row is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Mapping set not found")
    mappings = list(
        (
            await db.scalars(
                select(QuestionOutcomeMapping)
                .where(
                    QuestionOutcomeMapping.tenant_id == tenant_id,
                    QuestionOutcomeMapping.mapping_set_id == mapping_set_id,
                )
                .order_by(QuestionOutcomeMapping.created_at.asc())
            )
        ).all()
    )
    payload = serialize_mapping_set(row, mapping_count=len(mappings))
    payload["mappings"] = [serialize_question_mapping(m) for m in mappings]
    return payload


async def add_question_mapping(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    mapping_set_id: uuid.UUID,
    question_id: uuid.UUID,
    outcome_definition_id: uuid.UUID,
    weight: Decimal | float | None = None,
) -> dict[str, Any]:
    mapping_set = await db.scalar(
        select(OutcomeMappingSet).where(
            OutcomeMappingSet.tenant_id == tenant_id,
            OutcomeMappingSet.id == mapping_set_id,
        )
    )
    if mapping_set is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Mapping set not found")
    if mapping_set.status != "DRAFT":
        raise OutcomeIntelligenceError(
            "MAPPING_SET_NOT_DRAFT",
            "Only DRAFT mapping sets can be modified",
        )
    outcome = await db.scalar(
        select(OutcomeDefinition).where(
            OutcomeDefinition.tenant_id == tenant_id,
            OutcomeDefinition.id == outcome_definition_id,
        )
    )
    if outcome is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Outcome definition not found")
    if outcome.status != "ACTIVE":
        raise OutcomeIntelligenceError(
            "OUTCOME_NOT_ACTIVE",
            "Only ACTIVE outcome definitions can be mapped",
        )
    qv = await db.scalar(
        select(QuestionVersion).where(
            QuestionVersion.tenant_id == tenant_id,
            QuestionVersion.question_id == question_id,
            QuestionVersion.assessment_version_id == mapping_set.assessment_version_id,
        )
    )
    if qv is None:
        raise OutcomeIntelligenceError(
            "NOT_FOUND", "Question version not found for assessment version"
        )
    w = _as_decimal(weight if weight is not None else Decimal("1"))
    if w <= 0 or w > 1:
        raise OutcomeIntelligenceError("INVALID_WEIGHT", "weight must satisfy 0 < weight <= 1")
    w = _normalize_weight(w)
    row = QuestionOutcomeMapping(
        tenant_id=tenant_id,
        mapping_set_id=mapping_set_id,
        question_id=question_id,
        question_version_id=qv.id,
        outcome_definition_id=outcome_definition_id,
        weight=w,
    )
    db.add(row)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise OutcomeIntelligenceError(
            "MAPPING_CONFLICT", "Question already mapped to this outcome in set"
        ) from exc
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="question_outcome_mapping",
        entity_id=row.id,
        action="QUESTION_OUTCOME_MAPPING_ADDED",
        after=serialize_question_mapping(row),
    )
    await db.refresh(row)
    return serialize_question_mapping(row)


async def remove_question_mapping(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    mapping_id: uuid.UUID,
) -> dict[str, Any]:
    row = await db.scalar(
        select(QuestionOutcomeMapping).where(
            QuestionOutcomeMapping.tenant_id == tenant_id,
            QuestionOutcomeMapping.id == mapping_id,
        )
    )
    if row is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Mapping not found")
    mapping_set = await db.scalar(
        select(OutcomeMappingSet).where(
            OutcomeMappingSet.tenant_id == tenant_id,
            OutcomeMappingSet.id == row.mapping_set_id,
        )
    )
    if mapping_set is None or mapping_set.status != "DRAFT":
        raise OutcomeIntelligenceError(
            "MAPPING_SET_NOT_DRAFT",
            "Only DRAFT mapping sets can be modified",
        )
    payload = serialize_question_mapping(row)
    await db.delete(row)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="question_outcome_mapping",
        entity_id=mapping_id,
        action="QUESTION_OUTCOME_MAPPING_REMOVED",
        before=payload,
    )
    return {"ok": True, "id": str(mapping_id)}


async def activate_mapping_set(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    mapping_set_id: uuid.UUID,
) -> dict[str, Any]:
    mapping_set = await db.scalar(
        select(OutcomeMappingSet).where(
            OutcomeMappingSet.tenant_id == tenant_id,
            OutcomeMappingSet.id == mapping_set_id,
        )
    )
    if mapping_set is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Mapping set not found")
    if mapping_set.status != "DRAFT":
        raise OutcomeIntelligenceError(
            "MAPPING_SET_NOT_DRAFT", "Only DRAFT mapping sets can be activated"
        )
    mappings = list(
        (
            await db.scalars(
                select(QuestionOutcomeMapping).where(
                    QuestionOutcomeMapping.tenant_id == tenant_id,
                    QuestionOutcomeMapping.mapping_set_id == mapping_set_id,
                )
            )
        ).all()
    )
    if len(mappings) < 1:
        raise OutcomeIntelligenceError(
            "MAPPING_SET_EMPTY", "Cannot activate a mapping set with no mappings"
        )

    outcome_ids = {m.outcome_definition_id for m in mappings}
    outcomes = list(
        (
            await db.scalars(
                select(OutcomeDefinition).where(
                    OutcomeDefinition.tenant_id == tenant_id,
                    OutcomeDefinition.id.in_(list(outcome_ids)),
                )
            )
        ).all()
    )
    outcomes_by_id = {o.id: o for o in outcomes}
    for oid in outcome_ids:
        outcome = outcomes_by_id.get(oid)
        if outcome is None or outcome.status != "ACTIVE":
            raise OutcomeIntelligenceError(
                "OUTCOME_NOT_ACTIVE",
                "All mapped outcomes must be ACTIVE at activation time",
            )

    activation_hash = compute_mapping_activation_hash(
        tenant_id=tenant_id,
        assessment_id=mapping_set.assessment_id,
        assessment_version_id=mapping_set.assessment_version_id,
        mapping_set_id=mapping_set.id,
        version_number=mapping_set.version_number,
        mappings=[
            (
                m.question_id,
                m.question_version_id,
                m.outcome_definition_id,
                _as_decimal(m.weight),
            )
            for m in mappings
        ],
    )

    # Retire any currently ACTIVE set for the same assessment version.
    active_rows = list(
        (
            await db.scalars(
                select(OutcomeMappingSet).where(
                    OutcomeMappingSet.tenant_id == tenant_id,
                    OutcomeMappingSet.assessment_version_id == mapping_set.assessment_version_id,
                    OutcomeMappingSet.status == "ACTIVE",
                )
            )
        ).all()
    )
    now = _utcnow()
    for active in active_rows:
        active.status = "RETIRED"
        active.retired_by = actor_user_id
        active.retired_at = now

    mapping_set.status = "ACTIVE"
    mapping_set.activated_by = actor_user_id
    mapping_set.activated_at = now
    mapping_set.activation_hash = activation_hash
    await db.flush()
    await db.refresh(mapping_set)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="outcome_mapping_set",
        entity_id=mapping_set.id,
        action="OUTCOME_MAPPING_SET_ACTIVATED",
        after=serialize_mapping_set(mapping_set, mapping_count=len(mappings)),
    )
    return serialize_mapping_set(mapping_set, mapping_count=len(mappings))


async def create_attainment_report(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    mapping_set_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    version = await _get_assessment_version(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )
    if mapping_set_id is not None:
        mapping_set = await db.scalar(
            select(OutcomeMappingSet).where(
                OutcomeMappingSet.tenant_id == tenant_id,
                OutcomeMappingSet.id == mapping_set_id,
                OutcomeMappingSet.assessment_version_id == assessment_version_id,
            )
        )
    else:
        mapping_set = await db.scalar(
            select(OutcomeMappingSet)
            .where(
                OutcomeMappingSet.tenant_id == tenant_id,
                OutcomeMappingSet.assessment_version_id == assessment_version_id,
                OutcomeMappingSet.status == "ACTIVE",
            )
            .order_by(OutcomeMappingSet.version_number.desc())
        )
    if mapping_set is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Mapping set not found")
    if mapping_set.status not in {"ACTIVE", "RETIRED"}:
        raise OutcomeIntelligenceError(
            "MAPPING_SET_NOT_ACTIVE",
            "Attainment reports require an ACTIVE (or historical RETIRED) mapping set",
        )

    mappings = list(
        (
            await db.scalars(
                select(QuestionOutcomeMapping).where(
                    QuestionOutcomeMapping.tenant_id == tenant_id,
                    QuestionOutcomeMapping.mapping_set_id == mapping_set.id,
                )
            )
        ).all()
    )
    if not mappings:
        raise OutcomeIntelligenceError("MAPPING_SET_EMPTY", "Mapping set has no mappings")

    published = await _load_published_cohort(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )
    run_ids = [pr.evaluation_run_id for pr in published]
    all_qes: list[QuestionEvaluation] = []
    if run_ids:
        all_qes = list(
            (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.tenant_id == tenant_id,
                        QuestionEvaluation.evaluation_run_id.in_(run_ids),
                        QuestionEvaluation.workflow_state.in_(list(ELIGIBLE_WORKFLOW_STATES)),
                        QuestionEvaluation.final_human_approved_score.is_not(None),
                    )
                )
            ).all()
        )
    qes_by_run_qid: dict[tuple[uuid.UUID, uuid.UUID], QuestionEvaluation] = {
        (qe.evaluation_run_id, qe.question_id): qe for qe in all_qes
    }

    source_ids = [str(pr.id) for pr in published]
    activation_hash = mapping_set.activation_hash
    if not activation_hash:
        # Defensive: historical sets activated before B18.1 should already be backfilled.
        activation_hash = compute_mapping_activation_hash(
            tenant_id=tenant_id,
            assessment_id=mapping_set.assessment_id,
            assessment_version_id=mapping_set.assessment_version_id,
            mapping_set_id=mapping_set.id,
            version_number=mapping_set.version_number,
            mappings=[
                (
                    m.question_id,
                    m.question_version_id,
                    m.outcome_definition_id,
                    _as_decimal(m.weight),
                )
                for m in mappings
            ],
        )
    source_set_hash = _stable_json_hash(
        {
            "published_result_ids": sorted(source_ids),
            "mapping_set_id": str(mapping_set.id),
            "mapping_set_version": mapping_set.version_number,
            "mapping_activation_hash": activation_hash,
        }
    )

    existing = await db.scalar(
        select(OutcomeAttainmentReportRun).where(
            OutcomeAttainmentReportRun.tenant_id == tenant_id,
            OutcomeAttainmentReportRun.assessment_version_id == assessment_version_id,
            OutcomeAttainmentReportRun.mapping_set_id == mapping_set.id,
            OutcomeAttainmentReportRun.source_set_hash == source_set_hash,
            OutcomeAttainmentReportRun.algorithm_version == ALGORITHM_MARKS_WEIGHTED_V1,
        )
    )
    if existing is not None:
        return await get_attainment_report(db, tenant_id=tenant_id, report_id=existing.id)

    now = _utcnow()
    report = OutcomeAttainmentReportRun(
        tenant_id=tenant_id,
        assessment_id=version.assessment_id,
        assessment_version_id=assessment_version_id,
        mapping_set_id=mapping_set.id,
        mapping_set_version_number=mapping_set.version_number,
        mapping_activation_hash=activation_hash,
        cohort_definition={
            "scope": "assessment_version",
            "status_filter": ["PUBLISHED"],
            "human_final_states": sorted(ELIGIBLE_WORKFLOW_STATES),
            "exclude_superseded": True,
            "mapping_set_id": str(mapping_set.id),
            "mapping_activation_hash": activation_hash,
        },
        algorithm_version=ALGORITHM_MARKS_WEIGHTED_V1,
        source_set_hash=source_set_hash,
        source_result_count=len(published),
        source_published_result_ids=source_ids,
        status="PENDING",
        requested_by=actor_user_id,
        requested_at=now,
    )
    db.add(report)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        db.expunge(report)
        existing = await db.scalar(
            select(OutcomeAttainmentReportRun).where(
                OutcomeAttainmentReportRun.tenant_id == tenant_id,
                OutcomeAttainmentReportRun.assessment_version_id == assessment_version_id,
                OutcomeAttainmentReportRun.mapping_set_id == mapping_set.id,
                OutcomeAttainmentReportRun.source_set_hash == source_set_hash,
                OutcomeAttainmentReportRun.algorithm_version == ALGORITHM_MARKS_WEIGHTED_V1,
            )
        )
        if existing is not None:
            return await get_attainment_report(db, tenant_id=tenant_id, report_id=existing.id)
        raise OutcomeIntelligenceError(
            "ATTAINMENT_REPORT_CONFLICT", "Could not create attainment report"
        ) from exc

    outcome_ids = {m.outcome_definition_id for m in mappings}
    outcomes = {
        o.id: o
        for o in (
            await db.scalars(
                select(OutcomeDefinition).where(
                    OutcomeDefinition.tenant_id == tenant_id,
                    OutcomeDefinition.id.in_(list(outcome_ids)),
                )
            )
        ).all()
    }

    # Accumulators per outcome.
    earned: dict[uuid.UUID, Decimal] = {oid: Decimal("0") for oid in outcome_ids}
    maximum: dict[uuid.UUID, Decimal] = {oid: Decimal("0") for oid in outcome_ids}
    contrib: dict[uuid.UUID, int] = {oid: 0 for oid in outcome_ids}
    mapped_q: dict[uuid.UUID, set[uuid.UUID]] = {oid: set() for oid in outcome_ids}

    for mapping in mappings:
        mapped_q[mapping.outcome_definition_id].add(mapping.question_id)
        weight = _as_decimal(mapping.weight)
        for pr in published:
            qe = qes_by_run_qid.get((pr.evaluation_run_id, mapping.question_id))
            if qe is None:
                continue
            score = _as_decimal(qe.final_human_approved_score or 0)
            max_mark = _as_decimal(qe.max_mark)
            earned[mapping.outcome_definition_id] += score * weight
            maximum[mapping.outcome_definition_id] += max_mark * weight
            contrib[mapping.outcome_definition_id] += 1

    for oid in sorted(outcome_ids, key=lambda x: str(x)):
        outcome = outcomes[oid]
        w_max = maximum[oid]
        w_earned = earned[oid]
        if w_max == 0:
            pct = None
            denom_status = "ZERO_DENOM"
        else:
            pct = (Decimal("100") * w_earned / w_max).quantize(Decimal("0.000001"))
            denom_status = "OK"
        db.add(
            OutcomeAttainmentMetric(
                tenant_id=tenant_id,
                report_run_id=report.id,
                outcome_definition_id=oid,
                outcome_type=outcome.outcome_type,
                outcome_code=outcome.code,
                outcome_title=outcome.title,
                weighted_earned=w_earned,
                weighted_max=w_max,
                attainment_pct=pct,
                denom_status=denom_status,
                mapped_question_count=len(mapped_q[oid]),
                contribution_count=contrib[oid],
            )
        )

    report.status = "COMPLETED"
    report.completed_at = _utcnow()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="outcome_attainment_report_run",
        entity_id=report.id,
        action="OUTCOME_ATTAINMENT_REPORT_COMPLETED",
        after=serialize_attainment_run(report),
    )
    await db.flush()
    return await get_attainment_report(db, tenant_id=tenant_id, report_id=report.id)


async def list_attainment_reports(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(OutcomeAttainmentReportRun).where(
        OutcomeAttainmentReportRun.tenant_id == tenant_id
    )
    if assessment_version_id is not None:
        stmt = stmt.where(OutcomeAttainmentReportRun.assessment_version_id == assessment_version_id)
    rows = list(
        (await db.scalars(stmt.order_by(OutcomeAttainmentReportRun.requested_at.desc()))).all()
    )
    return {"items": [serialize_attainment_run(r) for r in rows]}


async def get_attainment_report(
    db: AsyncSession, *, tenant_id: uuid.UUID, report_id: uuid.UUID
) -> dict[str, Any]:
    run = await db.scalar(
        select(OutcomeAttainmentReportRun).where(
            OutcomeAttainmentReportRun.tenant_id == tenant_id,
            OutcomeAttainmentReportRun.id == report_id,
        )
    )
    if run is None:
        raise OutcomeIntelligenceError("NOT_FOUND", "Attainment report not found")
    metrics = list(
        (
            await db.scalars(
                select(OutcomeAttainmentMetric)
                .where(
                    OutcomeAttainmentMetric.tenant_id == tenant_id,
                    OutcomeAttainmentMetric.report_run_id == report_id,
                )
                .order_by(
                    OutcomeAttainmentMetric.outcome_type.asc(),
                    OutcomeAttainmentMetric.outcome_code.asc(),
                )
            )
        ).all()
    )
    payload = serialize_attainment_run(run)
    payload["metrics"] = [serialize_attainment_metric(m) for m in metrics]
    return payload


async def export_attainment_csv(
    db: AsyncSession, *, tenant_id: uuid.UUID, report_id: uuid.UUID
) -> str:
    report = await get_attainment_report(db, tenant_id=tenant_id, report_id=report_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "report_id",
            "mapping_set_id",
            "mapping_set_version_number",
            "mapping_activation_hash",
            "source_result_count",
            "outcome_type",
            "outcome_code",
            "outcome_title",
            "weighted_earned",
            "weighted_max",
            "attainment_pct",
            "denom_status",
            "mapped_question_count",
            "contribution_count",
        ]
    )
    for m in report.get("metrics") or []:
        writer.writerow(
            [
                report["id"],
                report.get("mapping_set_id") or "",
                report.get("mapping_set_version_number") or "",
                report.get("mapping_activation_hash") or "",
                report.get("source_result_count") or "",
                m["outcome_type"],
                m["outcome_code"],
                m["outcome_title"],
                m["weighted_earned"],
                m["weighted_max"],
                m["attainment_pct"] if m["attainment_pct"] is not None else "",
                m["denom_status"],
                m["mapped_question_count"],
                m["contribution_count"],
            ]
        )
    return buf.getvalue()
