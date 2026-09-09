"""B15 gold benchmark curation and isolated AI regression (PEV-058/059).

Default release-gate thresholds (copied into version snapshot at create; editable
until lock):

```python
B15_DEFAULT_THRESHOLDS = {
  "profile_code": "B15_DEFAULT_V1",
  "algorithm_version": "B15_V1",
  "max_missing_output_rate": 0.0,
  "max_mean_abs_score_error": 0.25,
  "min_exact_score_agreement_rate": 1.0,
  "min_taxonomy_agreement_rate": 1.0,
  "max_safety_invariant_failure_rate": 0.0,
  "score_tolerance": 0.0,  # exact unless tolerance > 0
}
```

Deterministic metric formulas (n = case count in run):
- missing_output_rate = missing_count / n (n=0 → treat as fail safety)
- mean_abs_score_error = mean(score_abs_error) over non-missing;
  if all missing → 0 but missing rate fails
- exact_score_agreement_rate = exact_match_count / n
- taxonomy_agreement_rate = taxonomy_match_count / taxonomy_applicable_count;
  if applicable=0 → 1.0
- safety_invariant_failure_rate = safety_fail_count / n
- Overall PASS iff all threshold comparisons hold (≤ for max_*, ≥ for min_*)

Regression never mutates QuestionEvaluation / PublishedResult / Mastery* /
EvaluationLedger rows.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.benchmark import (
    FIXED_BENCHMARK_PROVIDER,
    BenchmarkCandidateOutput,
    resolve_fixed_benchmark_provider,
)
from app.ai.tracing import (
    canonical_input_hash,
    record_ai_execution,
    redacted_evaluation_response_summary,
    redacted_request_summary,
)
from app.db.models import (
    AnswerRegionTranscription,
    BenchmarkCase,
    BenchmarkDataset,
    BenchmarkDatasetVersion,
    BenchmarkRegressionCaseResult,
    BenchmarkRegressionRun,
    PublishedResult,
    QuestionEvaluation,
)
from app.db.models.benchmark import ALGORITHM_VERSION_B15_V1
from app.services.audit import add_audit_event

B15_DEFAULT_THRESHOLDS: dict[str, Any] = {
    "profile_code": "B15_DEFAULT_V1",
    "algorithm_version": ALGORITHM_VERSION_B15_V1,
    "max_missing_output_rate": 0.0,
    "max_mean_abs_score_error": 0.25,
    "min_exact_score_agreement_rate": 1.0,
    "min_taxonomy_agreement_rate": 1.0,
    "max_safety_invariant_failure_rate": 0.0,
    "score_tolerance": 0.0,
}

ELIGIBLE_WORKFLOW_STATES = frozenset({"ACCEPTED", "OVERRIDDEN"})


class BenchmarkError(RuntimeError):
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


def _stable_json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_error_codes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return sorted(str(code) for code in raw)


def default_threshold_snapshot() -> dict[str, Any]:
    return copy.deepcopy(B15_DEFAULT_THRESHOLDS)


def compare_case_output(
    *,
    expected_final_marks: Decimal,
    expected_max_marks: Decimal,
    expected_error_codes: list[str],
    actual_marks: Decimal | None,
    actual_error_codes: list[str] | None,
    missing_output: bool,
    score_tolerance: Decimal = Decimal("0"),
) -> dict[str, Any]:
    """Compare one candidate output to gold; returns case-result metric fields."""
    expected_codes = _normalize_error_codes(expected_error_codes)
    actual_codes = _normalize_error_codes(actual_error_codes or [])

    if missing_output or actual_marks is None:
        return {
            "missing_output": True,
            "actual_marks": None,
            "actual_error_codes": actual_codes,
            "score_abs_error": None,
            "exact_score_match": False,
            "taxonomy_match": None,
            "safety_invariant_failed": False,
            "diff": {
                "reason": "missing_output",
                "expected_final_marks": str(expected_final_marks),
                "expected_error_codes": expected_codes,
            },
        }

    abs_error = abs(Decimal(str(actual_marks)) - Decimal(str(expected_final_marks)))
    exact = abs_error <= Decimal(str(score_tolerance))
    taxonomy_applicable = True
    taxonomy_ok = actual_codes == expected_codes
    safety_failed = Decimal(str(actual_marks)) > Decimal(str(expected_max_marks))

    return {
        "missing_output": False,
        "actual_marks": Decimal(str(actual_marks)),
        "actual_error_codes": actual_codes,
        "score_abs_error": abs_error,
        "exact_score_match": exact,
        "taxonomy_match": taxonomy_ok if taxonomy_applicable else None,
        "safety_invariant_failed": safety_failed,
        "diff": {
            "expected_final_marks": str(expected_final_marks),
            "actual_marks": str(actual_marks),
            "score_abs_error": str(abs_error),
            "expected_error_codes": expected_codes,
            "actual_error_codes": actual_codes,
            "safety_invariant_failed": safety_failed,
        },
    }


def aggregate_regression_metrics(
    case_rows: list[dict[str, Any]],
    *,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate per-case results into rates and overall PASS/FAIL verdict.

    ``case_rows`` items use keys produced by :func:`compare_case_output`
    (missing_output, score_abs_error, exact_score_match, taxonomy_match,
    safety_invariant_failed).
    """
    profile = thresholds or B15_DEFAULT_THRESHOLDS
    n = len(case_rows)
    if n == 0:
        metrics = {
            "case_count": 0,
            "missing_count": 0,
            "missing_output_rate": 1.0,
            "mean_abs_score_error": 0.0,
            "exact_score_agreement_rate": 0.0,
            "taxonomy_agreement_rate": 1.0,
            "safety_invariant_failure_rate": 1.0,
            "exact_match_count": 0,
            "taxonomy_match_count": 0,
            "taxonomy_applicable_count": 0,
            "safety_fail_count": 0,
        }
        return {
            **metrics,
            "verdict": "FAIL",
            "passed": False,
            "threshold_comparisons": {
                "empty_run_safety_fail": True,
            },
        }

    missing_count = sum(1 for row in case_rows if row.get("missing_output"))
    exact_match_count = sum(1 for row in case_rows if row.get("exact_score_match"))
    safety_fail_count = sum(
        1 for row in case_rows if row.get("safety_invariant_failed")
    )
    score_errors = [
        Decimal(str(row["score_abs_error"]))
        for row in case_rows
        if not row.get("missing_output") and row.get("score_abs_error") is not None
    ]
    if score_errors:
        mean_abs = sum(score_errors, Decimal("0")) / Decimal(len(score_errors))
    else:
        mean_abs = Decimal("0")

    taxonomy_applicable = [
        row for row in case_rows if row.get("taxonomy_match") is not None
    ]
    taxonomy_match_count = sum(
        1 for row in taxonomy_applicable if row.get("taxonomy_match") is True
    )
    taxonomy_applicable_count = len(taxonomy_applicable)
    if taxonomy_applicable_count == 0:
        taxonomy_rate = 1.0
    else:
        taxonomy_rate = taxonomy_match_count / taxonomy_applicable_count

    metrics = {
        "case_count": n,
        "missing_count": missing_count,
        "missing_output_rate": missing_count / n,
        "mean_abs_score_error": float(mean_abs),
        "exact_score_agreement_rate": exact_match_count / n,
        "taxonomy_agreement_rate": taxonomy_rate,
        "safety_invariant_failure_rate": safety_fail_count / n,
        "exact_match_count": exact_match_count,
        "taxonomy_match_count": taxonomy_match_count,
        "taxonomy_applicable_count": taxonomy_applicable_count,
        "safety_fail_count": safety_fail_count,
    }

    comparisons = {
        "missing_output_rate": metrics["missing_output_rate"]
        <= float(profile["max_missing_output_rate"]),
        "mean_abs_score_error": metrics["mean_abs_score_error"]
        <= float(profile["max_mean_abs_score_error"]),
        "exact_score_agreement_rate": metrics["exact_score_agreement_rate"]
        >= float(profile["min_exact_score_agreement_rate"]),
        "taxonomy_agreement_rate": metrics["taxonomy_agreement_rate"]
        >= float(profile["min_taxonomy_agreement_rate"]),
        "safety_invariant_failure_rate": metrics["safety_invariant_failure_rate"]
        <= float(profile["max_safety_invariant_failure_rate"]),
    }
    passed = all(comparisons.values())
    return {
        **metrics,
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "threshold_comparisons": comparisons,
    }


