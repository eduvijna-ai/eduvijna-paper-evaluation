"""B8 analytics materialization and published-only query projections."""

from __future__ import annotations

import statistics
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Assessment,
    CurriculumNode,
    EvaluationRun,
    MasteryEvidence,
    PipelineJob,
    PublishedResult,
    Question,
    QuestionAnswerMapping,
    QuestionCurriculumMapping,
    QuestionEvaluation,
    QuestionVersion,
    Student,
)
from app.db.models.mastery import ALGORITHM_VERSION_B8_V1
from app.services.audit import add_audit_event
from app.services.mastery_derivation import (
    ALGORITHM_VERSION,
    aggregate_signal,
    derive_b8_v1_signals,
)

SCORE_DISTRIBUTION_BANDS: tuple[tuple[float, float], ...] = (
    (0.0, 20.0),
    (20.0, 40.0),
    (40.0, 60.0),
    (60.0, 80.0),
    (80.0, 100.0),
)


class AnalyticsError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _pct(score: Decimal, max_score: Decimal) -> float:
    if max_score <= 0:
        return 0.0
    return float((score / max_score) * Decimal("100"))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.mean(values))


def analytics_idempotency_key(published_result_id: uuid.UUID) -> str:
    return f"analytics:{published_result_id}:{ALGORITHM_VERSION}"


async def ensure_analytics_job(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published: PublishedResult,
) -> PipelineJob:
    """Create or reuse ANALYTICS PipelineJob inside the caller's transaction."""
    if published.status != "PUBLISHED":
        raise AnalyticsError("NOT_PUBLISHED", "Analytics requires PUBLISHED result")

    key = analytics_idempotency_key(published.id)
    existing = await db.scalar(
        select(PipelineJob).where(
            PipelineJob.tenant_id == tenant_id,
            PipelineJob.idempotency_key == key,
        )
    )
    if existing is not None:
        return existing

    job = PipelineJob(
        tenant_id=tenant_id,
        submission_id=published.submission_id,
        stage="ANALYTICS",
        status="QUEUED",
        attempt=1,
        idempotency_key=key,
    )
    db.add(job)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=None,
        entity_type="PublishedResult",
        entity_id=published.id,
        action="analytics_job_ensured",
        after={
            "pipeline_job_id": str(job.id),
            "algorithm_version": ALGORITHM_VERSION,
        },
    )
    await db.flush()
    return job


async def prepare_analytics_materialization(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
) -> tuple[PublishedResult, PipelineJob]:
    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        raise AnalyticsError("NOT_FOUND", "Published result not found")
    if published.status != "PUBLISHED":
        raise AnalyticsError("NOT_PUBLISHED", "Prepare requires PUBLISHED result")
    job = await ensure_analytics_job(db, tenant_id=tenant_id, published=published)
    if job.status in {"SUCCEEDED"}:
        return published, job
    if job.status == "FAILED":
        job.status = "QUEUED"
        job.error_code = None
        job.error_detail = None
        job.finished_at = None
        job.attempt = max(job.attempt, 1) + 1
        await db.flush()
    return published, job


