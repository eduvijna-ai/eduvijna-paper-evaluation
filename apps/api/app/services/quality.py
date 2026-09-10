"""B17 assessment quality psychometrics and evaluator calibration (PEV-048/049).

Does not mutate QuestionEvaluation, ReviewAction, PublishedResult, mastery, or
grading work items. Calibration responses are isolated QA artifacts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssessmentVersion,
    CalibrationCase,
    CalibrationEvaluatorMetric,
    CalibrationParticipant,
    CalibrationResponse,
    CalibrationSession,
    CalibrationSessionMetric,
    ItemPsychometricMetric,
    PsychometricRun,
    PublishedResult,
    Question,
    QuestionEvaluation,
    User,
)
from app.db.models.quality import (
    ALGORITHM_CALIBRATION_V1,
    ALGORITHM_PSYCHOMETRICS_V1,
    DISCRIMINATION_METHOD_V1,
)
from app.services.audit import add_audit_event
from app.services.quality_stats import (
    corrected_item_total_discrimination,
    difficulty_band,
    difficulty_index,
    discrimination_band,
    icc_a1,
    mean,
    population_std,
)

MIN_PSYCHOMETRIC_COHORT_SIZE = 20
MIN_CALIBRATION_CASES = 10
ALGORITHM_PSYCH = ALGORITHM_PSYCHOMETRICS_V1
ALGORITHM_CAL = ALGORITHM_CALIBRATION_V1

ELIGIBLE_WORKFLOW_STATES = frozenset({"ACCEPTED", "OVERRIDDEN"})


class QualityError(RuntimeError):
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


def _stable_json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def serialize_psychometric_run(run: PsychometricRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "assessment_id": str(run.assessment_id),
        "assessment_version_id": str(run.assessment_version_id),
        "cohort_definition": run.cohort_definition or {},
        "algorithm_version": run.algorithm_version,
        "min_cohort_size": run.min_cohort_size,
        "source_set_hash": run.source_set_hash,
        "source_result_count": run.source_result_count,
        "source_published_result_ids": [
            str(x) for x in (run.source_published_result_ids or [])
        ],
        "status": run.status,
        "requested_by": str(run.requested_by) if run.requested_by else None,
        "requested_at": run.requested_at.isoformat() if run.requested_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "failure_code": run.failure_code,
        "failure_detail": run.failure_detail,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def serialize_item_metric(row: ItemPsychometricMetric) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "run_id": str(row.run_id),
        "question_id": str(row.question_id),
        "question_version_id": str(row.question_version_id),
        "question_code": row.question_code,
        "attempt_count": row.attempt_count,
        "max_mark": _dec(row.max_mark),
        "mean_raw_score": _dec(row.mean_raw_score),
        "std_dev": _dec(row.std_dev),
        "difficulty_index": _dec(row.difficulty_index),
        "discrimination_index": _dec(row.discrimination_index),
        "discrimination_method": row.discrimination_method,
        "discrimination_status": row.discrimination_status,
        "full_credit_rate": _dec(row.full_credit_rate),
        "zero_score_rate": _dec(row.zero_score_rate),
        "blank_rate": _dec(row.blank_rate),
        "difficulty_band": row.difficulty_band,
        "discrimination_band": row.discrimination_band,
    }


def serialize_calibration_session(
    session: CalibrationSession, *, case_count: int | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(session.id),
        "assessment_id": str(session.assessment_id),
        "assessment_version_id": str(session.assessment_version_id),
        "title": session.title,
        "status": session.status,
        "algorithm_version": session.algorithm_version,
        "score_tolerance_abs": _dec(session.score_tolerance_abs),
        "score_tolerance_pct": _dec(session.score_tolerance_pct),
        "min_cases": session.min_cases,
        "activated_by": str(session.activated_by) if session.activated_by else None,
        "activated_at": session.activated_at.isoformat() if session.activated_at else None,
        "closed_by": str(session.closed_by) if session.closed_by else None,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
        "created_by": str(session.created_by) if session.created_by else None,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }
    if case_count is not None:
        payload["case_count"] = case_count
    return payload


def serialize_calibration_case_management(case: CalibrationCase) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "session_id": str(case.session_id),
        "case_code": case.case_code,
        "published_result_id": str(case.published_result_id),
        "evaluation_run_id": str(case.evaluation_run_id),
        "question_evaluation_id": str(case.question_evaluation_id),
        "question_version_id": str(case.question_version_id),
        "rubric_version_id": str(case.rubric_version_id),
        "max_mark": _dec(case.max_mark),
        "reference_score": _dec(case.reference_score),
        "source_snapshot_hash": case.source_snapshot_hash,
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }


def serialize_calibration_case_blind(case: CalibrationCase) -> dict[str, Any]:
    """Blind view: no reference score, student identity, or source evaluator."""
    evidence = copy.deepcopy(case.evidence_snapshot or {})
    for key in (
        "student_id",
        "reviewed_by",
        "source_evaluator_id",
        "submission_id",
        "published_result_id",
        "question_evaluation_id",
    ):
        evidence.pop(key, None)
    return {
        "id": str(case.id),
        "session_id": str(case.session_id),
        "case_code": case.case_code,
        "question_version_id": str(case.question_version_id),
        "rubric_version_id": str(case.rubric_version_id),
        "max_mark": _dec(case.max_mark),
        "criterion_snapshot": case.criterion_snapshot or [],
        "evidence_snapshot": evidence,
    }


def serialize_calibration_response(row: CalibrationResponse) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "session_id": str(row.session_id),
        "case_id": str(row.case_id),
        "participant_id": str(row.participant_id),
        "user_id": str(row.user_id),
        "score": _dec(row.score),
        "max_mark": _dec(row.max_mark),
        "comment": row.comment,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
    }


def serialize_session_metric(row: CalibrationSessionMetric) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "session_id": str(row.session_id),
        "metric_name": row.metric_name,
        "algorithm_version": row.algorithm_version,
        "evaluator_count": row.evaluator_count,
        "common_case_count": row.common_case_count,
        "icc_value": _dec(row.icc_value),
        "status": row.status,
    }


def serialize_evaluator_metric(row: CalibrationEvaluatorMetric) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "session_id": str(row.session_id),
        "user_id": str(row.user_id),
        "case_count": row.case_count,
        "mean_signed_diff": _dec(row.mean_signed_diff),
        "mae": _dec(row.mae),
        "nmae": _dec(row.nmae),
        "exact_match_rate": _dec(row.exact_match_rate),
        "within_tolerance_rate": _dec(row.within_tolerance_rate),
    }


async def _get_assessment_version(
    db: AsyncSession, *, tenant_id: uuid.UUID, assessment_version_id: uuid.UUID
) -> AssessmentVersion:
    version = await db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.id == assessment_version_id,
            AssessmentVersion.tenant_id == tenant_id,
        )
    )
    if version is None:
        raise QualityError("NOT_FOUND", "Assessment version not found")
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
    # One current published result per submission (defense in depth).
    by_submission: dict[uuid.UUID, PublishedResult] = {}
    for row in rows:
        by_submission[row.submission_id] = row
    return sorted(by_submission.values(), key=lambda r: str(r.id))


async def _bulk_load_cohort_qes(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    evaluation_run_ids: list[uuid.UUID],
) -> list[QuestionEvaluation]:
    """One bounded SELECT for all human-final QEs in the cohort."""
    if not evaluation_run_ids:
        return []
    return list(
        (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id.in_(evaluation_run_ids),
                    QuestionEvaluation.workflow_state.in_(
                        list(ELIGIBLE_WORKFLOW_STATES)
                    ),
                    QuestionEvaluation.final_human_approved_score.is_not(None),
                )
            )
        ).all()
    )


async def _bulk_load_question_codes(
    db: AsyncSession, *, tenant_id: uuid.UUID, question_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """One bounded SELECT for question metadata."""
    if not question_ids:
        return {}
    rows = list(
        (
            await db.scalars(
                select(Question).where(
                    Question.tenant_id == tenant_id,
                    Question.id.in_(list(question_ids)),
                )
            )
        ).all()
    )
    return {q.id: q.stable_code for q in rows}


async def create_or_get_psychometric_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
) -> dict[str, Any]:
    version = await _get_assessment_version(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )
    published = await _load_published_cohort(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )

    # Bulk-load all human-final QEs for the cohort (constant DB round trips).
    run_ids = [pr.evaluation_run_id for pr in published]
    all_qes = await _bulk_load_cohort_qes(
        db, tenant_id=tenant_id, evaluation_run_ids=run_ids
    )
    qes_by_run: dict[uuid.UUID, list[QuestionEvaluation]] = {}
    for qe in all_qes:
        qes_by_run.setdefault(qe.evaluation_run_id, []).append(qe)

    eligible_published: list[PublishedResult] = [
        pr for pr in published if qes_by_run.get(pr.evaluation_run_id)
    ]

    source_ids = [str(pr.id) for pr in eligible_published]
    source_set_hash = _stable_json_hash(sorted(source_ids))

    existing = await db.scalar(
        select(PsychometricRun).where(
            PsychometricRun.tenant_id == tenant_id,
            PsychometricRun.assessment_version_id == assessment_version_id,
            PsychometricRun.source_set_hash == source_set_hash,
            PsychometricRun.algorithm_version == ALGORITHM_PSYCH,
        )
    )
    if existing is not None:
        return serialize_psychometric_run(existing)

    now = _utcnow()
    run = PsychometricRun(
        tenant_id=tenant_id,
        assessment_id=version.assessment_id,
        assessment_version_id=assessment_version_id,
        cohort_definition={
            "scope": "assessment_version",
            "status_filter": ["PUBLISHED"],
            "human_final_states": sorted(ELIGIBLE_WORKFLOW_STATES),
            "exclude_superseded": True,
        },
        algorithm_version=ALGORITHM_PSYCH,
        min_cohort_size=MIN_PSYCHOMETRIC_COHORT_SIZE,
        source_set_hash=source_set_hash,
        source_result_count=len(eligible_published),
        source_published_result_ids=source_ids,
        status="PENDING",
        requested_by=actor_user_id,
        requested_at=now,
    )
    db.add(run)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        db.expunge(run)
        existing = await db.scalar(
            select(PsychometricRun).where(
                PsychometricRun.tenant_id == tenant_id,
                PsychometricRun.assessment_version_id == assessment_version_id,
                PsychometricRun.source_set_hash == source_set_hash,
                PsychometricRun.algorithm_version == ALGORITHM_PSYCH,
            )
        )
        if existing is not None:
            return serialize_psychometric_run(existing)
        raise QualityError(
            "PSYCHOMETRIC_RUN_CONFLICT", "Could not create psychometric run"
        ) from exc

    if len(eligible_published) < MIN_PSYCHOMETRIC_COHORT_SIZE:
        run.status = "INSUFFICIENT_SAMPLE"
        run.completed_at = _utcnow()
        run.failure_code = "INSUFFICIENT_SAMPLE"
        run.failure_detail = (
            f"Published cohort size {len(eligible_published)} "
            f"< minimum {MIN_PSYCHOMETRIC_COHORT_SIZE}"
        )
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="psychometric_run",
            entity_id=run.id,
            action="PSYCHOMETRIC_RUN_INSUFFICIENT_SAMPLE",
            after=serialize_psychometric_run(run),
        )
        await db.flush()
        await db.refresh(run)
        return serialize_psychometric_run(run)

    # Explicit per-result × question_version matrix (aligned vectors).
    # matrix[pr_id][qv_id] = score
    matrix: dict[uuid.UUID, dict[uuid.UUID, float]] = {}
    item_meta: dict[uuid.UUID, dict[str, Any]] = {}
    question_ids: set[uuid.UUID] = set()

    for pr in eligible_published:
        by_qv: dict[uuid.UUID, float] = {}
        for qe in qes_by_run[pr.evaluation_run_id]:
            score = float(Decimal(str(qe.final_human_approved_score)))
            by_qv[qe.question_version_id] = score
            if qe.question_version_id not in item_meta:
                item_meta[qe.question_version_id] = {
                    "question_id": qe.question_id,
                    "max_mark": float(Decimal(str(qe.max_mark))),
                }
                question_ids.add(qe.question_id)
        matrix[pr.id] = by_qv

    codes = await _bulk_load_question_codes(
        db, tenant_id=tenant_id, question_ids=question_ids
    )
    for meta in item_meta.values():
        meta["question_code"] = codes.get(meta["question_id"], str(meta["question_id"]))

    ordered_pr_ids = [pr.id for pr in eligible_published]

    for qv_id, meta in item_meta.items():
        # Aligned pairs: only published results that have this item.
        paired_scores: list[float] = []
        paired_totals: list[float] = []
        for pr_id in ordered_pr_ids:
            by_qv = matrix[pr_id]
            if qv_id not in by_qv:
                continue
            score = by_qv[qv_id]
            paired_scores.append(score)
            paired_totals.append(sum(by_qv.values()))

        max_mark = float(meta["max_mark"])
        attempt_count = len(paired_scores)
        if attempt_count == 0:
            continue
        m = mean(paired_scores) or 0.0
        sd = population_std(paired_scores) or 0.0
        diff = difficulty_index(paired_scores, max_mark)
        if diff is None:
            diff = 0.0
        full_credit = (
            sum(1 for s in paired_scores if abs(s - max_mark) < 1e-9) / attempt_count
        )
        zero_rate = sum(1 for s in paired_scores if abs(s) < 1e-9) / attempt_count

        if attempt_count < 2:
            disc = None
            disc_status = "INSUFFICIENT_SAMPLE"
        else:
            disc, disc_reason = corrected_item_total_discrimination(
                paired_scores, paired_totals
            )
            if disc is None:
                disc_status = (
                    "INSUFFICIENT_SAMPLE"
                    if disc_reason == "INSUFFICIENT_PAIRS"
                    else "UNDEFINED_VARIANCE"
                )
            else:
                disc_status = "OK"

        metric = ItemPsychometricMetric(
            tenant_id=tenant_id,
            run_id=run.id,
            question_id=meta["question_id"],
            question_version_id=qv_id,
            question_code=meta["question_code"],
            attempt_count=attempt_count,
            max_mark=_as_decimal(max_mark),
            mean_raw_score=_as_decimal(m),
            std_dev=_as_decimal(sd),
            difficulty_index=_as_decimal(diff),
            discrimination_index=_as_decimal(disc) if disc is not None else None,
            discrimination_method=DISCRIMINATION_METHOD_V1,
            discrimination_status=disc_status,
            full_credit_rate=_as_decimal(full_credit),
            zero_score_rate=_as_decimal(zero_rate),
            blank_rate=None,
            difficulty_band=difficulty_band(diff),
            discrimination_band=discrimination_band(disc),
        )
        db.add(metric)

    run.status = "COMPLETED"
    run.completed_at = _utcnow()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="psychometric_run",
        entity_id=run.id,
        action="PSYCHOMETRIC_RUN_COMPLETED",
        after=serialize_psychometric_run(run),
    )
    await db.flush()
    await db.refresh(run)
    return serialize_psychometric_run(run)


async def list_psychometric_runs(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(PsychometricRun).where(PsychometricRun.tenant_id == tenant_id)
    if assessment_version_id is not None:
        stmt = stmt.where(
            PsychometricRun.assessment_version_id == assessment_version_id
        )
    rows = list(
        (await db.scalars(stmt.order_by(PsychometricRun.requested_at.desc()))).all()
    )
    return {"items": [serialize_psychometric_run(row) for row in rows]}


async def get_psychometric_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    run = await db.scalar(
        select(PsychometricRun).where(
            PsychometricRun.id == run_id,
            PsychometricRun.tenant_id == tenant_id,
        )
    )
    if run is None:
        raise QualityError("NOT_FOUND", "Psychometric run not found")
    return serialize_psychometric_run(run)


async def list_psychometric_run_items(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    await get_psychometric_run(db, tenant_id=tenant_id, run_id=run_id)
    rows = list(
        (
            await db.scalars(
                select(ItemPsychometricMetric)
                .where(
                    ItemPsychometricMetric.tenant_id == tenant_id,
                    ItemPsychometricMetric.run_id == run_id,
                )
                .order_by(ItemPsychometricMetric.question_code.asc())
            )
        ).all()
    )
    return {"items": [serialize_item_metric(row) for row in rows]}


async def get_latest_psychometric_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, assessment_version_id: uuid.UUID
) -> dict[str, Any]:
    await _get_assessment_version(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )
    run = await db.scalar(
        select(PsychometricRun)
        .where(
            PsychometricRun.tenant_id == tenant_id,
            PsychometricRun.assessment_version_id == assessment_version_id,
        )
        .order_by(PsychometricRun.requested_at.desc())
        .limit(1)
    )
    if run is None:
        raise QualityError("NOT_FOUND", "No psychometric run for assessment version")
    return serialize_psychometric_run(run)


async def _get_session(
    db: AsyncSession, *, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> CalibrationSession:
    session = await db.scalar(
        select(CalibrationSession).where(
            CalibrationSession.id == session_id,
            CalibrationSession.tenant_id == tenant_id,
        )
    )
    if session is None:
        raise QualityError("NOT_FOUND", "Calibration session not found")
    return session


async def _case_count(
    db: AsyncSession, *, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> int:
    rows = list(
        (
            await db.scalars(
                select(CalibrationCase).where(
                    CalibrationCase.tenant_id == tenant_id,
                    CalibrationCase.session_id == session_id,
                )
            )
        ).all()
    )
    return len(rows)


async def create_calibration_session(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    title: str,
    score_tolerance_abs: Decimal | None = None,
    score_tolerance_pct: Decimal | None = None,
    min_cases: int | None = None,
) -> dict[str, Any]:
    version = await _get_assessment_version(
        db, tenant_id=tenant_id, assessment_version_id=assessment_version_id
    )
    session = CalibrationSession(
        tenant_id=tenant_id,
        assessment_id=version.assessment_id,
        assessment_version_id=assessment_version_id,
        title=title.strip(),
        status="DRAFT",
        algorithm_version=ALGORITHM_CAL,
        score_tolerance_abs=score_tolerance_abs
        if score_tolerance_abs is not None
        else Decimal("0.5"),
        score_tolerance_pct=score_tolerance_pct
        if score_tolerance_pct is not None
        else Decimal("0.05"),
        min_cases=min_cases if min_cases is not None else MIN_CALIBRATION_CASES,
        created_by=actor_user_id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="calibration_session",
        entity_id=session.id,
        action="CALIBRATION_SESSION_CREATED",
        after=serialize_calibration_session(session, case_count=0),
    )
    return serialize_calibration_session(session, case_count=0)


async def list_calibration_sessions(
    db: AsyncSession, *, tenant_id: uuid.UUID
) -> dict[str, Any]:
    rows = list(
        (
            await db.scalars(
                select(CalibrationSession)
                .where(CalibrationSession.tenant_id == tenant_id)
                .order_by(CalibrationSession.created_at.desc())
            )
        ).all()
    )
    items = []
    for row in rows:
        count = await _case_count(db, tenant_id=tenant_id, session_id=row.id)
        items.append(serialize_calibration_session(row, case_count=count))
    return {"items": items}


async def get_calibration_session(
    db: AsyncSession, *, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    count = await _case_count(db, tenant_id=tenant_id, session_id=session_id)
    cases = list(
        (
            await db.scalars(
                select(CalibrationCase)
                .where(
                    CalibrationCase.tenant_id == tenant_id,
                    CalibrationCase.session_id == session_id,
                )
                .order_by(CalibrationCase.case_code.asc())
            )
        ).all()
    )
    participants = list(
        (
            await db.scalars(
                select(CalibrationParticipant).where(
                    CalibrationParticipant.tenant_id == tenant_id,
                    CalibrationParticipant.session_id == session_id,
                )
            )
        ).all()
    )
    payload = serialize_calibration_session(session, case_count=count)
    payload["cases"] = [serialize_calibration_case_management(c) for c in cases]
    payload["participants"] = [
        {"id": str(p.id), "user_id": str(p.user_id)} for p in participants
    ]
    return payload


async def add_calibration_case(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
    published_result_id: uuid.UUID,
    question_evaluation_id: uuid.UUID,
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    if session.status != "DRAFT":
        raise QualityError(
            "CALIBRATION_SESSION_NOT_DRAFT",
            "Cases can only be added while the session is DRAFT",
        )

    pr = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if pr is None or pr.status != "PUBLISHED":
        raise QualityError(
            "CALIBRATION_CASE_INELIGIBLE",
            "Published result must exist and be PUBLISHED",
        )
    if pr.assessment_version_id != session.assessment_version_id:
        raise QualityError(
            "CALIBRATION_CASE_INELIGIBLE",
            "Published result assessment version does not match session",
        )

    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == question_evaluation_id,
            QuestionEvaluation.tenant_id == tenant_id,
        )
    )
    if (
        qe is None
        or qe.evaluation_run_id != pr.evaluation_run_id
        or qe.workflow_state not in ELIGIBLE_WORKFLOW_STATES
        or qe.final_human_approved_score is None
    ):
        raise QualityError(
            "CALIBRATION_CASE_INELIGIBLE",
            "Question evaluation must be human-final on the published run",
        )

    existing = await db.scalar(
        select(CalibrationCase).where(
            CalibrationCase.tenant_id == tenant_id,
            CalibrationCase.session_id == session_id,
            CalibrationCase.question_evaluation_id == question_evaluation_id,
        )
    )
    if existing is not None:
        return serialize_calibration_case_management(existing)

    count = await _case_count(db, tenant_id=tenant_id, session_id=session_id)
    case_code = f"C{count + 1:04d}"
    evidence_snapshot = {
        "transcription_refs": copy.deepcopy(qe.transcription_refs or []),
        "evidence_metadata": copy.deepcopy(qe.evidence_metadata or {}),
        "error_codes": copy.deepcopy(qe.error_codes or []),
        "deduction_reasons": copy.deepcopy(qe.deduction_reasons or []),
        "workflow_state": qe.workflow_state,
        # Intentionally omit student_id / reviewed_by for blind safety at freeze.
    }
    source_snapshot_hash = _stable_json_hash(
        {
            "published_result_id": str(pr.id),
            "question_evaluation_id": str(qe.id),
            "reference_score": str(qe.final_human_approved_score),
            "max_mark": str(qe.max_mark),
            "criterion_snapshot": qe.criterion_snapshot or [],
            "ledger_snapshot_hash": pr.ledger_snapshot_hash,
        }
    )
    case = CalibrationCase(
        tenant_id=tenant_id,
        session_id=session_id,
        case_code=case_code,
        published_result_id=pr.id,
        evaluation_run_id=pr.evaluation_run_id,
        question_evaluation_id=qe.id,
        question_version_id=qe.question_version_id,
        rubric_version_id=qe.rubric_version_id,
        max_mark=qe.max_mark,
        reference_score=qe.final_human_approved_score,
        criterion_snapshot=copy.deepcopy(qe.criterion_snapshot or []),
        evidence_snapshot=evidence_snapshot,
        source_snapshot_hash=source_snapshot_hash,
    )
    db.add(case)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise QualityError(
            "CALIBRATION_CASE_CONFLICT", "Case already exists for this QE"
        ) from exc
    await db.refresh(case)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="calibration_case",
        entity_id=case.id,
        action="CALIBRATION_CASE_ADDED",
        after=serialize_calibration_case_management(case),
    )
    return serialize_calibration_case_management(case)


async def add_calibration_participant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    if session.status != "DRAFT":
        raise QualityError(
            "CALIBRATION_SESSION_NOT_DRAFT",
            "Participants can only be added while the session is DRAFT",
        )
    user = await db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    if user is None:
        raise QualityError("NOT_FOUND", "User not found in tenant")

    existing = await db.scalar(
        select(CalibrationParticipant).where(
            CalibrationParticipant.tenant_id == tenant_id,
            CalibrationParticipant.session_id == session_id,
            CalibrationParticipant.user_id == user_id,
        )
    )
    if existing is not None:
        return {"id": str(existing.id), "user_id": str(existing.user_id)}

    participant = CalibrationParticipant(
        tenant_id=tenant_id,
        session_id=session_id,
        user_id=user_id,
    )
    db.add(participant)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise QualityError(
            "CALIBRATION_PARTICIPANT_CONFLICT", "Participant already added"
        ) from exc
    await db.refresh(participant)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="calibration_participant",
        entity_id=participant.id,
        action="CALIBRATION_PARTICIPANT_ADDED",
        after={"id": str(participant.id), "user_id": str(user_id)},
    )
    return {"id": str(participant.id), "user_id": str(participant.user_id)}


async def activate_calibration_session(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    if session.status == "ACTIVE":
        count = await _case_count(db, tenant_id=tenant_id, session_id=session_id)
        return serialize_calibration_session(session, case_count=count)
    if session.status != "DRAFT":
        raise QualityError(
            "CALIBRATION_SESSION_NOT_DRAFT",
            "Only DRAFT sessions can be activated",
        )
    count = await _case_count(db, tenant_id=tenant_id, session_id=session_id)
    if count < session.min_cases:
        raise QualityError(
            "CALIBRATION_INSUFFICIENT_CASES",
            f"Need at least {session.min_cases} cases to activate (have {count})",
        )
    participants = list(
        (
            await db.scalars(
                select(CalibrationParticipant).where(
                    CalibrationParticipant.tenant_id == tenant_id,
                    CalibrationParticipant.session_id == session_id,
                )
            )
        ).all()
    )
    if len(participants) < 2:
        raise QualityError(
            "CALIBRATION_INSUFFICIENT_PARTICIPANTS",
            "Need at least 2 participants to activate",
        )
    session.status = "ACTIVE"
    session.activated_by = actor_user_id
    session.activated_at = _utcnow()
    await db.flush()
    await db.refresh(session)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="calibration_session",
        entity_id=session.id,
        action="CALIBRATION_SESSION_ACTIVATED",
        after=serialize_calibration_session(session, case_count=count),
    )
    return serialize_calibration_session(session, case_count=count)


async def list_my_calibration_sessions(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any]:
    participant_rows = list(
        (
            await db.scalars(
                select(CalibrationParticipant).where(
                    CalibrationParticipant.tenant_id == tenant_id,
                    CalibrationParticipant.user_id == user_id,
                )
            )
        ).all()
    )
    session_ids = [p.session_id for p in participant_rows]
    if not session_ids:
        return {"items": []}
    rows = list(
        (
            await db.scalars(
                select(CalibrationSession)
                .where(
                    CalibrationSession.tenant_id == tenant_id,
                    CalibrationSession.id.in_(session_ids),
                    CalibrationSession.status.in_(["ACTIVE", "CLOSED"]),
                )
                .order_by(CalibrationSession.created_at.desc())
            )
        ).all()
    )
    items = []
    for row in rows:
        count = await _case_count(db, tenant_id=tenant_id, session_id=row.id)
        items.append(serialize_calibration_session(row, case_count=count))
    return {"items": items}


async def _require_participant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CalibrationParticipant:
    participant = await db.scalar(
        select(CalibrationParticipant).where(
            CalibrationParticipant.tenant_id == tenant_id,
            CalibrationParticipant.session_id == session_id,
            CalibrationParticipant.user_id == user_id,
        )
    )
    if participant is None:
        raise QualityError(
            "CALIBRATION_NOT_PARTICIPANT",
            "Caller is not a participant in this session",
        )
    return participant


async def get_blind_calibration_case(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    case_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    if session.status not in {"ACTIVE", "CLOSED"}:
        raise QualityError(
            "CALIBRATION_SESSION_NOT_ACTIVE",
            "Blind cases are available only after activation",
        )
    await _require_participant(
        db, tenant_id=tenant_id, session_id=session_id, user_id=user_id
    )
    case = await db.scalar(
        select(CalibrationCase).where(
            CalibrationCase.id == case_id,
            CalibrationCase.tenant_id == tenant_id,
            CalibrationCase.session_id == session_id,
        )
    )
    if case is None:
        raise QualityError("NOT_FOUND", "Calibration case not found")
    return serialize_calibration_case_blind(case)


async def submit_calibration_response(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    case_id: uuid.UUID,
    user_id: uuid.UUID,
    score: Decimal,
    comment: str | None = None,
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    if session.status != "ACTIVE":
        raise QualityError(
            "CALIBRATION_SESSION_NOT_ACTIVE",
            "Responses can only be submitted while ACTIVE",
        )
    participant = await _require_participant(
        db, tenant_id=tenant_id, session_id=session_id, user_id=user_id
    )
    case = await db.scalar(
        select(CalibrationCase).where(
            CalibrationCase.id == case_id,
            CalibrationCase.tenant_id == tenant_id,
            CalibrationCase.session_id == session_id,
        )
    )
    if case is None:
        raise QualityError("NOT_FOUND", "Calibration case not found")

    score_dec = _as_decimal(score)
    if score_dec < 0 or score_dec > case.max_mark:
        raise QualityError(
            "CALIBRATION_SCORE_OUT_OF_BOUNDS",
            f"Score must be between 0 and {case.max_mark}",
        )

    existing = await db.scalar(
        select(CalibrationResponse).where(
            CalibrationResponse.tenant_id == tenant_id,
            CalibrationResponse.session_id == session_id,
            CalibrationResponse.case_id == case_id,
            CalibrationResponse.user_id == user_id,
        )
    )
    if existing is not None:
        raise QualityError(
            "CALIBRATION_RESPONSE_IMMUTABLE",
            "Response already submitted and cannot be changed",
        )

    response = CalibrationResponse(
        tenant_id=tenant_id,
        session_id=session_id,
        case_id=case_id,
        participant_id=participant.id,
        user_id=user_id,
        score=score_dec,
        max_mark=case.max_mark,
        comment=comment,
        submitted_at=_utcnow(),
    )
    db.add(response)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise QualityError(
            "CALIBRATION_RESPONSE_IMMUTABLE",
            "Response already submitted and cannot be changed",
        ) from exc
    await db.refresh(response)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        entity_type="calibration_response",
        entity_id=response.id,
        action="CALIBRATION_RESPONSE_SUBMITTED",
        after=serialize_calibration_response(response),
    )
    return serialize_calibration_response(response)


async def get_calibration_progress(
    db: AsyncSession, *, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> dict[str, Any]:
    await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    cases = list(
        (
            await db.scalars(
                select(CalibrationCase).where(
                    CalibrationCase.tenant_id == tenant_id,
                    CalibrationCase.session_id == session_id,
                )
            )
        ).all()
    )
    participants = list(
        (
            await db.scalars(
                select(CalibrationParticipant).where(
                    CalibrationParticipant.tenant_id == tenant_id,
                    CalibrationParticipant.session_id == session_id,
                )
            )
        ).all()
    )
    responses = list(
        (
            await db.scalars(
                select(CalibrationResponse).where(
                    CalibrationResponse.tenant_id == tenant_id,
                    CalibrationResponse.session_id == session_id,
                )
            )
        ).all()
    )
    expected = len(cases) * len(participants)
    by_user: dict[str, int] = {str(p.user_id): 0 for p in participants}
    for resp in responses:
        key = str(resp.user_id)
        by_user[key] = by_user.get(key, 0) + 1
    return {
        "session_id": str(session_id),
        "case_count": len(cases),
        "participant_count": len(participants),
        "response_count": len(responses),
        "expected_response_count": expected,
        "completion_rate": (len(responses) / expected) if expected else 0.0,
        "responses_by_user": by_user,
    }


def _within_tolerance(
    *,
    score: Decimal,
    reference: Decimal,
    max_mark: Decimal,
    abs_tol: Decimal,
    pct_tol: Decimal,
) -> bool:
    diff = abs(score - reference)
    if diff <= abs_tol:
        return True
    if max_mark > 0 and diff <= (pct_tol * max_mark):
        return True
    return False


async def close_calibration_session(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    if session.status == "CLOSED":
        # Idempotent: ensure metrics exist, return session.
        await _ensure_calibration_metrics(db, tenant_id=tenant_id, session=session)
        count = await _case_count(db, tenant_id=tenant_id, session_id=session_id)
        return serialize_calibration_session(session, case_count=count)
    if session.status != "ACTIVE":
        raise QualityError(
            "CALIBRATION_SESSION_NOT_ACTIVE",
            "Only ACTIVE sessions can be closed",
        )

    session.status = "CLOSED"
    session.closed_by = actor_user_id
    session.closed_at = _utcnow()
    await _ensure_calibration_metrics(db, tenant_id=tenant_id, session=session)
    await db.flush()
    await db.refresh(session)
    count = await _case_count(db, tenant_id=tenant_id, session_id=session_id)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="calibration_session",
        entity_id=session.id,
        action="CALIBRATION_SESSION_CLOSED",
        after=serialize_calibration_session(session, case_count=count),
    )
    return serialize_calibration_session(session, case_count=count)


async def _ensure_calibration_metrics(
    db: AsyncSession, *, tenant_id: uuid.UUID, session: CalibrationSession
) -> None:
    existing_session_metric = await db.scalar(
        select(CalibrationSessionMetric).where(
            CalibrationSessionMetric.tenant_id == tenant_id,
            CalibrationSessionMetric.session_id == session.id,
            CalibrationSessionMetric.metric_name == "ICC_A1",
            CalibrationSessionMetric.algorithm_version == ALGORITHM_CAL,
        )
    )
    if existing_session_metric is None:
        cases = list(
            (
                await db.scalars(
                    select(CalibrationCase)
                    .where(
                        CalibrationCase.tenant_id == tenant_id,
                        CalibrationCase.session_id == session.id,
                    )
                    .order_by(CalibrationCase.case_code.asc())
                )
            ).all()
        )
        participants = list(
            (
                await db.scalars(
                    select(CalibrationParticipant)
                    .where(
                        CalibrationParticipant.tenant_id == tenant_id,
                        CalibrationParticipant.session_id == session.id,
                    )
                    .order_by(CalibrationParticipant.user_id.asc())
                )
            ).all()
        )
        responses = list(
            (
                await db.scalars(
                    select(CalibrationResponse).where(
                        CalibrationResponse.tenant_id == tenant_id,
                        CalibrationResponse.session_id == session.id,
                    )
                )
            ).all()
        )
        resp_map: dict[tuple[uuid.UUID, uuid.UUID], float] = {
            (r.case_id, r.user_id): float(r.score) for r in responses
        }
        # Common cases: every participant responded.
        common_cases = [
            case
            for case in cases
            if all((case.id, p.user_id) in resp_map for p in participants)
        ]
        evaluator_count = len(participants)
        common_case_count = len(common_cases)
        # Product reliability floor (B17 V1): always MIN_CALIBRATION_CASES=10,
        # independent of session.min_cases used for activation/training.
        icc_value: float | None = None
        status = "INSUFFICIENT_SAMPLE"
        if evaluator_count >= 2 and common_case_count >= MIN_CALIBRATION_CASES:
            matrix = [
                [resp_map[(case.id, p.user_id)] for p in participants]
                for case in common_cases
            ]
            icc_value, _icc_reason = icc_a1(matrix)
            status = "COMPLETED" if icc_value is not None else "UNDEFINED"

        db.add(
            CalibrationSessionMetric(
                tenant_id=tenant_id,
                session_id=session.id,
                metric_name="ICC_A1",
                algorithm_version=ALGORITHM_CAL,
                evaluator_count=evaluator_count,
                common_case_count=common_case_count,
                icc_value=_as_decimal(icc_value) if icc_value is not None else None,
                status=status,
            )
        )

    # Evaluator metrics vs reference (idempotent per user).
    cases = list(
        (
            await db.scalars(
                select(CalibrationCase).where(
                    CalibrationCase.tenant_id == tenant_id,
                    CalibrationCase.session_id == session.id,
                )
            )
        ).all()
    )
    case_by_id = {c.id: c for c in cases}
    participants = list(
        (
            await db.scalars(
                select(CalibrationParticipant).where(
                    CalibrationParticipant.tenant_id == tenant_id,
                    CalibrationParticipant.session_id == session.id,
                )
            )
        ).all()
    )
    responses = list(
        (
            await db.scalars(
                select(CalibrationResponse).where(
                    CalibrationResponse.tenant_id == tenant_id,
                    CalibrationResponse.session_id == session.id,
                )
            )
        ).all()
    )
    by_user: dict[uuid.UUID, list[CalibrationResponse]] = {}
    for resp in responses:
        by_user.setdefault(resp.user_id, []).append(resp)

    for participant in participants:
        existing = await db.scalar(
            select(CalibrationEvaluatorMetric).where(
                CalibrationEvaluatorMetric.tenant_id == tenant_id,
                CalibrationEvaluatorMetric.session_id == session.id,
                CalibrationEvaluatorMetric.user_id == participant.user_id,
            )
        )
        if existing is not None:
            continue
        user_responses = by_user.get(participant.user_id, [])
        if not user_responses:
            db.add(
                CalibrationEvaluatorMetric(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    user_id=participant.user_id,
                    case_count=0,
                    mean_signed_diff=Decimal("0"),
                    mae=Decimal("0"),
                    nmae=Decimal("0"),
                    exact_match_rate=Decimal("0"),
                    within_tolerance_rate=Decimal("0"),
                )
            )
            continue

        signed: list[float] = []
        abs_errs: list[float] = []
        exact = 0
        within = 0
        for resp in user_responses:
            case = case_by_id[resp.case_id]
            ref = float(case.reference_score)
            score = float(resp.score)
            diff = score - ref
            signed.append(diff)
            abs_errs.append(abs(diff))
            if abs(diff) < 1e-9:
                exact += 1
            if _within_tolerance(
                score=resp.score,
                reference=case.reference_score,
                max_mark=case.max_mark,
                abs_tol=session.score_tolerance_abs,
                pct_tol=session.score_tolerance_pct,
            ):
                within += 1
        n = len(user_responses)
        mae = sum(abs_errs) / n
        mean_signed = sum(signed) / n
        # Normalized MAE against mean max_mark of scored cases.
        mean_max = sum(float(case_by_id[r.case_id].max_mark) for r in user_responses) / n
        nmae = (mae / mean_max) if mean_max > 0 else 0.0
        db.add(
            CalibrationEvaluatorMetric(
                tenant_id=tenant_id,
                session_id=session.id,
                user_id=participant.user_id,
                case_count=n,
                mean_signed_diff=_as_decimal(mean_signed),
                mae=_as_decimal(mae),
                nmae=_as_decimal(nmae),
                exact_match_rate=_as_decimal(exact / n),
                within_tolerance_rate=_as_decimal(within / n),
            )
        )
    await db.flush()


async def get_calibration_session_metrics(
    db: AsyncSession, *, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    if session.status != "CLOSED":
        raise QualityError(
            "CALIBRATION_SESSION_NOT_CLOSED",
            "Session metrics are available after close",
        )
    await _ensure_calibration_metrics(db, tenant_id=tenant_id, session=session)
    rows = list(
        (
            await db.scalars(
                select(CalibrationSessionMetric).where(
                    CalibrationSessionMetric.tenant_id == tenant_id,
                    CalibrationSessionMetric.session_id == session_id,
                )
            )
        ).all()
    )
    return {"items": [serialize_session_metric(row) for row in rows]}


async def get_calibration_evaluator_metrics(
    db: AsyncSession, *, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    if session.status != "CLOSED":
        raise QualityError(
            "CALIBRATION_SESSION_NOT_CLOSED",
            "Evaluator metrics are available after close",
        )
    await _ensure_calibration_metrics(db, tenant_id=tenant_id, session=session)
    rows = list(
        (
            await db.scalars(
                select(CalibrationEvaluatorMetric).where(
                    CalibrationEvaluatorMetric.tenant_id == tenant_id,
                    CalibrationEvaluatorMetric.session_id == session_id,
                )
            )
        ).all()
    )
    return {"items": [serialize_evaluator_metric(row) for row in rows]}


async def get_my_calibration_metrics(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    session = await _get_session(db, tenant_id=tenant_id, session_id=session_id)
    await _require_participant(
        db, tenant_id=tenant_id, session_id=session_id, user_id=user_id
    )
    if session.status != "CLOSED":
        raise QualityError(
            "CALIBRATION_SESSION_NOT_CLOSED",
            "Own metrics are available after close",
        )
    await _ensure_calibration_metrics(db, tenant_id=tenant_id, session=session)
    row = await db.scalar(
        select(CalibrationEvaluatorMetric).where(
            CalibrationEvaluatorMetric.tenant_id == tenant_id,
            CalibrationEvaluatorMetric.session_id == session_id,
            CalibrationEvaluatorMetric.user_id == user_id,
        )
    )
    if row is None:
        raise QualityError("NOT_FOUND", "Evaluator metrics not found")
    return serialize_evaluator_metric(row)