def serialize_dataset(dataset: BenchmarkDataset) -> dict[str, Any]:
    return {
        "id": str(dataset.id),
        "code": dataset.code,
        "title": dataset.title,
        "description": dataset.description,
        "created_by": str(dataset.created_by) if dataset.created_by else None,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
        "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None,
    }


def serialize_version(version: BenchmarkDatasetVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "dataset_id": str(version.dataset_id),
        "version_number": version.version_number,
        "status": version.status,
        "threshold_profile_snapshot": version.threshold_profile_snapshot or {},
        "case_count": version.case_count,
        "content_hash": version.content_hash,
        "locked_by": str(version.locked_by) if version.locked_by else None,
        "locked_at": version.locked_at.isoformat() if version.locked_at else None,
        "created_by": str(version.created_by) if version.created_by else None,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "updated_at": version.updated_at.isoformat() if version.updated_at else None,
    }


def serialize_case(case: BenchmarkCase) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "dataset_version_id": str(case.dataset_version_id),
        "published_result_id": str(case.published_result_id),
        "evaluation_run_id": str(case.evaluation_run_id),
        "question_evaluation_id": str(case.question_evaluation_id),
        "question_version_id": str(case.question_version_id),
        "rubric_version_id": str(case.rubric_version_id),
        "assessment_version_id": str(case.assessment_version_id),
        "expected_final_marks": _dec(case.expected_final_marks),
        "expected_max_marks": _dec(case.expected_max_marks),
        "expected_error_codes": case.expected_error_codes or [],
        "source_ledger_hash": case.source_ledger_hash,
        "evidence_hash": case.evidence_hash,
        "adjudicated_by": str(case.adjudicated_by) if case.adjudicated_by else None,
        "adjudicated_at": case.adjudicated_at.isoformat()
        if case.adjudicated_at
        else None,
        "replay_fixture": case.replay_fixture or {},
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


def serialize_run(run: BenchmarkRegressionRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "dataset_version_id": str(run.dataset_version_id),
        "status": run.status,
        "verdict": run.verdict,
        "idempotency_key": run.idempotency_key,
        "candidate_provider": run.candidate_provider,
        "candidate_model": run.candidate_model,
        "candidate_model_version": run.candidate_model_version,
        "candidate_prompt_template_version": run.candidate_prompt_template_version,
        "candidate_config": run.candidate_config or {},
        "threshold_snapshot": run.threshold_snapshot or {},
        "aggregate_metrics": run.aggregate_metrics or {},
        "initiated_by": str(run.initiated_by) if run.initiated_by else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "failure_code": run.failure_code,
        "failure_detail": run.failure_detail,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def serialize_case_result(row: BenchmarkRegressionCaseResult) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "regression_run_id": str(row.regression_run_id),
        "benchmark_case_id": str(row.benchmark_case_id),
        "missing_output": row.missing_output,
        "actual_marks": _dec(row.actual_marks),
        "actual_error_codes": row.actual_error_codes or [],
        "score_abs_error": _dec(row.score_abs_error),
        "exact_score_match": row.exact_score_match,
        "taxonomy_match": row.taxonomy_match,
        "safety_invariant_failed": row.safety_invariant_failed,
        "diff": row.diff or {},
        "ai_execution_record_id": str(row.ai_execution_record_id)
        if row.ai_execution_record_id
        else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def _get_dataset(
    db: AsyncSession, *, tenant_id: uuid.UUID, dataset_id: uuid.UUID
) -> BenchmarkDataset:
    row = await db.scalar(
        select(BenchmarkDataset).where(
            BenchmarkDataset.id == dataset_id,
            BenchmarkDataset.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise BenchmarkError("NOT_FOUND", "Benchmark dataset not found")
    return row


async def _get_version(
    db: AsyncSession, *, tenant_id: uuid.UUID, version_id: uuid.UUID
) -> BenchmarkDatasetVersion:
    row = await db.scalar(
        select(BenchmarkDatasetVersion).where(
            BenchmarkDatasetVersion.id == version_id,
            BenchmarkDatasetVersion.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise BenchmarkError("NOT_FOUND", "Benchmark dataset version not found")
    return row


async def _get_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> BenchmarkRegressionRun:
    row = await db.scalar(
        select(BenchmarkRegressionRun).where(
            BenchmarkRegressionRun.id == run_id,
            BenchmarkRegressionRun.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise BenchmarkError("NOT_FOUND", "Benchmark regression run not found")
    return row


async def create_dataset(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    code: str,
    title: str,
    description: str | None = None,
) -> dict[str, Any]:
    existing = await db.scalar(
        select(BenchmarkDataset).where(
            BenchmarkDataset.tenant_id == tenant_id,
            BenchmarkDataset.code == code,
        )
    )
    if existing is not None:
        raise BenchmarkError(
            "BENCHMARK_DATASET_CODE_CONFLICT",
            f"Dataset code already exists: {code}",
        )
    dataset = BenchmarkDataset(
        tenant_id=tenant_id,
        code=code,
        title=title,
        description=description,
        created_by=actor_user_id,
    )
    db.add(dataset)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="BenchmarkDataset",
        entity_id=dataset.id,
        action="benchmark_dataset_created",
        after=serialize_dataset(dataset),
    )
    return serialize_dataset(dataset)


async def list_datasets(
    db: AsyncSession, *, tenant_id: uuid.UUID
) -> dict[str, Any]:
    rows = list(
        (
            await db.scalars(
                select(BenchmarkDataset)
                .where(BenchmarkDataset.tenant_id == tenant_id)
                .order_by(BenchmarkDataset.created_at.desc())
            )
        ).all()
    )
    return {"items": [serialize_dataset(row) for row in rows]}


async def get_dataset(
    db: AsyncSession, *, tenant_id: uuid.UUID, dataset_id: uuid.UUID
) -> dict[str, Any]:
    dataset = await _get_dataset(db, tenant_id=tenant_id, dataset_id=dataset_id)
    return serialize_dataset(dataset)


async def create_version(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    dataset_id: uuid.UUID,
    threshold_profile_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await _get_dataset(db, tenant_id=tenant_id, dataset_id=dataset_id)
    max_number = await db.scalar(
        select(func.max(BenchmarkDatasetVersion.version_number)).where(
            BenchmarkDatasetVersion.tenant_id == tenant_id,
            BenchmarkDatasetVersion.dataset_id == dataset_id,
        )
    )
    next_number = int(max_number or 0) + 1
    snapshot = (
        copy.deepcopy(threshold_profile_snapshot)
        if threshold_profile_snapshot is not None
        else default_threshold_snapshot()
    )
    version = BenchmarkDatasetVersion(
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        version_number=next_number,
        status="DRAFT",
        threshold_profile_snapshot=snapshot,
        case_count=0,
        created_by=actor_user_id,
    )
    db.add(version)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="BenchmarkDatasetVersion",
        entity_id=version.id,
        action="benchmark_version_created",
        after=serialize_version(version),
    )
    return serialize_version(version)


async def list_versions(
    db: AsyncSession, *, tenant_id: uuid.UUID, dataset_id: uuid.UUID
) -> dict[str, Any]:
    await _get_dataset(db, tenant_id=tenant_id, dataset_id=dataset_id)
    rows = list(
        (
            await db.scalars(
                select(BenchmarkDatasetVersion)
                .where(
                    BenchmarkDatasetVersion.tenant_id == tenant_id,
                    BenchmarkDatasetVersion.dataset_id == dataset_id,
                )
                .order_by(BenchmarkDatasetVersion.version_number.desc())
            )
        ).all()
    )
    return {"items": [serialize_version(row) for row in rows]}


async def get_version(
    db: AsyncSession, *, tenant_id: uuid.UUID, version_id: uuid.UUID
) -> dict[str, Any]:
    version = await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    return serialize_version(version)


async def list_eligible_sources(
    db: AsyncSession, *, tenant_id: uuid.UUID, version_id: uuid.UUID
) -> dict[str, Any]:
    await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    published = list(
        (
            await db.scalars(
                select(PublishedResult).where(
                    PublishedResult.tenant_id == tenant_id,
                    PublishedResult.status == "PUBLISHED",
                )
            )
        ).all()
    )
    items: list[dict[str, Any]] = []
    for pr in published:
        qes = list(
            (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.tenant_id == tenant_id,
                        QuestionEvaluation.evaluation_run_id == pr.evaluation_run_id,
                        QuestionEvaluation.workflow_state.in_(
                            list(ELIGIBLE_WORKFLOW_STATES)
                        ),
                        QuestionEvaluation.final_human_approved_score.is_not(None),
                    )
                )
            ).all()
        )
        if not qes:
            continue
        items.append(
            {
                "published_result_id": str(pr.id),
                "evaluation_run_id": str(pr.evaluation_run_id),
                "submission_id": str(pr.submission_id),
                "assessment_version_id": str(pr.assessment_version_id),
                "ledger_snapshot_hash": pr.ledger_snapshot_hash,
                "question_evaluations": [
                    {
                        "question_evaluation_id": str(qe.id),
                        "question_version_id": str(qe.question_version_id),
                        "workflow_state": qe.workflow_state,
                        "final_human_approved_score": _dec(
                            qe.final_human_approved_score
                        ),
                        "max_mark": _dec(qe.max_mark),
                        "error_codes": qe.error_codes or [],
                    }
                    for qe in qes
                ],
            }
        )
    return {"items": items}


async def _load_transcription_text(
    db: AsyncSession, *, tenant_id: uuid.UUID, qe: QuestionEvaluation
) -> tuple[str, bool]:
    """Build anonymized transcription text from region refs (no student PII)."""
    texts: list[str] = []
    unreadable = False
    for ref in qe.transcription_refs or []:
        if not isinstance(ref, dict):
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
                AnswerRegionTranscription.id == tid,
                AnswerRegionTranscription.tenant_id == tenant_id,
            )
        )
        if row is None:
            continue
        if row.unreadable:
            unreadable = True
        if row.text:
            texts.append(row.text)
    if "UNREADABLE" in (qe.error_codes or []):
        unreadable = True
    return "\n".join(texts), unreadable


def _build_replay_fixture(
    *,
    qe: QuestionEvaluation,
    transcription_text: str,
    unreadable: bool,
    expected_final_marks: Decimal,
    expected_max_marks: Decimal,
    expected_error_codes: list[str],
) -> dict[str, Any]:
    """Frozen minimal rubric/transcription payload — no student name/id."""
    return {
        "question_version_id": str(qe.question_version_id),
        "assessment_version_id": str(qe.assessment_version_id),
        "rubric_version_id": str(qe.rubric_version_id),
        "criterion_snapshot": copy.deepcopy(qe.criterion_snapshot or []),
        "transcription_text": transcription_text,
        "blank_flag": not bool(transcription_text.strip()),
        "unreadable_flag": unreadable,
        "expected_final_marks": str(expected_final_marks),
        "expected_max_marks": str(expected_max_marks),
        "expected_error_codes": expected_error_codes,
        "max_mark": str(qe.max_mark),
    }


def _compute_evidence_hash(
    *,
    published_result_id: uuid.UUID,
    question_evaluation_id: uuid.UUID,
    expected_final_marks: Decimal,
    expected_max_marks: Decimal,
    expected_error_codes: list[str],
    source_ledger_hash: str,
    criterion_snapshot: list[Any],
) -> str:
    return _stable_json_hash(
        {
            "published_result_id": str(published_result_id),
            "question_evaluation_id": str(question_evaluation_id),
            "expected_final_marks": str(expected_final_marks),
            "expected_max_marks": str(expected_max_marks),
            "expected_error_codes": expected_error_codes,
            "source_ledger_hash": source_ledger_hash,
            "criterion_snapshot": criterion_snapshot,
        }
    )


async def add_case(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    version_id: uuid.UUID,
    published_result_id: uuid.UUID,
    question_evaluation_id: uuid.UUID,
) -> dict[str, Any]:
    version = await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    if version.status != "DRAFT":
        raise BenchmarkError(
            "BENCHMARK_VERSION_LOCKED",
            "Cannot add cases to a locked benchmark version",
        )

    existing = await db.scalar(
        select(BenchmarkCase).where(
            BenchmarkCase.tenant_id == tenant_id,
            BenchmarkCase.dataset_version_id == version_id,
            BenchmarkCase.question_evaluation_id == question_evaluation_id,
        )
    )
    if existing is not None:
        return serialize_case(existing)

    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        raise BenchmarkError("NOT_FOUND", "Published result not found")
    if published.status != "PUBLISHED":
        raise BenchmarkError(
            "BENCHMARK_CASE_INELIGIBLE",
            "Published result must be PUBLISHED",
        )

    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == question_evaluation_id,
            QuestionEvaluation.tenant_id == tenant_id,
        )
    )
    if qe is None:
        raise BenchmarkError("NOT_FOUND", "Question evaluation not found")
    if qe.evaluation_run_id != published.evaluation_run_id:
        raise BenchmarkError(
            "BENCHMARK_CASE_INELIGIBLE",
            "Question evaluation is not part of the published result run",
        )
    if qe.workflow_state not in ELIGIBLE_WORKFLOW_STATES:
        raise BenchmarkError(
            "BENCHMARK_CASE_INELIGIBLE",
            "Question evaluation must be ACCEPTED or OVERRIDDEN",
        )
    if qe.final_human_approved_score is None:
        raise BenchmarkError(
            "BENCHMARK_CASE_INELIGIBLE",
            "Question evaluation lacks final_human_approved_score",
        )

    expected_final = Decimal(str(qe.final_human_approved_score))
    expected_max = Decimal(str(qe.max_mark))
    expected_codes = _normalize_error_codes(qe.error_codes)
    transcription_text, unreadable = await _load_transcription_text(
        db, tenant_id=tenant_id, qe=qe
    )
    replay = _build_replay_fixture(
        qe=qe,
        transcription_text=transcription_text,
        unreadable=unreadable,
        expected_final_marks=expected_final,
        expected_max_marks=expected_max,
        expected_error_codes=expected_codes,
    )
    evidence_hash = _compute_evidence_hash(
        published_result_id=published.id,
        question_evaluation_id=qe.id,
        expected_final_marks=expected_final,
        expected_max_marks=expected_max,
        expected_error_codes=expected_codes,
        source_ledger_hash=published.ledger_snapshot_hash,
        criterion_snapshot=qe.criterion_snapshot or [],
    )
    case = BenchmarkCase(
        tenant_id=tenant_id,
        dataset_version_id=version.id,
        published_result_id=published.id,
        evaluation_run_id=qe.evaluation_run_id,
        question_evaluation_id=qe.id,
        question_version_id=qe.question_version_id,
        rubric_version_id=qe.rubric_version_id,
        assessment_version_id=qe.assessment_version_id,
        expected_final_marks=expected_final,
        expected_max_marks=expected_max,
        expected_error_codes=expected_codes,
        source_ledger_hash=published.ledger_snapshot_hash,
        evidence_hash=evidence_hash,
        adjudicated_by=actor_user_id,
        adjudicated_at=_utcnow(),
        replay_fixture=replay,
    )
    db.add(case)
    version.case_count = int(version.case_count or 0) + 1
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="BenchmarkCase",
        entity_id=case.id,
        action="benchmark_case_added",
        after=serialize_case(case),
    )
    return serialize_case(case)


async def list_cases(
    db: AsyncSession, *, tenant_id: uuid.UUID, version_id: uuid.UUID
) -> dict[str, Any]:
    await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    rows = list(
        (
            await db.scalars(
                select(BenchmarkCase)
                .where(
                    BenchmarkCase.tenant_id == tenant_id,
                    BenchmarkCase.dataset_version_id == version_id,
                )
                .order_by(BenchmarkCase.created_at.asc())
            )
        ).all()
    )
    return {"items": [serialize_case(row) for row in rows]}


async def remove_case(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    version_id: uuid.UUID,
    case_id: uuid.UUID,
) -> dict[str, Any]:
    version = await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    if version.status != "DRAFT":
        raise BenchmarkError(
            "BENCHMARK_VERSION_LOCKED",
            "Cannot remove cases from a locked benchmark version",
        )
    case = await db.scalar(
        select(BenchmarkCase).where(
            BenchmarkCase.id == case_id,
            BenchmarkCase.tenant_id == tenant_id,
            BenchmarkCase.dataset_version_id == version_id,
        )
    )
    if case is None:
        raise BenchmarkError("NOT_FOUND", "Benchmark case not found")
    payload = serialize_case(case)
    await db.delete(case)
    version.case_count = max(0, int(version.case_count or 0) - 1)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="BenchmarkCase",
        entity_id=case_id,
        action="benchmark_case_removed",
        before=payload,
    )
    return {"id": str(case_id), "removed": True}


def _version_content_hash(
    version: BenchmarkDatasetVersion, cases: list[BenchmarkCase]
) -> str:
    return _stable_json_hash(
        {
            "version_id": str(version.id),
            "version_number": version.version_number,
            "threshold_profile_snapshot": version.threshold_profile_snapshot or {},
            "case_evidence_hashes": sorted(case.evidence_hash for case in cases),
        }
    )


async def lock_version(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    cases = list(
        (
            await db.scalars(
                select(BenchmarkCase).where(
                    BenchmarkCase.tenant_id == tenant_id,
                    BenchmarkCase.dataset_version_id == version_id,
                )
            )
        ).all()
    )
    content_hash = _version_content_hash(version, cases)

    if version.status == "LOCKED":
        if version.content_hash == content_hash:
            return serialize_version(version)
        raise BenchmarkError(
            "BENCHMARK_VERSION_LOCKED",
            "Version is locked with a different content hash",
        )

    if len(cases) < 1:
        raise BenchmarkError(
            "BENCHMARK_VERSION_EMPTY",
            "Cannot lock a version with zero cases",
        )

    version.status = "LOCKED"
    version.content_hash = content_hash
    version.locked_by = actor_user_id
    version.locked_at = _utcnow()
    version.case_count = len(cases)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="BenchmarkDatasetVersion",
        entity_id=version.id,
        action="benchmark_version_locked",
        after=serialize_version(version),
    )
    return serialize_version(version)


async def _record_isolated_execution(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    case: BenchmarkCase,
    output: BenchmarkCandidateOutput,
) -> uuid.UUID:
    meta = output.execution_metadata
    record = await record_ai_execution(
        db,
        tenant_id=tenant_id,
        operation="gold_benchmark_evaluate",
        provider=meta.provider,
        status="SUCCEEDED" if not output.missing_output else "FAILED",
        request_summary=redacted_request_summary(
            operation="gold_benchmark_evaluate",
            entity_ids={
                "benchmark_case_id": str(case.id),
                "question_evaluation_id": str(case.question_evaluation_id),
            },
            input_refs={"replay_fixture_keys": sorted((case.replay_fixture or {}).keys())},
        ),
        response_summary=redacted_evaluation_response_summary(
            proposed_total=float(output.marks) if output.marks is not None else None,
            evaluation_confidence=None,
            criterion_count=len((case.replay_fixture or {}).get("criterion_snapshot") or []),
            error_codes=list(output.error_codes),
            ecf_applied=False,
            workflow_hint="isolated_benchmark",
        ),
        model=meta.model,
        model_version=meta.model_version,
        prompt_template_version=meta.prompt_template_version,
        input_hash=canonical_input_hash(
            {
                "benchmark_case_id": str(case.id),
                "evidence_hash": case.evidence_hash,
                "model": meta.model,
            }
        ),
        error_class="missing_output" if output.missing_output else None,
    )
    return record.id


async def start_regression_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    version_id: uuid.UUID,
    candidate_provider: str,
    candidate_model: str,
    candidate_model_version: str,
    candidate_prompt_template_version: str,
    candidate_config: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    version = await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    if version.status != "LOCKED":
        raise BenchmarkError(
            "BENCHMARK_VERSION_NOT_LOCKED",
            "Regression requires a LOCKED dataset version",
        )

    if idempotency_key:
        existing = await db.scalar(
            select(BenchmarkRegressionRun).where(
                BenchmarkRegressionRun.tenant_id == tenant_id,
                BenchmarkRegressionRun.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return serialize_run(existing)

    if candidate_provider != FIXED_BENCHMARK_PROVIDER:
        raise BenchmarkError(
            "BENCHMARK_CANDIDATE_UNSUPPORTED",
            f"Unsupported candidate provider: {candidate_provider}",
        )
    try:
        provider = resolve_fixed_benchmark_provider(candidate_model=candidate_model)
    except ValueError as exc:
        raise BenchmarkError(
            "BENCHMARK_CANDIDATE_UNSUPPORTED",
            str(exc),
        ) from exc

    cases = list(
        (
            await db.scalars(
                select(BenchmarkCase)
                .where(
                    BenchmarkCase.tenant_id == tenant_id,
                    BenchmarkCase.dataset_version_id == version_id,
                )
                .order_by(BenchmarkCase.created_at.asc())
            )
        ).all()
    )
    threshold_snapshot = copy.deepcopy(version.threshold_profile_snapshot or {})
    score_tolerance = Decimal(str(threshold_snapshot.get("score_tolerance", 0)))

    run = BenchmarkRegressionRun(
        tenant_id=tenant_id,
        dataset_version_id=version_id,
        status="RUNNING",
        verdict="PENDING",
        idempotency_key=idempotency_key,
        candidate_provider=candidate_provider,
        candidate_model=candidate_model,
        candidate_model_version=candidate_model_version,
        candidate_prompt_template_version=candidate_prompt_template_version,
        candidate_config=copy.deepcopy(candidate_config or {}),
        threshold_snapshot=threshold_snapshot,
        aggregate_metrics={},
        initiated_by=actor_user_id,
        started_at=_utcnow(),
    )
    db.add(run)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        db.expunge(run)
        if idempotency_key:
            existing = await db.scalar(
                select(BenchmarkRegressionRun).where(
                    BenchmarkRegressionRun.tenant_id == tenant_id,
                    BenchmarkRegressionRun.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return serialize_run(existing)
        raise BenchmarkError(
            "BENCHMARK_IDEMPOTENCY_CONFLICT",
            "Idempotency key conflict",
        ) from exc

    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="BenchmarkRegressionRun",
        entity_id=run.id,
        action="benchmark_regression_started",
        after=serialize_run(run),
    )

    case_metric_rows: list[dict[str, Any]] = []
    try:
        for case in cases:
            output = provider.evaluate_gold_case(
                case.replay_fixture or {},
                expected_final_marks=case.expected_final_marks,
                expected_max_marks=case.expected_max_marks,
                expected_error_codes=list(case.expected_error_codes or []),
            )
            compared = compare_case_output(
                expected_final_marks=case.expected_final_marks,
                expected_max_marks=case.expected_max_marks,
                expected_error_codes=list(case.expected_error_codes or []),
                actual_marks=output.marks,
                actual_error_codes=output.error_codes,
                missing_output=output.missing_output,
                score_tolerance=score_tolerance,
            )
            ai_record_id = await _record_isolated_execution(
                db, tenant_id=tenant_id, case=case, output=output
            )
            result_row = BenchmarkRegressionCaseResult(
                tenant_id=tenant_id,
                regression_run_id=run.id,
                benchmark_case_id=case.id,
                missing_output=bool(compared["missing_output"]),
                actual_marks=compared["actual_marks"],
                actual_error_codes=compared["actual_error_codes"],
                score_abs_error=compared["score_abs_error"],
                exact_score_match=bool(compared["exact_score_match"]),
                taxonomy_match=compared["taxonomy_match"],
                safety_invariant_failed=bool(compared["safety_invariant_failed"]),
                diff=compared["diff"],
                ai_execution_record_id=ai_record_id,
            )
            db.add(result_row)
            case_metric_rows.append(compared)

        metrics = aggregate_regression_metrics(
            case_metric_rows, thresholds=threshold_snapshot
        )
        run.aggregate_metrics = metrics
        run.verdict = str(metrics["verdict"])
        run.status = "PASSED" if metrics["passed"] else "FAILED"
        run.finished_at = _utcnow()
    except Exception as exc:  # noqa: BLE001 — isolate regression failures
        run.status = "ERROR"
        run.verdict = "FAIL"
        run.failure_code = "BENCHMARK_REGRESSION_ERROR"
        run.failure_detail = str(exc)[:2000]
        run.finished_at = _utcnow()
        run.aggregate_metrics = {
            "case_count": len(case_metric_rows),
            "error": True,
        }

    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="BenchmarkRegressionRun",
        entity_id=run.id,
        action="benchmark_regression_completed",
        after=serialize_run(run),
    )
    return serialize_run(run)


async def list_runs(
    db: AsyncSession, *, tenant_id: uuid.UUID, version_id: uuid.UUID
) -> dict[str, Any]:
    await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    rows = list(
        (
            await db.scalars(
                select(BenchmarkRegressionRun)
                .where(
                    BenchmarkRegressionRun.tenant_id == tenant_id,
                    BenchmarkRegressionRun.dataset_version_id == version_id,
                )
                .order_by(BenchmarkRegressionRun.created_at.desc())
            )
        ).all()
    )
    return {"items": [serialize_run(row) for row in rows]}


async def get_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    run = await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    return serialize_run(run)


async def list_case_results(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    rows = list(
        (
            await db.scalars(
                select(BenchmarkRegressionCaseResult)
                .where(
                    BenchmarkRegressionCaseResult.tenant_id == tenant_id,
                    BenchmarkRegressionCaseResult.regression_run_id == run_id,
                )
                .order_by(BenchmarkRegressionCaseResult.created_at.asc())
            )
        ).all()
    )
    return {"items": [serialize_case_result(row) for row in rows]}


async def evaluate_release_gate(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    run = await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    verdict = run.verdict
    passed = verdict == "PASS" and run.status == "PASSED"
    if verdict in {"FAIL", "PENDING"} or run.status in {"ERROR", "QUEUED", "RUNNING"}:
        passed = False
    result = {
        "verdict": verdict,
        "passed": passed,
        "run_id": str(run.id),
        "status": run.status,
        "candidate_provider": run.candidate_provider,
        "candidate_model": run.candidate_model,
        "candidate_model_version": run.candidate_model_version,
        "candidate_prompt_template_version": run.candidate_prompt_template_version,
        "metrics": run.aggregate_metrics or {},
        "threshold_snapshot": run.threshold_snapshot or {},
    }
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="BenchmarkRegressionRun",
        entity_id=run.id,
        action="benchmark_gate_evaluated",
        after=result,
    )
    return result