async def materialize_published_result(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    job = await db.scalar(
        select(PipelineJob).where(
            PipelineJob.id == job_id,
            PipelineJob.tenant_id == tenant_id,
            PipelineJob.stage == "ANALYTICS",
        )
    )
    if job is None:
        raise AnalyticsError("NOT_FOUND", "Analytics job not found")

    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        job.status = "FAILED"
        job.error_code = "NOT_FOUND"
        job.error_detail = "Published result not found"
        job.finished_at = datetime.now(UTC)
        await db.commit()
        return

    if published.status != "PUBLISHED":
        job.status = "FAILED"
        job.error_code = "NOT_PUBLISHED"
        job.error_detail = "Source is not PUBLISHED"
        job.finished_at = datetime.now(UTC)
        await db.commit()
        return

    if job.status == "SUCCEEDED":
        return

    job.status = "RUNNING"
    job.started_at = datetime.now(UTC)
    await db.commit()

    try:
        await _insert_evidence_rows(db, tenant_id=tenant_id, published=published)
        job.status = "SUCCEEDED"
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        job.error_detail = None
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=None,
            entity_type="PublishedResult",
            entity_id=published.id,
            action="analytics_materialized",
            after={"algorithm_version": ALGORITHM_VERSION},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001 — durable failure metadata
        await db.rollback()
        job = await db.scalar(select(PipelineJob).where(PipelineJob.id == job_id))
        if job is not None:
            job.status = "FAILED"
            job.error_code = "MATERIALIZATION_FAILED"
            job.error_detail = str(exc)[:500]
            job.finished_at = datetime.now(UTC)
            await db.commit()
        raise


async def _insert_evidence_rows(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published: PublishedResult,
) -> None:
    if published.student_id is None:
        raise AnalyticsError("STUDENT_MISSING", "Published result has no student")

    run = await db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == published.evaluation_run_id,
            EvaluationRun.tenant_id == tenant_id,
        )
    )
    if run is None:
        raise AnalyticsError("EVALUATION_RUN_MISSING", "Evaluation run not found")

    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == published.assessment_id,
            Assessment.tenant_id == tenant_id,
        )
    )
    if assessment is None:
        raise AnalyticsError("ASSESSMENT_MISSING", "Assessment not found")

    qes = list(
        (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id == published.evaluation_run_id,
                )
            )
        ).all()
    )

    rows: list[dict[str, Any]] = []
    for qe in qes:
        if qe.final_human_approved_score is None:
            raise AnalyticsError(
                "FINAL_SCORE_MISSING",
                f"QuestionEvaluation {qe.id} missing final_human_approved_score",
            )
        mapping = await db.scalar(
            select(QuestionAnswerMapping).where(
                QuestionAnswerMapping.tenant_id == tenant_id,
                QuestionAnswerMapping.submission_id == published.submission_id,
                QuestionAnswerMapping.question_version_id == qe.question_version_id,
            )
        )
        is_blank = mapping is not None and mapping.disposition == "BLANK"
        signals = derive_b8_v1_signals(
            final_score=Decimal(qe.final_human_approved_score),
            max_mark=Decimal(qe.max_mark),
            error_codes=list(qe.error_codes or []),
            is_blank=is_blank,
        )

        curriculum_maps = list(
            (
                await db.scalars(
                    select(QuestionCurriculumMapping).where(
                        QuestionCurriculumMapping.tenant_id == tenant_id,
                        QuestionCurriculumMapping.question_version_id
                        == qe.question_version_id,
                    )
                )
            ).all()
        )
        # Collapse same node with multiple mapping types.
        by_node: dict[uuid.UUID, list[QuestionCurriculumMapping]] = defaultdict(list)
        for cm in curriculum_maps:
            node = await db.scalar(
                select(CurriculumNode).where(
                    CurriculumNode.id == cm.curriculum_node_id,
                    CurriculumNode.tenant_id == tenant_id,
                )
            )
            if node is None:
                continue
            if node.curriculum_id != assessment.curriculum_id:
                continue
            by_node[cm.curriculum_node_id].append(cm)

        for node_id, maps in by_node.items():
            mapping_types = sorted({m.mapping_type for m in maps})
            weights = [m.weight for m in maps if m.weight is not None]
            mapping_weight = weights[0] if len(weights) == 1 else (
                sum(weights) / len(weights) if weights else None
            )
            for evidence_type, strength in (
                ("CONCEPT", signals.concept),
                ("EXECUTION", signals.execution),
                ("PROCEDURE", signals.procedure),
            ):
                rows.append(
                    {
                        "id": uuid.uuid4(),
                        "tenant_id": tenant_id,
                        "student_id": published.student_id,
                        "curriculum_id": assessment.curriculum_id,
                        "curriculum_node_id": node_id,
                        "published_result_id": published.id,
                        "submission_id": published.submission_id,
                        "assessment_id": published.assessment_id,
                        "assessment_version_id": published.assessment_version_id,
                        "evaluation_run_id": published.evaluation_run_id,
                        "question_evaluation_id": qe.id,
                        "question_version_id": qe.question_version_id,
                        "evidence_type": evidence_type,
                        "strength": strength,
                        "score_ratio": signals.score_ratio,
                        "source_final_score": Decimal(qe.final_human_approved_score),
                        "source_max_mark": Decimal(qe.max_mark),
                        "mapping_types": mapping_types,
                        "mapping_weight": mapping_weight,
                        "academic_error_codes": list(signals.academic_error_codes),
                        "review_condition_codes": list(signals.review_condition_codes),
                        "reason_codes": list(signals.reason_codes),
                        "source_ledger_snapshot_hash": published.ledger_snapshot_hash,
                        "algorithm_version": ALGORITHM_VERSION_B8_V1,
                    }
                )

    if not rows:
        return

    stmt = pg_insert(MasteryEvidence).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        constraint="uq_mastery_evidence_idempotency"
    )
    await db.execute(stmt)
    await db.flush()


