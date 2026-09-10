"""B6 evaluation ledger pipeline and review actions."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.execution_metadata import metadata_from_provider
from app.ai.registry import evaluation_provider_active, get_evaluation_provider
from app.ai.tracing import (
    canonical_input_hash,
    record_ai_execution,
    redacted_evaluation_response_summary,
    redacted_request_summary,
)
from app.ai.types import (
    ALL_ERROR_CODES,
    REVIEW_BLOCKING_ERROR_CODES,
    ProviderUnavailable,
    RubricCriterionSnapshot,
    RubricEvaluationInput,
    RubricEvaluationResult,
)
from app.core.config import Settings, get_settings
from app.db.models import (
    AnswerKeyVersion,
    AnswerRegionTranscription,
    CriterionEvaluation,
    EvaluationRun,
    PipelineJob,
    QuestionAnswerMapping,
    QuestionAnswerMappingRegion,
    QuestionEvaluation,
    QuestionVersion,
    ReviewAction,
    RubricCriterion,
    RubricVersion,
    Submission,
)
from app.services.audit import add_audit_event
from app.services.grading_access import (
    GradingAccessError,
    assert_question_evaluation_review_allowed,
)
from app.services.math_verification import verify_math

RULES_ENGINE_VERSION = "b6.0.0"


class EvaluationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _dec(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


def _snapshot_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _qe_before_snapshot(qe: QuestionEvaluation) -> dict[str, Any]:
    return {
        "workflow_state": qe.workflow_state,
        "proposed_ai_score": _dec(qe.proposed_ai_score),
        "final_human_approved_score": _dec(qe.final_human_approved_score),
        "reviewer_feedback": qe.reviewer_feedback,
        "error_codes": list(qe.error_codes or []),
        "ledger_version": qe.ledger_version,
    }


async def _leaf_questions(
    db: AsyncSession, *, tenant_id: uuid.UUID, assessment_version_id: uuid.UUID
) -> list[QuestionVersion]:
    questions = list(
        (
            await db.scalars(
                select(QuestionVersion).where(
                    QuestionVersion.tenant_id == tenant_id,
                    QuestionVersion.assessment_version_id == assessment_version_id,
                )
            )
        ).all()
    )
    parent_ids = {
        q.parent_question_version_id
        for q in questions
        if q.parent_question_version_id is not None
    }
    return [
        q
        for q in questions
        if q.id not in parent_ids and q.scoring_mode == "LEAF_SCORABLE"
    ]


async def _approved_answer_key(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    question_version_id: uuid.UUID,
) -> AnswerKeyVersion | None:
    result = await db.scalar(
        select(AnswerKeyVersion).where(
            AnswerKeyVersion.tenant_id == tenant_id,
            AnswerKeyVersion.assessment_version_id == assessment_version_id,
            AnswerKeyVersion.question_version_id == question_version_id,
            AnswerKeyVersion.status == "APPROVED",
        )
    )
    return result if isinstance(result, AnswerKeyVersion) else None


async def _approved_rubric(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    question_version_id: uuid.UUID,
) -> RubricVersion | None:
    result = await db.scalar(
        select(RubricVersion).where(
            RubricVersion.tenant_id == tenant_id,
            RubricVersion.question_version_id == question_version_id,
            RubricVersion.status == "APPROVED",
        )
    )
    return result if isinstance(result, RubricVersion) else None


async def _active_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, submission_id: uuid.UUID
) -> EvaluationRun | None:
    result = await db.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.tenant_id == tenant_id,
            EvaluationRun.submission_id == submission_id,
            EvaluationRun.status.in_(["QUEUED", "RUNNING"]),
        )
        .order_by(EvaluationRun.run_number.desc())
        .limit(1)
    )
    return result if isinstance(result, EvaluationRun) else None


def validate_provider_result(
    *,
    result: RubricEvaluationResult,
    criteria: list[RubricCriterion],
    max_mark: Decimal,
) -> tuple[bool, str | None, Decimal | None]:
    """Server-side validation. Returns (ok, error_code, recomputed_total)."""
    by_id = {c.id: c for c in criteria}
    seen: set[uuid.UUID] = set()
    recomputed = Decimal("0")
    any_null = False

    if result.evaluation_confidence is not None:
        if result.evaluation_confidence < 0 or result.evaluation_confidence > 1:
            return False, "OTHER_REVIEW_REQUIRED", None

    for code in result.error_codes:
        if code not in ALL_ERROR_CODES:
            return False, "OTHER_REVIEW_REQUIRED", None

    for prop in result.criterion_proposals:
        if prop.rubric_criterion_id not in by_id:
            return False, "OTHER_REVIEW_REQUIRED", None
        if prop.rubric_criterion_id in seen:
            return False, "OTHER_REVIEW_REQUIRED", None
        seen.add(prop.rubric_criterion_id)
        crit = by_id[prop.rubric_criterion_id]

        if prop.error_code is not None and prop.error_code not in ALL_ERROR_CODES:
            return False, "OTHER_REVIEW_REQUIRED", None

        if prop.proposed_marks is not None:
            if prop.proposed_marks < 0 or prop.proposed_marks > crit.max_marks:
                return False, "OTHER_REVIEW_REQUIRED", None
            recomputed += prop.proposed_marks
        else:
            any_null = True
            if prop.decision not in {"UNREADABLE", "NOT_APPLICABLE"}:
                # Null marks only for unscorable / review decisions
                if prop.decision not in {"PARTIAL", "DEDUCTED"}:
                    pass
                # PARTIAL/DEDUCTED with null marks is review-blocking — allowed but total null
                any_null = True

        if prop.ecf_source_criterion_id is not None or result.ecf_applied:
            if crit.ecf_policy == "NONE" and prop.ecf_source_criterion_id is not None:
                return False, "OTHER_REVIEW_REQUIRED", None
            if result.ecf_applied and all(c.ecf_policy == "NONE" for c in criteria):
                return False, "OTHER_REVIEW_REQUIRED", None

    if result.ecf_applied and all(c.ecf_policy == "NONE" for c in criteria):
        return False, "OTHER_REVIEW_REQUIRED", None

    if any_null or result.proposed_total is None:
        return True, None, None

    if recomputed > max_mark:
        return False, "OTHER_REVIEW_REQUIRED", None

    # Provider total must match server recompute (tolerance 0.0001)
    if abs(result.proposed_total - recomputed) > Decimal("0.0001"):
        return False, "OTHER_REVIEW_REQUIRED", None

    return True, None, recomputed


async def prepare_evaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
    actor_user_id: uuid.UUID,
    settings: Settings | None = None,
) -> tuple[EvaluationRun, PipelineJob | None]:
    settings = settings or get_settings()

    if submission.workflow_state != "READY_FOR_EVALUATION":
        raise EvaluationError(
            "INVALID_WORKFLOW_STATE",
            "Evaluation prepare requires READY_FOR_EVALUATION",
        )
    if submission.student_match_state != "CONFIRMED":
        raise EvaluationError(
            "IDENTITY_NOT_CONFIRMED",
            "Student identity must be CONFIRMED before evaluation",
        )
    if submission.transcription_state != "READY":
        raise EvaluationError(
            "TRANSCRIPTION_NOT_READY",
            "Transcription must be READY before evaluation",
        )

    active = await _active_run(db, tenant_id=tenant_id, submission_id=submission.id)
    if active is not None:
        job = await db.scalar(
            select(PipelineJob)
            .where(
                PipelineJob.tenant_id == tenant_id,
                PipelineJob.submission_id == submission.id,
                PipelineJob.stage == "EVALUATION",
            )
            .order_by(PipelineJob.created_at.desc())
            .limit(1)
        )
        return active, job

    # Serialize concurrent prepares for the same submission (React Strict Mode / double click).
    locked = await db.scalar(
        select(Submission)
        .where(
            Submission.id == submission.id,
            Submission.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    if locked is None:
        raise EvaluationError("NOT_FOUND", "Submission not found")
    submission = locked
    if submission.workflow_state != "READY_FOR_EVALUATION":
        active = await _active_run(db, tenant_id=tenant_id, submission_id=submission.id)
        if active is not None:
            job = await db.scalar(
                select(PipelineJob)
                .where(
                    PipelineJob.tenant_id == tenant_id,
                    PipelineJob.submission_id == submission.id,
                    PipelineJob.stage == "EVALUATION",
                )
                .order_by(PipelineJob.created_at.desc())
                .limit(1)
            )
            return active, job
        raise EvaluationError(
            "INVALID_WORKFLOW_STATE",
            "Evaluation prepare requires READY_FOR_EVALUATION",
        )
    active = await _active_run(db, tenant_id=tenant_id, submission_id=submission.id)
    if active is not None:
        job = await db.scalar(
            select(PipelineJob)
            .where(
                PipelineJob.tenant_id == tenant_id,
                PipelineJob.submission_id == submission.id,
                PipelineJob.stage == "EVALUATION",
            )
            .order_by(PipelineJob.created_at.desc())
            .limit(1)
        )
        return active, job

    leaves = await _leaf_questions(
        db,
        tenant_id=tenant_id,
        assessment_version_id=submission.assessment_version_id,
    )
    if not leaves:
        raise EvaluationError(
            "NO_LEAF_QUESTIONS",
            "Assessment version has no LEAF_SCORABLE questions",
        )

    for leaf in leaves:
        mapping = await db.scalar(
            select(QuestionAnswerMapping).where(
                QuestionAnswerMapping.tenant_id == tenant_id,
                QuestionAnswerMapping.submission_id == submission.id,
                QuestionAnswerMapping.question_version_id == leaf.id,
                QuestionAnswerMapping.mapping_state == "CONFIRMED",
            )
        )
        if mapping is None:
            raise EvaluationError(
                "MAPPING_INCOMPLETE",
                f"Leaf {leaf.display_label} lacks a CONFIRMED mapping",
            )
        akv = await _approved_answer_key(
            db,
            tenant_id=tenant_id,
            assessment_version_id=submission.assessment_version_id,
            question_version_id=leaf.id,
        )
        if akv is None:
            raise EvaluationError(
                "ANSWER_KEY_MISSING",
                f"Leaf {leaf.display_label} lacks an approved answer key "
                "for the frozen assessment version",
            )
        rv = await _approved_rubric(
            db, tenant_id=tenant_id, question_version_id=leaf.id
        )
        if rv is None:
            raise EvaluationError(
                "RUBRIC_MISSING",
                f"Leaf {leaf.display_label} lacks an approved rubric",
            )

    max_run = await db.scalar(
        select(func.max(EvaluationRun.run_number)).where(
            EvaluationRun.tenant_id == tenant_id,
            EvaluationRun.submission_id == submission.id,
        )
    )
    run_number = int(max_run or 0) + 1

    provider_name = "none"
    model_name: str | None = None
    if evaluation_provider_active(settings):
        provider = get_evaluation_provider(settings)
        provider_name = provider.provider_name
        model_name = settings.ai_model_evaluation

    run = EvaluationRun(
        tenant_id=tenant_id,
        submission_id=submission.id,
        assessment_id=submission.assessment_id,
        assessment_version_id=submission.assessment_version_id,
        run_number=run_number,
        status="QUEUED",
        provider=provider_name,
        model=model_name,
        rules_engine_version=RULES_ENGINE_VERSION,
        started_by=actor_user_id,
    )
    db.add(run)
    await db.flush()

    job = PipelineJob(
        tenant_id=tenant_id,
        submission_id=submission.id,
        stage="EVALUATION",
        status="QUEUED",
        attempt=1,
        idempotency_key=f"evaluation:{submission.id}:run:{run_number}",
    )
    db.add(job)
    submission.workflow_state = "EVALUATING"
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="Submission",
        entity_id=submission.id,
        action="evaluation_prepared",
        after={
            "evaluation_run_id": str(run.id),
            "run_number": run_number,
            "provider": provider_name,
        },
    )
    await db.flush()
    return run, job


async def _load_transcription_evidence(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    mapping: QuestionAnswerMapping,
) -> tuple[list[uuid.UUID], list[dict[str, Any]], str, bool, Decimal | None]:
    """Return region_ids, transcription_refs, joined text, unreadable, min confidence."""
    links = list(
        (
            await db.scalars(
                select(QuestionAnswerMappingRegion)
                .where(
                    QuestionAnswerMappingRegion.tenant_id == tenant_id,
                    QuestionAnswerMappingRegion.mapping_id == mapping.id,
                )
                .order_by(QuestionAnswerMappingRegion.sequence)
            )
        ).all()
    )
    region_ids = [link.answer_region_id for link in links]
    texts: list[str] = []
    refs: list[dict[str, Any]] = []
    unreadable = False
    confidences: list[Decimal] = []

    for rid in region_ids:
        versions = list(
            (
                await db.scalars(
                    select(AnswerRegionTranscription)
                    .where(
                        AnswerRegionTranscription.tenant_id == tenant_id,
                        AnswerRegionTranscription.answer_region_id == rid,
                        AnswerRegionTranscription.status != "SUPERSEDED",
                    )
                    .order_by(AnswerRegionTranscription.version_number.desc())
                )
            ).all()
        )
        active = next((v for v in versions if v.status == "CONFIRMED"), None)
        if active is None and versions:
            active = versions[0]
        if active is None:
            continue
        refs.append(
            {
                "transcription_id": str(active.id),
                "answer_region_id": str(rid),
                "status": active.status,
                "unreadable": active.unreadable,
                "visual_only": active.visual_only,
            }
        )
        if active.unreadable:
            unreadable = True
        if active.text:
            texts.append(active.text)
        if active.transcription_confidence is not None:
            confidences.append(active.transcription_confidence)

    joined = "\n".join(texts)
    min_conf = min(confidences) if confidences else None
    return region_ids, refs, joined, unreadable, min_conf


def _criterion_snapshots(criteria: list[RubricCriterion]) -> list[RubricCriterionSnapshot]:
    return [
        RubricCriterionSnapshot(
            id=c.id,
            code=c.criterion_code,
            label=c.description[:255],
            max_marks=c.max_marks,
            sequence=c.sequence,
            scoring_mode=c.scoring_mode,
            partial_credit_allowed=c.partial_credit_allowed,
            ecf_policy=c.ecf_policy,
            unit_requirement=c.unit_requirement,
            precision_requirement=c.precision_requirement,
            accepted_equivalents=[str(x) for x in (c.accepted_equivalents or [])][:50],
        )
        for c in sorted(criteria, key=lambda x: x.sequence)
    ]


async def _write_criterion_rows(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    qe: QuestionEvaluation,
    criteria: list[RubricCriterion],
    proposals: list[Any],
    final_marks: bool = False,
) -> None:
    by_id = {c.id: c for c in criteria}
    for prop in proposals:
        crit = by_id[prop.rubric_criterion_id]
        marks = prop.proposed_marks
        db.add(
            CriterionEvaluation(
                tenant_id=tenant_id,
                question_evaluation_id=qe.id,
                rubric_criterion_id=crit.id,
                criterion_code=crit.criterion_code,
                criterion_label=crit.description[:255],
                max_marks=crit.max_marks,
                proposed_marks=marks,
                final_marks=marks if final_marks else None,
                decision=prop.decision,
                error_code=prop.error_code,
                deduction_reason=prop.deduction_reason,
                step_index=prop.step_index,
                ecf_source_criterion_id=prop.ecf_source_criterion_id,
            )
        )


async def _evaluate_one_leaf(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
    run: EvaluationRun,
    leaf: QuestionVersion,
    settings: Settings,
) -> None:
    mapping = await db.scalar(
        select(QuestionAnswerMapping).where(
            QuestionAnswerMapping.tenant_id == tenant_id,
            QuestionAnswerMapping.submission_id == submission.id,
            QuestionAnswerMapping.question_version_id == leaf.id,
            QuestionAnswerMapping.mapping_state == "CONFIRMED",
        )
    )
    if mapping is None:
        raise EvaluationError("MAPPING_INCOMPLETE", f"Missing mapping for {leaf.id}")

    akv = await _approved_answer_key(
        db,
        tenant_id=tenant_id,
        assessment_version_id=submission.assessment_version_id,
        question_version_id=leaf.id,
    )
    rv = await _approved_rubric(db, tenant_id=tenant_id, question_version_id=leaf.id)
    if akv is None or rv is None:
        raise EvaluationError("AUTHORING_MISSING", f"Missing AKV/RV for {leaf.id}")

    criteria = list(
        (
            await db.scalars(
                select(RubricCriterion)
                .where(
                    RubricCriterion.tenant_id == tenant_id,
                    RubricCriterion.rubric_version_id == rv.id,
                )
                .order_by(RubricCriterion.sequence)
            )
        ).all()
    )
    if not criteria:
        raise EvaluationError("RUBRIC_EMPTY", f"No criteria for rubric {rv.id}")

    region_ids, tx_refs, tx_text, unreadable, tx_conf = await _load_transcription_evidence(
        db, tenant_id=tenant_id, mapping=mapping
    )

    snapshots = _criterion_snapshots(criteria)
    qe = QuestionEvaluation(
        tenant_id=tenant_id,
        evaluation_run_id=run.id,
        submission_id=submission.id,
        student_id=submission.student_id,
        assessment_id=submission.assessment_id,
        assessment_version_id=submission.assessment_version_id,
        question_id=leaf.question_id,
        question_version_id=leaf.id,
        rubric_version_id=rv.id,
        answer_key_version_id=akv.id,
        mapping_id=mapping.id,
        answer_region_ids=[str(r) for r in region_ids],
        transcription_refs=tx_refs,
        evidence_metadata={"disposition": mapping.disposition},
        max_mark=leaf.max_marks,
        criterion_snapshot=[s.model_dump(mode="json") for s in snapshots],
        identity_confidence=submission.identity_confidence,
        mapping_confidence=mapping.mapping_confidence,
        transcription_confidence=tx_conf,
        workflow_state="PENDING",
        ledger_version=1,
    )
    db.add(qe)
    await db.flush()

    # --- BLANK disposition (rules engine) ---
    if mapping.disposition == "BLANK":
        from app.ai.types import CriterionProposal

        proposals = [
            CriterionProposal(
                rubric_criterion_id=c.id,
                decision="DEDUCTED",
                proposed_marks=Decimal("0"),
                error_code="INCOMPLETE",
                deduction_reason="Confirmed blank answer",
                step_index=c.sequence,
            )
            for c in criteria
        ]
        qe.proposed_ai_score = Decimal("0")
        qe.evaluation_confidence = Decimal("1.0000")
        qe.error_codes = ["INCOMPLETE"]
        qe.deduction_reasons = [
            {
                "criterion_id": str(c.id),
                "error_code": "INCOMPLETE",
                "reason": "Confirmed blank answer",
                "marks_deducted": float(c.max_marks),
            }
            for c in criteria
        ]
        qe.workflow_state = "PROPOSED"
        qe.ecf_applied = False
        await _write_criterion_rows(
            db, tenant_id=tenant_id, qe=qe, criteria=criteria, proposals=proposals
        )
        exec_row = await record_ai_execution(
            db,
            tenant_id=tenant_id,
            operation="evaluate_rubric",
            provider="rules",
            status="SUCCEEDED",
            request_summary=redacted_request_summary(
                operation="evaluate_rubric",
                entity_ids={
                    "submission_id": str(submission.id),
                    "question_version_id": str(leaf.id),
                    "evaluation_run_id": str(run.id),
                },
            ),
            response_summary=redacted_evaluation_response_summary(
                proposed_total=0.0,
                evaluation_confidence=1.0,
                criterion_count=len(criteria),
                error_codes=["INCOMPLETE"],
                ecf_applied=False,
                workflow_hint="BLANK",
            ),
            submission_id=submission.id,
            evaluation_run_id=run.id,
            question_evaluation_id=qe.id,
            model="rules-engine",
            model_version="B11_V1",
            prompt_template_version=RULES_ENGINE_VERSION,
            input_hash=canonical_input_hash(
                {"disposition": "BLANK", "question_version_id": str(leaf.id)}
            ),
        )
        qe.ai_execution_record_id = exec_row.id
        await db.flush()
        return

    # --- UNREADABLE ---
    if unreadable:
        from app.ai.types import CriterionProposal

        proposals = [
            CriterionProposal(
                rubric_criterion_id=c.id,
                decision="UNREADABLE",
                proposed_marks=None,
                error_code="UNREADABLE",
                step_index=c.sequence,
            )
            for c in criteria
        ]
        qe.proposed_ai_score = None
        qe.evaluation_confidence = None
        qe.error_codes = ["UNREADABLE"]
        qe.workflow_state = "REVIEW_REQUIRED"
        qe.ecf_applied = False
        await _write_criterion_rows(
            db, tenant_id=tenant_id, qe=qe, criteria=criteria, proposals=proposals
        )
        exec_row = await record_ai_execution(
            db,
            tenant_id=tenant_id,
            operation="evaluate_rubric",
            provider="rules",
            status="SUCCEEDED",
            request_summary=redacted_request_summary(
                operation="evaluate_rubric",
                entity_ids={
                    "submission_id": str(submission.id),
                    "question_version_id": str(leaf.id),
                    "evaluation_run_id": str(run.id),
                },
            ),
            response_summary=redacted_evaluation_response_summary(
                proposed_total=None,
                evaluation_confidence=None,
                criterion_count=len(criteria),
                error_codes=["UNREADABLE"],
                ecf_applied=False,
                workflow_hint="UNREADABLE",
            ),
            submission_id=submission.id,
            evaluation_run_id=run.id,
            question_evaluation_id=qe.id,
            model="rules-engine",
            model_version="B11_V1",
            prompt_template_version=RULES_ENGINE_VERSION,
            input_hash=canonical_input_hash(
                {"unreadable": True, "question_version_id": str(leaf.id)}
            ),
        )
        qe.ai_execution_record_id = exec_row.id
        await db.flush()
        return

    # --- Math verify (optional) then AI evaluate ---
    structured = akv.structured_answer if isinstance(akv.structured_answer, dict) else None
    expected_expr = None
    if structured:
        expected_expr = structured.get("expression") or structured.get("expected_expression")
    student_expr = tx_text.strip() or None
    math_result = verify_math(
        student_expr=student_expr if expected_expr else None,
        expected_expr=str(expected_expr) if expected_expr else None,
        structured_answer=structured,
    )
    qe.math_verification_confidence = math_result.math_verification_confidence
    math_summary = math_result.model_dump(mode="json")

    eval_input = RubricEvaluationInput(
        question_version_id=leaf.id,
        assessment_version_id=submission.assessment_version_id,
        rubric_criteria=snapshots,
        answer_key_text=akv.answer_text or "",
        structured_answer=structured,
        transcription_text=tx_text,
        blank_flag=False,
        unreadable_flag=False,
        math_verification_summary=math_summary,
        max_mark=leaf.max_marks,
    )

    started = datetime.now(UTC)
    provider_name = "none"
    status = "SUCCEEDED"
    error_class: str | None = None
    result: RubricEvaluationResult | None = None
    provider = None

    try:
        if not evaluation_provider_active(settings):
            raise ProviderUnavailable("AI_PROVIDER_VISION=none")
        provider = get_evaluation_provider(settings)
        provider_name = provider.provider_name
        result = await provider.evaluate_rubric(eval_input)
    except ProviderUnavailable as exc:
        status = "UNAVAILABLE"
        error_class = "PROVIDER_UNAVAILABLE"
        qe.proposed_ai_score = None
        qe.evaluation_confidence = None
        qe.error_codes = ["OTHER_REVIEW_REQUIRED"]
        qe.workflow_state = "REVIEW_REQUIRED"
        qe.evidence_metadata = {
            **(qe.evidence_metadata or {}),
            "provider_error": str(exc),
        }
        from app.ai.types import CriterionProposal

        proposals = [
            CriterionProposal(
                rubric_criterion_id=c.id,
                decision="UNREADABLE",
                proposed_marks=None,
                error_code="OTHER_REVIEW_REQUIRED",
                step_index=c.sequence,
            )
            for c in criteria
        ]
        await _write_criterion_rows(
            db, tenant_id=tenant_id, qe=qe, criteria=criteria, proposals=proposals
        )
    except Exception as exc:  # noqa: BLE001 — isolate per-question failures
        status = "FAILED"
        error_class = type(exc).__name__
        qe.proposed_ai_score = None
        qe.evaluation_confidence = None
        qe.error_codes = ["OTHER_REVIEW_REQUIRED"]
        qe.workflow_state = "REVIEW_REQUIRED"
        qe.evidence_metadata = {
            **(qe.evidence_metadata or {}),
            "evaluation_error": error_class,
        }
        from app.ai.types import CriterionProposal

        proposals = [
            CriterionProposal(
                rubric_criterion_id=c.id,
                decision="UNREADABLE",
                proposed_marks=None,
                error_code="OTHER_REVIEW_REQUIRED",
                step_index=c.sequence,
            )
            for c in criteria
        ]
        await _write_criterion_rows(
            db, tenant_id=tenant_id, qe=qe, criteria=criteria, proposals=proposals
        )
    else:
        assert result is not None
        ok, _rej, recomputed = validate_provider_result(
            result=result, criteria=criteria, max_mark=leaf.max_marks
        )
        if not ok:
            status = "FAILED"
            error_class = "INVALID_PROVIDER_OUTPUT"
            qe.proposed_ai_score = None
            qe.evaluation_confidence = None
            qe.error_codes = ["OTHER_REVIEW_REQUIRED"]
            qe.workflow_state = "REVIEW_REQUIRED"
            from app.ai.types import CriterionProposal

            proposals = [
                CriterionProposal(
                    rubric_criterion_id=c.id,
                    decision="UNREADABLE",
                    proposed_marks=None,
                    error_code="OTHER_REVIEW_REQUIRED",
                    step_index=c.sequence,
                )
                for c in criteria
            ]
            await _write_criterion_rows(
                db, tenant_id=tenant_id, qe=qe, criteria=criteria, proposals=proposals
            )
        else:
            qe.proposed_ai_score = recomputed
            qe.evaluation_confidence = result.evaluation_confidence
            qe.first_divergence_step = result.first_divergence_step
            qe.ecf_applied = result.ecf_applied
            qe.alternative_method_id = result.alternative_method_id
            qe.alternative_method_label = result.alternative_method_label
            qe.error_codes = list(result.error_codes)
            qe.deduction_reasons = list(result.deduction_reasons)
            blocking = bool(set(result.error_codes) & REVIEW_BLOCKING_ERROR_CODES)
            if recomputed is None or blocking or result.evaluation_confidence is None:
                qe.workflow_state = "REVIEW_REQUIRED"
            else:
                qe.workflow_state = "PROPOSED"
            await _write_criterion_rows(
                db,
                tenant_id=tenant_id,
                qe=qe,
                criteria=criteria,
                proposals=result.criterion_proposals,
            )

    finished = datetime.now(UTC)
    latency = int((finished - started).total_seconds() * 1000)
    meta_kwargs: dict[str, str] = {}
    if provider is not None:
        meta_kwargs = metadata_from_provider(provider, "evaluate_rubric").as_record_kwargs()
    exec_row = await record_ai_execution(
        db,
        tenant_id=tenant_id,
        operation="evaluate_rubric",
        provider=meta_kwargs.get("provider", provider_name),
        status=status,
        request_summary=redacted_request_summary(
            operation="evaluate_rubric",
            entity_ids={
                "submission_id": str(submission.id),
                "question_version_id": str(leaf.id),
                "evaluation_run_id": str(run.id),
            },
            input_refs={"answer_key_version_id": str(akv.id), "rubric_version_id": str(rv.id)},
        ),
        response_summary=redacted_evaluation_response_summary(
            proposed_total=_dec(qe.proposed_ai_score),
            evaluation_confidence=_dec(qe.evaluation_confidence),
            criterion_count=len(criteria),
            error_codes=list(qe.error_codes or []),
            ecf_applied=qe.ecf_applied,
            workflow_hint=qe.workflow_state,
        ),
        submission_id=submission.id,
        evaluation_run_id=run.id,
        question_evaluation_id=qe.id,
        model=meta_kwargs.get("model"),
        model_version=meta_kwargs.get("model_version"),
        prompt_template_version=meta_kwargs.get("prompt_template_version"),
        input_hash=canonical_input_hash(eval_input.model_dump(mode="json")),
        latency_ms=latency,
        error_class=error_class,
        started_at=started,
        finished_at=finished,
    )
    qe.ai_execution_record_id = exec_row.id
    await db.flush()


async def run_evaluation_pipeline(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
    job_id: uuid.UUID,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    job = await db.scalar(
        select(PipelineJob).where(
            PipelineJob.id == job_id,
            PipelineJob.tenant_id == tenant_id,
        )
    )
    if job is None:
        raise EvaluationError("JOB_NOT_FOUND", "Pipeline job not found")

    submission = await db.scalar(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.tenant_id == tenant_id,
        )
    )
    if submission is None:
        raise EvaluationError("SUBMISSION_NOT_FOUND", "Submission not found")

    run = await db.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.tenant_id == tenant_id,
            EvaluationRun.submission_id == submission_id,
            EvaluationRun.status.in_(["QUEUED", "RUNNING"]),
        )
        .order_by(EvaluationRun.run_number.desc())
        .limit(1)
    )
    if run is None:
        raise EvaluationError("RUN_NOT_FOUND", "No active evaluation run")

    job.status = "RUNNING"
    job.started_at = datetime.now(UTC)
    run.status = "RUNNING"
    run.started_at = datetime.now(UTC)
    await db.flush()

    leaves = await _leaf_questions(
        db,
        tenant_id=tenant_id,
        assessment_version_id=submission.assessment_version_id,
    )
    run_id = run.id

    try:
        for leaf in leaves:
            try:
                await _evaluate_one_leaf(
                    db,
                    tenant_id=tenant_id,
                    submission=submission,
                    run=run,
                    leaf=leaf,
                    settings=settings,
                )
            except Exception as exc:  # noqa: BLE001 — isolate per-question
                # Create a review-required stub if leaf write failed early
                existing = await db.scalar(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.tenant_id == tenant_id,
                        QuestionEvaluation.evaluation_run_id == run.id,
                        QuestionEvaluation.question_version_id == leaf.id,
                    )
                )
                if existing is None:
                    akv = await _approved_answer_key(
                        db,
                        tenant_id=tenant_id,
                        assessment_version_id=submission.assessment_version_id,
                        question_version_id=leaf.id,
                    )
                    rv = await _approved_rubric(
                        db, tenant_id=tenant_id, question_version_id=leaf.id
                    )
                    if akv and rv:
                        db.add(
                            QuestionEvaluation(
                                tenant_id=tenant_id,
                                evaluation_run_id=run.id,
                                submission_id=submission.id,
                                student_id=submission.student_id,
                                assessment_id=submission.assessment_id,
                                assessment_version_id=submission.assessment_version_id,
                                question_id=leaf.question_id,
                                question_version_id=leaf.id,
                                rubric_version_id=rv.id,
                                answer_key_version_id=akv.id,
                                max_mark=leaf.max_marks,
                                proposed_ai_score=None,
                                error_codes=["OTHER_REVIEW_REQUIRED"],
                                workflow_state="REVIEW_REQUIRED",
                                evidence_metadata={"isolated_error": type(exc).__name__},
                            )
                        )
                await db.flush()

        submission.workflow_state = "EVALUATION_REVIEW"
        run.status = "REVIEW_REQUIRED"
        run.finished_at = datetime.now(UTC)
        job.status = "SUCCEEDED"
        job.finished_at = datetime.now(UTC)
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=run.started_by,
            entity_type="EvaluationRun",
            entity_id=run.id,
            action="evaluation_pipeline_succeeded",
            after={"submission_id": str(submission.id)},
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        job_row = await db.scalar(select(PipelineJob).where(PipelineJob.id == job_id))
        run_row = await db.scalar(select(EvaluationRun).where(EvaluationRun.id == run_id))
        sub_row = await db.scalar(
            select(Submission).where(Submission.id == submission_id)
        )
        if job_row is not None:
            job_row.status = "FAILED"
            job_row.error_code = type(exc).__name__[:100]
            job_row.error_detail = str(exc)[:4000]
            job_row.finished_at = datetime.now(UTC)
        if run_row is not None:
            run_row.status = "FAILED"
            run_row.failure_code = type(exc).__name__[:100]
            run_row.failure_detail = str(exc)[:4000]
            run_row.finished_at = datetime.now(UTC)
        if sub_row is not None and sub_row.workflow_state == "EVALUATING":
            sub_row.workflow_state = "EVALUATION_REVIEW"
        await db.commit()
        raise


def _dump_criterion(row: CriterionEvaluation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "rubric_criterion_id": str(row.rubric_criterion_id),
        "criterion_code": row.criterion_code,
        "criterion_label": row.criterion_label,
        "max_marks": float(row.max_marks),
        "proposed_marks": _dec(row.proposed_marks),
        "final_marks": _dec(row.final_marks),
        "decision": row.decision,
        "error_code": row.error_code,
        "deduction_reason": row.deduction_reason,
        "step_index": row.step_index,
        "ecf_source_criterion_id": (
            str(row.ecf_source_criterion_id) if row.ecf_source_criterion_id else None
        ),
    }


def _dump_question_evaluation(
    qe: QuestionEvaluation, criteria: list[CriterionEvaluation]
) -> dict[str, Any]:
    return {
        "id": str(qe.id),
        "evaluation_run_id": str(qe.evaluation_run_id),
        "submission_id": str(qe.submission_id),
        "student_id": str(qe.student_id) if qe.student_id else None,
        "assessment_id": str(qe.assessment_id),
        "assessment_version_id": str(qe.assessment_version_id),
        "question_id": str(qe.question_id),
        "question_version_id": str(qe.question_version_id),
        "rubric_version_id": str(qe.rubric_version_id),
        "answer_key_version_id": str(qe.answer_key_version_id),
        "mapping_id": str(qe.mapping_id) if qe.mapping_id else None,
        "answer_region_ids": qe.answer_region_ids or [],
        "transcription_refs": qe.transcription_refs or [],
        "max_mark": float(qe.max_mark),
        "proposed_ai_score": _dec(qe.proposed_ai_score),
        "final_human_approved_score": _dec(qe.final_human_approved_score),
        "first_divergence_step": qe.first_divergence_step,
        "ecf_applied": qe.ecf_applied,
        "ecf_chain": qe.ecf_chain or {},
        "alternative_method_id": qe.alternative_method_id,
        "alternative_method_label": qe.alternative_method_label,
        "error_codes": qe.error_codes or [],
        "deduction_reasons": qe.deduction_reasons or [],
        "criterion_snapshot": qe.criterion_snapshot or [],
        "criterion_decisions": [_dump_criterion(c) for c in criteria],
        "identity_confidence": _dec(qe.identity_confidence),
        "mapping_confidence": _dec(qe.mapping_confidence),
        "transcription_confidence": _dec(qe.transcription_confidence),
        "evaluation_confidence": _dec(qe.evaluation_confidence),
        "math_verification_confidence": _dec(qe.math_verification_confidence),
        "workflow_state": qe.workflow_state,
        "ledger_version": qe.ledger_version,
        "reviewed_by": str(qe.reviewed_by) if qe.reviewed_by else None,
        "reviewed_at": qe.reviewed_at.isoformat() if qe.reviewed_at else None,
        "reviewer_feedback": qe.reviewer_feedback,
        "approved_snapshot_hash": qe.approved_snapshot_hash,
    }


def _dump_run(run: EvaluationRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "submission_id": str(run.submission_id),
        "assessment_id": str(run.assessment_id),
        "assessment_version_id": str(run.assessment_version_id),
        "run_number": run.run_number,
        "run_kind": run.run_kind,
        "supersedes_run_id": (
            str(run.supersedes_run_id) if run.supersedes_run_id else None
        ),
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "rules_engine_version": run.rules_engine_version,
        "started_by": str(run.started_by) if run.started_by else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "failure_code": run.failure_code,
        "failure_detail": run.failure_detail,
    }


async def build_evaluation_workspace(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
) -> dict[str, Any]:
    run = await db.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.tenant_id == tenant_id,
            EvaluationRun.submission_id == submission.id,
        )
        .order_by(EvaluationRun.run_number.desc())
        .limit(1)
    )
    questions: list[dict[str, Any]] = []
    if run is not None:
        qes = list(
            (
                await db.scalars(
                    select(QuestionEvaluation).where(
                        QuestionEvaluation.tenant_id == tenant_id,
                        QuestionEvaluation.evaluation_run_id == run.id,
                    )
                )
            ).all()
        )
        for qe in qes:
            criteria = list(
                (
                    await db.scalars(
                        select(CriterionEvaluation)
                        .where(
                            CriterionEvaluation.tenant_id == tenant_id,
                            CriterionEvaluation.question_evaluation_id == qe.id,
                        )
                        .order_by(CriterionEvaluation.step_index.nulls_last())
                    )
                ).all()
            )
            questions.append(_dump_question_evaluation(qe, criteria))

    return {
        "submission_id": str(submission.id),
        "workflow_state": submission.workflow_state,
        "student_match_state": submission.student_match_state,
        "transcription_state": submission.transcription_state,
        "assessment_version_id": str(submission.assessment_version_id),
        "evaluation_run": _dump_run(run) if run else None,
        "question_evaluations": questions,
        "automated_evaluation_active": evaluation_provider_active(),
    }


async def get_evaluation_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    run = await db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.tenant_id == tenant_id,
        )
    )
    if run is None:
        raise EvaluationError("NOT_FOUND", "Evaluation run not found")
    qes = list(
        (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id == run.id,
                )
            )
        ).all()
    )
    items = []
    for qe in qes:
        criteria = list(
            (
                await db.scalars(
                    select(CriterionEvaluation).where(
                        CriterionEvaluation.tenant_id == tenant_id,
                        CriterionEvaluation.question_evaluation_id == qe.id,
                    )
                )
            ).all()
        )
        items.append(_dump_question_evaluation(qe, criteria))
    return {**_dump_run(run), "question_evaluations": items}


async def get_question_evaluation(
    db: AsyncSession, *, tenant_id: uuid.UUID, qe_id: uuid.UUID
) -> dict[str, Any]:
    qe = await db.scalar(
        select(QuestionEvaluation).where(
            QuestionEvaluation.id == qe_id,
            QuestionEvaluation.tenant_id == tenant_id,
        )
    )
    if qe is None:
        raise EvaluationError("NOT_FOUND", "Question evaluation not found")
    criteria = list(
        (
            await db.scalars(
                select(CriterionEvaluation).where(
                    CriterionEvaluation.tenant_id == tenant_id,
                    CriterionEvaluation.question_evaluation_id == qe.id,
                )
            )
        ).all()
    )
    return _dump_question_evaluation(qe, criteria)


async def _enforce_grading_ownership(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    qe: QuestionEvaluation,
    actor_roles: frozenset[str] | None,
    actor_permissions: frozenset[str] | None,
) -> None:
    try:
        await assert_question_evaluation_review_allowed(
            db,
            tenant_id=tenant_id,
            question_evaluation_id=qe.id,
            actor_user_id=user_id,
            actor_roles=actor_roles or frozenset(),
            actor_permissions=actor_permissions or frozenset(),
        )
    except GradingAccessError as exc:
        raise EvaluationError(exc.code, exc.message) from exc


async def accept_question_evaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    qe: QuestionEvaluation,
    actor_roles: frozenset[str] | None = None,
    actor_permissions: frozenset[str] | None = None,
) -> QuestionEvaluation:
    if qe.tenant_id != tenant_id:
        raise EvaluationError("NOT_FOUND", "Question evaluation not found")
    await _enforce_grading_ownership(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        qe=qe,
        actor_roles=actor_roles,
        actor_permissions=actor_permissions,
    )
    if qe.proposed_ai_score is None:
        raise EvaluationError(
            "NO_PROPOSAL",
            "Cannot accept a question evaluation with null proposed_ai_score",
        )
    if qe.workflow_state in {"ACCEPTED", "OVERRIDDEN"}:
        raise EvaluationError("ALREADY_REVIEWED", "Question evaluation already reviewed")
    if qe.workflow_state == "ESCALATED":
        raise EvaluationError("ESCALATED", "Escalated evaluations cannot be accepted")

    before = _qe_before_snapshot(qe)
    qe.final_human_approved_score = qe.proposed_ai_score
    qe.workflow_state = "ACCEPTED"
    qe.reviewed_by = user_id
    qe.reviewed_at = datetime.now(UTC)

    criteria = list(
        (
            await db.scalars(
                select(CriterionEvaluation).where(
                    CriterionEvaluation.question_evaluation_id == qe.id
                )
            )
        ).all()
    )
    for c in criteria:
        c.final_marks = c.proposed_marks

    after = _qe_before_snapshot(qe)
    qe.approved_snapshot_hash = _snapshot_hash(
        {**after, "criterion_decisions": [_dump_criterion(c) for c in criteria]}
    )
    db.add(
        ReviewAction(
            tenant_id=tenant_id,
            submission_id=qe.submission_id,
            question_evaluation_id=qe.id,
            evaluation_run_id=qe.evaluation_run_id,
            actor_user_id=user_id,
            action_type="ACCEPT",
            reason=None,
            before_snapshot=before,
            after_snapshot=after,
            previous_score=None,
            new_score=qe.final_human_approved_score,
        )
    )
    await db.flush()
    return qe


async def override_question_evaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    qe: QuestionEvaluation,
    score: Decimal,
    reason: str,
    feedback: str | None = None,
    criterion_finals: list[dict[str, Any]] | None = None,
    valid_alternative: bool = False,
    actor_roles: frozenset[str] | None = None,
    actor_permissions: frozenset[str] | None = None,
) -> QuestionEvaluation:
    if qe.tenant_id != tenant_id:
        raise EvaluationError("NOT_FOUND", "Question evaluation not found")
    await _enforce_grading_ownership(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        qe=qe,
        actor_roles=actor_roles,
        actor_permissions=actor_permissions,
    )
    if not reason or not reason.strip():
        raise EvaluationError("REASON_REQUIRED", "Override reason is required")
    if score < 0 or score > qe.max_mark:
        raise EvaluationError("SCORE_OUT_OF_RANGE", "Score must be between 0 and max_mark")
    if qe.workflow_state == "ESCALATED":
        raise EvaluationError("ESCALATED", "Escalated evaluations cannot be overridden here")

    before = _qe_before_snapshot(qe)
    previous = qe.final_human_approved_score
    # Preserve AI proposal; set human final
    qe.final_human_approved_score = score
    qe.workflow_state = "OVERRIDDEN"
    qe.reviewed_by = user_id
    qe.reviewed_at = datetime.now(UTC)
    qe.reviewer_feedback = (feedback or reason).strip()
    qe.ledger_version = int(qe.ledger_version or 1) + 1
    if valid_alternative:
        codes = list(qe.error_codes or [])
        if "VALID_ALTERNATIVE" not in codes:
            codes.append("VALID_ALTERNATIVE")
        qe.error_codes = codes

    criteria = (
        await db.scalars(
            select(CriterionEvaluation).where(
                CriterionEvaluation.tenant_id == tenant_id,
                CriterionEvaluation.question_evaluation_id == qe.id,
            )
        )
    ).all()
    if criterion_finals:
        by_id = {c.rubric_criterion_id: c for c in criteria}
        total = Decimal("0")
        for item in criterion_finals:
            cid = item["rubric_criterion_id"]
            marks = Decimal(str(item["final_marks"]))
            row = by_id.get(cid)
            if row is None:
                raise EvaluationError("FOREIGN_CRITERION", "Unknown rubric criterion")
            if marks > row.max_marks:
                raise EvaluationError(
                    "CRITERION_OVER_MAX",
                    "Criterion final marks exceed maximum",
                )
            row.final_marks = marks
            total += marks
        if total != score:
            raise EvaluationError(
                "CRITERION_TOTAL_MISMATCH",
                "Criterion finals must reconcile to the question score",
            )
    else:
        # Proportional fallback when only question score is supplied.
        prop_total = sum((c.proposed_marks or Decimal("0")) for c in criteria)
        if criteria and prop_total > 0:
            remaining = score
            for idx, c in enumerate(criteria):
                if idx == len(criteria) - 1:
                    c.final_marks = remaining
                else:
                    share = (score * (c.proposed_marks or Decimal("0")) / prop_total).quantize(
                        Decimal("0.0001")
                    )
                    c.final_marks = min(share, c.max_marks)
                    remaining -= c.final_marks
        elif len(criteria) == 1:
            criteria[0].final_marks = score

    after = _qe_before_snapshot(qe)
    qe.approved_snapshot_hash = _snapshot_hash(after)
    action_type = "VALID_ALTERNATIVE" if valid_alternative else "OVERRIDE"
    db.add(
        ReviewAction(
            tenant_id=tenant_id,
            submission_id=qe.submission_id,
            question_evaluation_id=qe.id,
            evaluation_run_id=qe.evaluation_run_id,
            actor_user_id=user_id,
            action_type=action_type,
            reason=reason.strip(),
            before_snapshot=before,
            after_snapshot=after,
            previous_score=previous,
            new_score=score,
        )
    )
    await db.flush()
    return qe


async def feedback_question_evaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    qe: QuestionEvaluation,
    feedback: str,
    actor_roles: frozenset[str] | None = None,
    actor_permissions: frozenset[str] | None = None,
) -> QuestionEvaluation:
    if qe.tenant_id != tenant_id:
        raise EvaluationError("NOT_FOUND", "Question evaluation not found")
    await _enforce_grading_ownership(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        qe=qe,
        actor_roles=actor_roles,
        actor_permissions=actor_permissions,
    )
    if not feedback or not feedback.strip():
        raise EvaluationError("FEEDBACK_REQUIRED", "Feedback text is required")

    before = _qe_before_snapshot(qe)
    qe.reviewer_feedback = feedback.strip()
    after = _qe_before_snapshot(qe)
    db.add(
        ReviewAction(
            tenant_id=tenant_id,
            submission_id=qe.submission_id,
            question_evaluation_id=qe.id,
            evaluation_run_id=qe.evaluation_run_id,
            actor_user_id=user_id,
            action_type="EDIT_FEEDBACK",
            reason=feedback.strip(),
            before_snapshot=before,
            after_snapshot=after,
            previous_score=qe.final_human_approved_score,
            new_score=qe.final_human_approved_score,
        )
    )
    await db.flush()
    return qe


async def escalate_question_evaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    qe: QuestionEvaluation,
    reason: str,
    actor_roles: frozenset[str] | None = None,
    actor_permissions: frozenset[str] | None = None,
) -> QuestionEvaluation:
    if qe.tenant_id != tenant_id:
        raise EvaluationError("NOT_FOUND", "Question evaluation not found")
    await _enforce_grading_ownership(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        qe=qe,
        actor_roles=actor_roles,
        actor_permissions=actor_permissions,
    )
    if not reason or not reason.strip():
        raise EvaluationError("REASON_REQUIRED", "Escalation reason is required")

    before = _qe_before_snapshot(qe)
    qe.workflow_state = "ESCALATED"
    qe.reviewer_feedback = reason.strip()
    qe.reviewed_by = user_id
    qe.reviewed_at = datetime.now(UTC)
    after = _qe_before_snapshot(qe)
    db.add(
        ReviewAction(
            tenant_id=tenant_id,
            submission_id=qe.submission_id,
            question_evaluation_id=qe.id,
            evaluation_run_id=qe.evaluation_run_id,
            actor_user_id=user_id,
            action_type="ESCALATE",
            reason=reason.strip(),
            before_snapshot=before,
            after_snapshot=after,
            previous_score=qe.final_human_approved_score,
            new_score=qe.final_human_approved_score,
        )
    )
    await db.flush()
    return qe


async def finalize_evaluation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
    actor_user_id: uuid.UUID,
) -> Submission:
    if submission.workflow_state != "EVALUATION_REVIEW":
        raise EvaluationError(
            "INVALID_WORKFLOW_STATE",
            "Finalize requires EVALUATION_REVIEW",
        )

    run = await db.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.tenant_id == tenant_id,
            EvaluationRun.submission_id == submission.id,
        )
        .order_by(EvaluationRun.run_number.desc())
        .limit(1)
    )
    if run is None:
        raise EvaluationError("RUN_NOT_FOUND", "No evaluation run found")

    leaves = await _leaf_questions(
        db,
        tenant_id=tenant_id,
        assessment_version_id=submission.assessment_version_id,
    )
    qes = list(
        (
            await db.scalars(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id == run.id,
                )
            )
        ).all()
    )
    by_qv = {qe.question_version_id: qe for qe in qes}
    for leaf in leaves:
        qe = by_qv.get(leaf.id)
        if qe is None:
            raise EvaluationError(
                "LEDGER_INCOMPLETE",
                f"Missing ledger row for {leaf.display_label}",
            )
        if qe.workflow_state == "ESCALATED":
            raise EvaluationError(
                "ESCALATED_PENDING",
                "Cannot finalize while any question is ESCALATED",
            )
        if qe.workflow_state not in {"ACCEPTED", "OVERRIDDEN"}:
            raise EvaluationError(
                "REVIEW_INCOMPLETE",
                f"Question {leaf.display_label} is not ACCEPTED or OVERRIDDEN",
            )

    from app.services.enterprise_ops import (
        active_moderation_policy,
        ensure_moderation_case_for_run,
    )

    policy = await active_moderation_policy(
        db,
        tenant_id=tenant_id,
        assessment_version_id=submission.assessment_version_id,
    )
    if policy is not None:
        submission.workflow_state = "MODERATION_REVIEW"
        run.status = "REVIEW_REQUIRED"
        await ensure_moderation_case_for_run(
            db,
            tenant_id=tenant_id,
            policy=policy,
            submission=submission,
            run=run,
            actor_user_id=actor_user_id,
        )
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="Submission",
            entity_id=submission.id,
            action="evaluation_sent_to_moderation",
            after={
                "workflow_state": "MODERATION_REVIEW",
                "evaluation_run_id": str(run.id),
                "moderation_policy_id": str(policy.id),
            },
        )
        await db.flush()
        return submission

    submission.workflow_state = "APPROVED"
    run.status = "COMPLETED"
    run.finished_at = datetime.now(UTC)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="Submission",
        entity_id=submission.id,
        action="evaluation_finalized",
        after={
            "workflow_state": "APPROVED",
            "evaluation_run_id": str(run.id),
        },
    )
    await db.flush()
    return submission