async def materialization_status_for_student(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
) -> dict[str, Any]:
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
    published_count = len(published)
    if published_count == 0:
        return {
            "published_result_count": 0,
            "materialized_result_count": 0,
            "materialization_status": "NOT_STARTED",
        }

    materialized = 0
    statuses: list[str] = []
    for pr in published:
        key = analytics_idempotency_key(pr.id)
        job = await db.scalar(
            select(PipelineJob).where(
                PipelineJob.tenant_id == tenant_id,
                PipelineJob.idempotency_key == key,
            )
        )
        evidence_count = await db.scalar(
            select(func.count())
            .select_from(MasteryEvidence)
            .where(
                MasteryEvidence.tenant_id == tenant_id,
                MasteryEvidence.published_result_id == pr.id,
            )
        )
        if job is None:
            statuses.append("NOT_STARTED")
        elif job.status == "QUEUED":
            statuses.append("QUEUED")
        elif job.status == "RUNNING":
            statuses.append("RUNNING")
        elif job.status == "FAILED":
            statuses.append("FAILED")
        elif job.status == "SUCCEEDED":
            statuses.append("READY")
            if (evidence_count or 0) >= 0:
                materialized += 1
        else:
            statuses.append("PARTIAL")

    if any(s == "FAILED" for s in statuses) and materialized < published_count:
        status = "FAILED"
    elif any(s in {"QUEUED", "RUNNING"} for s in statuses):
        status = "RUNNING" if "RUNNING" in statuses else "QUEUED"
    elif materialized == published_count and all(s == "READY" for s in statuses):
        status = "READY"
    elif materialized == 0 and all(s == "NOT_STARTED" for s in statuses):
        status = "NOT_STARTED"
    else:
        status = "PARTIAL"

    return {
        "published_result_count": published_count,
        "materialized_result_count": materialized,
        "materialization_status": status,
    }


async def get_assessment_analytics(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_id: uuid.UUID,
    pass_threshold_percent: float | None = None,
) -> dict[str, Any]:
    if pass_threshold_percent is not None and not (0 <= pass_threshold_percent <= 100):
        raise AnalyticsError("INVALID_THRESHOLD", "pass_threshold_percent must be 0..100")

    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.tenant_id == tenant_id,
        )
    )
    if assessment is None:
        raise AnalyticsError("NOT_FOUND", "Assessment not found")

    published = list(
        (
            await db.scalars(
                select(PublishedResult).where(
                    PublishedResult.tenant_id == tenant_id,
                    PublishedResult.assessment_id == assessment_id,
                    PublishedResult.status == "PUBLISHED",
                )
            )
        ).all()
    )

    percentages = [
        _pct(Decimal(p.total_score), Decimal(p.max_total_score)) for p in published
    ]
    student_ids = {p.student_id for p in published if p.student_id is not None}

    pass_rate = None
    if pass_threshold_percent is not None and percentages:
        passes = sum(1 for pct in percentages if pct >= pass_threshold_percent)
        pass_rate = passes / len(percentages)

    # Score distribution (percentage bins; last band inclusive of 100)
    bands: list[dict[str, Any]] = []
    for lower, upper in SCORE_DISTRIBUTION_BANDS:
        if upper >= 100:
            count = sum(1 for pct in percentages if lower <= pct <= 100)
        else:
            count = sum(1 for pct in percentages if lower <= pct < upper)
        bands.append(
            {
                "lower_bound": lower,
                "upper_bound": upper,
                "count": count,
            }
        )

    question_perf, academic_errors, review_errors, coverage = await _question_side(
        db, tenant_id=tenant_id, published=published, assessment=assessment
    )
    curriculum_perf = await _curriculum_performance(
        db, tenant_id=tenant_id, assessment_id=assessment_id, published=published
    )

    return {
        "assessment": {
            "id": str(assessment.id),
            "code": assessment.code,
            "title": assessment.title,
            "curriculum_id": str(assessment.curriculum_id),
            "status": assessment.status,
        },
        "class_section_id": None,
        "published_attempt_count": len(published),
        "unique_student_count": len(student_ids),
        "mean_percentage": _mean(percentages),
        "median_percentage": _median(percentages),
        "pass_threshold_percent": pass_threshold_percent,
        "pass_rate": pass_rate,
        "score_distribution": bands,
        "question_performance": question_perf,
        "error_distribution": {
            "academic": academic_errors,
            "review_conditions": review_errors,
        },
        "curriculum_performance": curriculum_perf,
        "mapped_scorable_question_count": coverage["mapped"],
        "unmapped_scorable_question_count": coverage["unmapped"],
        "mastery_coverage_ratio": coverage["ratio"],
        "source": "PUBLISHED_LEDGER",
        "as_of": datetime.now(UTC).isoformat(),
    }


async def _question_side(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published: list[PublishedResult],
    assessment: Assessment,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    # Aggregate by Question.stable_code
    by_code: dict[str, dict[str, Any]] = {}
    academic_counts: dict[str, int] = defaultdict(int)
    review_counts: dict[str, int] = defaultdict(int)

    mapped_qv: set[uuid.UUID] = set()
    unmapped_qv: set[uuid.UUID] = set()
    seen_qv: set[uuid.UUID] = set()

    for pr in published:
        qes = list(
            (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.tenant_id == tenant_id,
                        QuestionEvaluation.evaluation_run_id == pr.evaluation_run_id,
                    )
                )
            ).all()
        )
        for qe in qes:
            if qe.final_human_approved_score is None:
                continue
            qv = await db.scalar(
                select(QuestionVersion).where(QuestionVersion.id == qe.question_version_id)
            )
            if qv is None:
                continue
            question = await db.scalar(select(Question).where(Question.id == qv.question_id))
            if question is None:
                continue
            code = question.stable_code
            bucket = by_code.setdefault(
                code,
                {
                    "question_id": str(question.id),
                    "question_code": code,
                    "question_version_ids": set(),
                    "pcts": [],
                    "attempt_count": 0,
                    "blank_count": 0,
                    "full_credit_count": 0,
                    "zero_score_count": 0,
                    "error_counts": defaultdict(int),
                },
            )
            bucket["question_version_ids"].add(str(qv.id))
            pct = _pct(Decimal(qe.final_human_approved_score), Decimal(qe.max_mark))
            bucket["pcts"].append(pct)
            bucket["attempt_count"] += 1
            if Decimal(qe.final_human_approved_score) == Decimal(qe.max_mark):
                bucket["full_credit_count"] += 1
            if Decimal(qe.final_human_approved_score) == 0:
                bucket["zero_score_count"] += 1

            mapping = await db.scalar(
                select(QuestionAnswerMapping).where(
                    QuestionAnswerMapping.tenant_id == tenant_id,
                    QuestionAnswerMapping.submission_id == pr.submission_id,
                    QuestionAnswerMapping.question_version_id == qe.question_version_id,
                )
            )
            if mapping is not None and mapping.disposition == "BLANK":
                bucket["blank_count"] += 1

            for code_err in qe.error_codes or []:
                if code_err in {
                    "UNREADABLE",
                    "OCR_TRANSCRIPTION",
                    "QUESTION_MAPPING",
                    "IDENTITY_MAPPING",
                    "RUBRIC_AMBIGUITY",
                    "OTHER_REVIEW_REQUIRED",
                }:
                    review_counts[code_err] += 1
                else:
                    academic_counts[code_err] += 1
                    bucket["error_counts"][code_err] += 1

            if qv.id not in seen_qv:
                seen_qv.add(qv.id)
                cmap_count = await db.scalar(
                    select(func.count())
                    .select_from(QuestionCurriculumMapping)
                    .where(
                        QuestionCurriculumMapping.tenant_id == tenant_id,
                        QuestionCurriculumMapping.question_version_id == qv.id,
                    )
                )
                if (cmap_count or 0) > 0:
                    mapped_qv.add(qv.id)
                else:
                    unmapped_qv.add(qv.id)

    question_perf: list[dict[str, Any]] = []
    for code in sorted(by_code.keys()):
        b = by_code[code]
        common = sorted(
            b["error_counts"].items(), key=lambda kv: (-kv[1], kv[0])
        )
        question_perf.append(
            {
                "question_id": b["question_id"],
                "question_code": code,
                "question_version_ids": sorted(b["question_version_ids"]),
                "attempt_count": b["attempt_count"],
                "blank_count": b["blank_count"],
                "mean_score_percent": _mean(b["pcts"]),
                "median_score_percent": _median(b["pcts"]),
                "full_credit_count": b["full_credit_count"],
                "zero_score_count": b["zero_score_count"],
                "common_errors": [
                    {"code": c, "count": n} for c, n in common[:10]
                ],
            }
        )

    academic_errors = [
        {"code": c, "count": n, "category": "academic"}
        for c, n in sorted(academic_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    review_errors = [
        {"code": c, "count": n, "category": "review_condition"}
        for c, n in sorted(review_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    mapped = len(mapped_qv)
    unmapped = len(unmapped_qv)
    total = mapped + unmapped
    coverage = {
        "mapped": mapped,
        "unmapped": unmapped,
        "ratio": (mapped / total) if total else None,
    }
    return question_perf, academic_errors, review_errors, coverage


async def _curriculum_performance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_id: uuid.UUID,
    published: list[PublishedResult],
) -> list[dict[str, Any]]:
    if not published:
        return []
    pr_ids = [p.id for p in published]
    rows = list(
        (
            await db.scalars(
                select(MasteryEvidence).where(
                    MasteryEvidence.tenant_id == tenant_id,
                    MasteryEvidence.assessment_id == assessment_id,
                    MasteryEvidence.published_result_id.in_(pr_ids),
                    MasteryEvidence.evidence_type == "CONCEPT",
                )
            )
        ).all()
    )
    by_node: dict[uuid.UUID, list[MasteryEvidence]] = defaultdict(list)
    for r in rows:
        by_node[r.curriculum_node_id].append(r)

    out: list[dict[str, Any]] = []
    for node_id in sorted(by_node.keys(), key=str):
        node = await db.scalar(
            select(CurriculumNode).where(
                CurriculumNode.id == node_id, CurriculumNode.tenant_id == tenant_id
            )
        )
        if node is None:
            continue
        evs = by_node[node_id]
        ratios = [float(e.score_ratio) for e in evs]
        err_counts: dict[str, int] = defaultdict(int)
        for e in evs:
            for c in e.academic_error_codes or []:
                err_counts[str(c)] += 1
        # Counts across all evidence types for the node
        all_types = list(
            (
                await db.scalars(
                    select(MasteryEvidence).where(
                        MasteryEvidence.tenant_id == tenant_id,
                        MasteryEvidence.assessment_id == assessment_id,
                        MasteryEvidence.published_result_id.in_(pr_ids),
                        MasteryEvidence.curriculum_node_id == node_id,
                    )
                )
            ).all()
        )
        out.append(
            {
                "curriculum_node_id": str(node.id),
                "code": node.code,
                "title": node.name,
                "node_type": node.node_type,
                "question_count": len({str(e.question_version_id) for e in evs}),
                "evidence_count": len(all_types),
                "mean_score_ratio": _mean(ratios),
                "strong_signal_count": sum(1 for e in all_types if e.strength == "STRONG"),
                "weak_signal_count": sum(1 for e in all_types if e.strength == "WEAK"),
                "inconclusive_signal_count": sum(
                    1 for e in all_types if e.strength == "INCONCLUSIVE"
                ),
                "common_academic_errors": [
                    {"code": c, "count": n}
                    for c, n in sorted(err_counts.items(), key=lambda kv: (-kv[1], kv[0]))[
                        :10
                    ]
                ],
            }
        )
    return out


async def get_student_analytics(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
) -> dict[str, Any]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise AnalyticsError("NOT_FOUND", "Student not found")

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
    percentages = [
        _pct(Decimal(p.total_score), Decimal(p.max_total_score)) for p in published
    ]
    assessment_ids = {p.assessment_id for p in published}

    evidence = list(
        (
            await db.scalars(
                select(MasteryEvidence).where(
                    MasteryEvidence.tenant_id == tenant_id,
                    MasteryEvidence.student_id == student_id,
                )
            )
        ).all()
    )

    by_node: dict[uuid.UUID, list[MasteryEvidence]] = defaultdict(list)
    for e in evidence:
        by_node[e.curriculum_node_id].append(e)

    concept_signals: list[dict[str, Any]] = []
    for node_id in sorted(by_node.keys(), key=str):
        node = await db.scalar(
            select(CurriculumNode).where(
                CurriculumNode.id == node_id, CurriculumNode.tenant_id == tenant_id
            )
        )
        if node is None:
            continue
        node_evidence = by_node[node_id]

        def counts(etype: str, rows: list[MasteryEvidence] = node_evidence) -> dict[str, Any]:
            subset = [e for e in rows if e.evidence_type == etype]
            strong = sum(1 for e in subset if e.strength == "STRONG")
            weak = sum(1 for e in subset if e.strength == "WEAK")
            inconclusive = sum(1 for e in subset if e.strength == "INCONCLUSIVE")
            return {
                "strong_count": strong,
                "weak_count": weak,
                "inconclusive_count": inconclusive,
                "signal": aggregate_signal(strong, weak, inconclusive),
            }

        ratios = [float(e.score_ratio) for e in node_evidence if e.evidence_type == "CONCEPT"]
        concept_signals.append(
            {
                "curriculum_node_id": str(node.id),
                "code": node.code,
                "title": node.name,
                "node_type": node.node_type,
                "concept": counts("CONCEPT"),
                "execution": counts("EXECUTION"),
                "procedure": counts("PROCEDURE"),
                "evidence_count": len(node_evidence),
                "mean_score_ratio": _mean(ratios),
            }
        )

    err_counts: dict[str, int] = defaultdict(int)
    for e in evidence:
        for c in e.academic_error_codes or []:
            err_counts[str(c)] += 1
    error_distribution = [
        {"code": c, "count": n}
        for c, n in sorted(err_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    mat = await materialization_status_for_student(
        db, tenant_id=tenant_id, student_id=student_id
    )

    # Coverage: distinct nodes with evidence vs mapped questions across published
    return {
        "student": {
            "id": str(student.id),
            "display_name": student.full_name,
            "student_code": student.student_code,
            "external_ref": student.student_code,
        },
        "published_assessment_count": len(assessment_ids),
        "published_attempt_count": len(published),
        "average_percentage": _mean(percentages),
        "concept_signals": concept_signals,
        "error_distribution": error_distribution,
        "mastery_coverage": {
            "curriculum_node_count": len(by_node),
            "evidence_row_count": len(evidence),
        },
        "materialization_status": mat["materialization_status"],
        "published_result_count": mat["published_result_count"],
        "materialized_result_count": mat["materialized_result_count"],
        "source": "PUBLISHED_LEDGER",
        "as_of": datetime.now(UTC).isoformat(),
    }


async def list_student_mastery_evidence(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    assessment_id: uuid.UUID | None = None,
    curriculum_id: uuid.UUID | None = None,
    curriculum_node_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise AnalyticsError("NOT_FOUND", "Student not found")

    stmt = select(MasteryEvidence).where(
        MasteryEvidence.tenant_id == tenant_id,
        MasteryEvidence.student_id == student_id,
    )
    if assessment_id is not None:
        stmt = stmt.where(MasteryEvidence.assessment_id == assessment_id)
    if curriculum_id is not None:
        stmt = stmt.where(MasteryEvidence.curriculum_id == curriculum_id)
    if curriculum_node_id is not None:
        stmt = stmt.where(MasteryEvidence.curriculum_node_id == curriculum_node_id)
    stmt = stmt.order_by(
        MasteryEvidence.created_at.asc(), MasteryEvidence.evidence_type.asc()
    )
    rows = list((await db.scalars(stmt)).all())
    return {
        "student_id": str(student_id),
        "items": [
            {
                "id": str(r.id),
                "published_result_id": str(r.published_result_id),
                "assessment_id": str(r.assessment_id),
                "assessment_version_id": str(r.assessment_version_id),
                "submission_id": str(r.submission_id),
                "evaluation_run_id": str(r.evaluation_run_id),
                "question_evaluation_id": str(r.question_evaluation_id),
                "question_version_id": str(r.question_version_id),
                "curriculum_id": str(r.curriculum_id),
                "curriculum_node_id": str(r.curriculum_node_id),
                "evidence_type": r.evidence_type,
                "strength": r.strength,
                "score_ratio": float(r.score_ratio),
                "source_final_score": float(r.source_final_score),
                "source_max_mark": float(r.source_max_mark),
                "mapping_types": r.mapping_types or [],
                "mapping_weight": float(r.mapping_weight)
                if r.mapping_weight is not None
                else None,
                "academic_error_codes": r.academic_error_codes or [],
                "review_condition_codes": r.review_condition_codes or [],
                "reason_codes": r.reason_codes or [],
                "source_ledger_snapshot_hash": r.source_ledger_snapshot_hash,
                "algorithm_version": r.algorithm_version,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }
