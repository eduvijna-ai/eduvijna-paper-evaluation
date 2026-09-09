"""B7 publication: approved-ledger freeze, annotated PDF, and audience reports."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.execution_metadata import metadata_from_provider
from app.ai.registry import get_narrative_provider
from app.ai.tracing import canonical_input_hash, record_ai_execution, redacted_request_summary
from app.ai.types import (
    ParentNarrativeInput,
    ParentNarrativeResult,
    ProviderUnavailable,
    StudentNarrativeInput,
    StudentNarrativeQuestionContext,
    StudentNarrativeResult,
)
from app.core.config import Settings, get_settings
from app.db.models import (
    Annotation,
    AnswerRegion,
    Assessment,
    CriterionEvaluation,
    EvaluationRun,
    PipelineJob,
    PublishedResult,
    QuestionEvaluation,
    QuestionVersion,
    ReviewAction,
    Student,
    Submission,
    SubmissionPage,
)
from app.services.audit import add_audit_event
from app.services.pdf_renderers import (
    render_evaluated_paper,
    render_parent_report_pdf,
    render_student_report_pdf,
    render_teacher_report_pdf,
)
from app.services.storage import ObjectStorage, publication_export_key

ARTIFACT_TYPES = frozenset(
    {
        "ANNOTATED_PDF",
        "STUDENT_REPORT_PDF",
        "PARENT_REPORT_PDF",
        "TEACHER_REPORT_PDF",
    }
)


class PublicationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _dec(v: Decimal | float | int | None) -> float | None:
    if v is None:
        return None
    return float(v)


def compute_ledger_snapshot_hash(canonical: dict[str, Any]) -> str:
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _performance_band(final: Decimal, max_mark: Decimal) -> Literal["full", "partial", "none"]:
    if max_mark <= 0:
        return "none"
    if final >= max_mark:
        return "full"
    if final <= 0:
        return "none"
    return "partial"


def _annotation_type_for_criterion(
    *, final: Decimal | None, max_marks: Decimal, decision: str
) -> str:
    if decision == "UNREADABLE":
        return "CROSS"
    if final is None:
        return "CROSS"
    if final <= 0:
        return "CROSS"
    if final >= max_marks:
        return "TICK"
    return "PARTIAL"


def _clamp_geom(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    x = max(0.0, min(x, 0.999))
    y = max(0.0, min(y, 0.999))
    w = max(0.01, min(w, 1.0 - x))
    h = max(0.01, min(h, 1.0 - y))
    if x + w > 1.0:
        w = 1.0 - x
    if y + h > 1.0:
        h = 1.0 - y
    return x, y, max(w, 0.01), max(h, 0.01)


async def load_approved_ledger_snapshot(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
) -> tuple[EvaluationRun, list[QuestionEvaluation], list[CriterionEvaluation], dict[str, Any]]:
    """Load COMPLETED run + ACCEPTED/OVERRIDDEN leaves with final scores only."""
    if submission.workflow_state != "APPROVED" and submission.workflow_state != "PUBLISHED":
        # prepare requires APPROVED; publish may still be APPROVED until transition
        if submission.workflow_state not in {"APPROVED"}:
            raise PublicationError(
                "INVALID_WORKFLOW_STATE",
                "Publication requires submission APPROVED",
            )

    run = await db.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.tenant_id == tenant_id,
            EvaluationRun.submission_id == submission.id,
            EvaluationRun.status == "COMPLETED",
        )
        .order_by(EvaluationRun.run_number.desc())
        .limit(1)
    )
    if run is None:
        raise PublicationError(
            "EVALUATION_RUN_MISSING",
            "No COMPLETED evaluation run found for publication",
        )

    qes = list(
        (
            await db.scalars(
                select(QuestionEvaluation)
                .where(
                    QuestionEvaluation.tenant_id == tenant_id,
                    QuestionEvaluation.evaluation_run_id == run.id,
                )
                .order_by(QuestionEvaluation.created_at.asc())
            )
        ).all()
    )
    if not qes:
        raise PublicationError("LEDGER_EMPTY", "Approved ledger has no question rows")

    criteria_all: list[CriterionEvaluation] = []
    canonical_questions: list[dict[str, Any]] = []
    for qe in qes:
        if qe.workflow_state not in {"ACCEPTED", "OVERRIDDEN"}:
            raise PublicationError(
                "LEDGER_INCOMPLETE",
                f"Question evaluation {qe.id} is not ACCEPTED or OVERRIDDEN",
            )
        if qe.final_human_approved_score is None:
            raise PublicationError(
                "FINAL_SCORE_MISSING",
                f"Question evaluation {qe.id} lacks final_human_approved_score",
            )
        criteria = list(
            (
                await db.scalars(
                    select(CriterionEvaluation)
                    .where(CriterionEvaluation.question_evaluation_id == qe.id)
                    .order_by(CriterionEvaluation.criterion_code.asc())
                )
            ).all()
        )
        criteria_all.extend(criteria)
        canonical_questions.append(
            {
                "question_evaluation_id": str(qe.id),
                "question_version_id": str(qe.question_version_id),
                "workflow_state": qe.workflow_state,
                "final_human_approved_score": str(qe.final_human_approved_score),
                "max_mark": str(qe.max_mark),
                # Never include proposed_ai_score in the publication snapshot.
                "criteria": [
                    {
                        "rubric_criterion_id": str(c.rubric_criterion_id),
                        "criterion_code": c.criterion_code,
                        "final_marks": str(c.final_marks) if c.final_marks is not None else None,
                        "max_marks": str(c.max_marks),
                        "decision": c.decision,
                    }
                    for c in criteria
                ],
            }
        )

    canonical = {
        "evaluation_run_id": str(run.id),
        "submission_id": str(submission.id),
        "assessment_version_id": str(submission.assessment_version_id),
        "questions": canonical_questions,
    }
    return run, qes, criteria_all, canonical


def reconcile_totals(
    qes: list[QuestionEvaluation],
) -> tuple[Decimal, Decimal]:
    total = sum((qe.final_human_approved_score or Decimal("0") for qe in qes), Decimal("0"))
    max_total = sum((qe.max_mark for qe in qes), Decimal("0"))
    leaf_sum = sum((qe.final_human_approved_score or Decimal("0") for qe in qes), Decimal("0"))
    if leaf_sum != total:
        raise PublicationError("TOTAL_MISMATCH", "Leaf final scores do not sum to total")
    if total < 0 or (max_total > 0 and total > max_total):
        raise PublicationError(
            "TOTAL_OUT_OF_RANGE",
            "Total score must be between 0 and assessment max",
        )
    return total, max_total


def _rules_student_narrative(
    *,
    assessment_title: str,
    questions: list[StudentNarrativeQuestionContext],
) -> StudentNarrativeResult:
    strengths = [
        f"Completed work on {q.question_code}." for q in questions if q.performance_band == "full"
    ] or ["Keep practicing clear solution structure."]
    improvements = [
        f"Review {q.question_code}." for q in questions if q.performance_band != "full"
    ] or ["Maintain accuracy on timed work."]
    return StudentNarrativeResult(
        strengths=strengths[:10],
        areas_for_improvement=improvements[:10],
        next_steps=[
            f"Review feedback for {assessment_title}.",
            "Practice similar problems.",
        ],
        question_narratives=[],
    )


def _rules_parent_narrative(
    *,
    student_display_name: str,
    assessment_title: str,
    overview: str,
) -> ParentNarrativeResult:
    return ParentNarrativeResult(
        what_went_well=[f"{student_display_name} completed {assessment_title}."],
        what_to_practice=["Review questions that need more practice."],
        how_family_can_help=["Ask your child to explain one problem aloud."],
        next_step="Encourage short, regular practice sessions.",
        score_summary=f"Summary for {student_display_name} ({overview}).",
    )


def validate_report_payload(kind: str, payload: dict[str, Any]) -> None:
    """Lightweight shape validation aligned with contracts schemas."""
    required_common = [
        "published_result_id",
        "ledger_snapshot_hash",
        "total_score",
        "max_total_score",
    ]
    for key in required_common:
        if key not in payload:
            raise PublicationError("INVALID_REPORT_PAYLOAD", f"Missing {key} in {kind} report")
    if kind == "student":
        for key in (
            "student",
            "assessment",
            "percentage",
            "questions",
            "strengths",
            "areas_for_improvement",
            "next_steps",
            "narrative_source",
        ):
            if key not in payload:
                raise PublicationError("INVALID_REPORT_PAYLOAD", f"Missing {key} in student report")
        for q in payload["questions"]:
            if "proposed_ai_score" in q:
                raise PublicationError(
                    "INVALID_REPORT_PAYLOAD",
                    "Student report must not include proposed_ai_score",
                )
            if "mastery" in q or "topic_focus" in q:
                raise PublicationError(
                    "INVALID_REPORT_PAYLOAD",
                    "Student report must not fabricate mastery/topic_focus",
                )
    elif kind == "parent":
        for key in (
            "student_display_name",
            "assessment_title",
            "percentage",
            "what_went_well",
            "what_to_practice",
            "how_family_can_help",
            "next_step",
            "narrative_source",
        ):
            if key not in payload:
                raise PublicationError("INVALID_REPORT_PAYLOAD", f"Missing {key} in parent report")
    elif kind == "teacher":
        for key in ("student", "assessment", "questions"):
            if key not in payload:
                raise PublicationError("INVALID_REPORT_PAYLOAD", f"Missing {key} in teacher report")
        for q in payload["questions"]:
            for req in (
                "final_score",
                "max_mark",
                "workflow_state",
                "criterion_decisions",
                "error_codes",
                "confidences",
            ):
                if req not in q:
                    raise PublicationError(
                        "INVALID_REPORT_PAYLOAD",
                        f"Teacher question missing {req}",
                    )
    else:
        raise PublicationError("INVALID_REPORT_PAYLOAD", f"Unknown report kind {kind}")


async def prepare_publication(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
    actor_user_id: uuid.UUID,
) -> tuple[PublishedResult, PipelineJob | None]:
    if submission.workflow_state != "APPROVED":
        raise PublicationError(
            "INVALID_WORKFLOW_STATE",
            "Publication prepare requires APPROVED",
        )

    run, qes, _criteria, canonical = await load_approved_ledger_snapshot(
        db, tenant_id=tenant_id, submission=submission
    )
    snapshot_hash = compute_ledger_snapshot_hash(canonical)
    total, max_total = reconcile_totals(qes)

    existing = await db.scalar(
        select(PublishedResult)
        .where(
            PublishedResult.tenant_id == tenant_id,
            PublishedResult.submission_id == submission.id,
            PublishedResult.ledger_snapshot_hash == snapshot_hash,
            PublishedResult.status.in_(["READY", "GENERATING", "GENERATED", "PUBLISHED"]),
        )
        .order_by(PublishedResult.version_number.desc())
        .limit(1)
    )
    if existing is not None:
        job = await db.scalar(
            select(PipelineJob)
            .where(
                PipelineJob.tenant_id == tenant_id,
                PipelineJob.submission_id == submission.id,
                PipelineJob.stage == "PUBLICATION",
                PipelineJob.idempotency_key
                == f"publication:{submission.id}:v{existing.version_number}",
            )
            .limit(1)
        )
        return existing, job

    max_ver = await db.scalar(
        select(func.max(PublishedResult.version_number)).where(
            PublishedResult.tenant_id == tenant_id,
            PublishedResult.submission_id == submission.id,
        )
    )
    version_number = int(max_ver or 0) + 1

    current_published = await db.scalar(
        select(PublishedResult)
        .where(
            PublishedResult.tenant_id == tenant_id,
            PublishedResult.submission_id == submission.id,
            PublishedResult.status == "PUBLISHED",
        )
        .order_by(PublishedResult.version_number.desc())
        .limit(1)
    )

    result = PublishedResult(
        tenant_id=tenant_id,
        submission_id=submission.id,
        student_id=submission.student_id,
        assessment_id=submission.assessment_id,
        assessment_version_id=submission.assessment_version_id,
        evaluation_run_id=run.id,
        version_number=version_number,
        status="READY",
        ledger_snapshot_hash=snapshot_hash,
        total_score=total,
        max_total_score=max_total,
        generated_by=actor_user_id,
        supersedes_result_id=(
            current_published.id if current_published is not None else None
        ),
    )
    db.add(result)
    await db.flush()

    job = PipelineJob(
        tenant_id=tenant_id,
        submission_id=submission.id,
        stage="PUBLICATION",
        status="QUEUED",
        attempt=1,
        idempotency_key=f"publication:{submission.id}:v{version_number}",
    )
    db.add(job)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="PublishedResult",
        entity_id=result.id,
        action="publication_prepared",
        after={
            "submission_id": str(submission.id),
            "version_number": version_number,
            "ledger_snapshot_hash": snapshot_hash,
        },
    )
    # Submission stays APPROVED until explicit publish.
    await db.flush()
    return result, job


async def _load_pages_and_regions(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
) -> tuple[list[SubmissionPage], dict[uuid.UUID, AnswerRegion]]:
    pages = list(
        (
            await db.scalars(
                select(SubmissionPage)
                .where(
                    SubmissionPage.tenant_id == tenant_id,
                    SubmissionPage.submission_id == submission_id,
                )
                .order_by(SubmissionPage.page_index.asc())
            )
        ).all()
    )
    regions = list(
        (
            await db.scalars(
                select(AnswerRegion).where(
                    AnswerRegion.tenant_id == tenant_id,
                    AnswerRegion.submission_page_id.in_([p.id for p in pages] or [uuid.uuid4()]),
                )
            )
        ).all()
    )
    return pages, {r.id: r for r in regions}


async def _create_ledger_annotations(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
    published: PublishedResult,
    qes: list[QuestionEvaluation],
    criteria_by_qe: dict[uuid.UUID, list[CriterionEvaluation]],
    regions_by_id: dict[uuid.UUID, AnswerRegion],
    pages: list[SubmissionPage],
) -> list[Annotation]:
    fallback_page = pages[0] if pages else None
    created: list[Annotation] = []

    for qe in qes:
        region_ids = [uuid.UUID(str(x)) for x in (qe.answer_region_ids or [])]
        region = None
        for rid in region_ids:
            region = regions_by_id.get(rid)
            if region is not None:
                break
        page_id = (
            region.submission_page_id if region else (fallback_page.id if fallback_page else None)
        )
        if page_id is None:
            continue

        if region is not None:
            base_x = float(region.bbox_x)
            base_y = float(region.bbox_y)
            base_w = float(region.bbox_width)
            base_h = float(region.bbox_height)
        else:
            # Deterministic fallback box when no answer region (e.g. BLANK)
            idx = len(created) % max(len(pages), 1)
            page_id = pages[idx].id if pages else page_id
            base_x, base_y, base_w, base_h = 0.05, 0.05 + 0.08 * (len(created) % 8), 0.12, 0.05

        # Question-level MARK with final score only
        mx, my, mw, mh = _clamp_geom(base_x + base_w * 0.75, base_y, 0.18, 0.06)
        mark = Annotation(
            tenant_id=tenant_id,
            submission_id=submission.id,
            submission_page_id=page_id,
            question_evaluation_id=qe.id,
            answer_region_id=region.id if region else None,
            published_result_id=published.id,
            annotation_type="MARK",
            x=mx,
            y=my,
            width=mw,
            height=mh,
            payload={
                "final_marks": _dec(qe.final_human_approved_score),
                "max_marks": _dec(qe.max_mark),
                # Explicitly never store proposed_ai_score
            },
            source_type="LEDGER",
        )
        db.add(mark)
        created.append(mark)

        for i, crit in enumerate(criteria_by_qe.get(qe.id, [])):
            atype = _annotation_type_for_criterion(
                final=crit.final_marks,
                max_marks=crit.max_marks,
                decision=crit.decision,
            )
            ox = base_x + min(0.02 * i, max(base_w - 0.05, 0))
            oy = base_y + base_h * 0.1
            cx, cy, cw, ch = _clamp_geom(ox, oy, min(0.05, base_w), min(0.05, base_h))
            ann = Annotation(
                tenant_id=tenant_id,
                submission_id=submission.id,
                submission_page_id=page_id,
                question_evaluation_id=qe.id,
                answer_region_id=region.id if region else None,
                published_result_id=published.id,
                annotation_type=atype,
                x=cx,
                y=cy,
                width=cw,
                height=ch,
                payload={
                    "final_marks": _dec(crit.final_marks),
                    "max_marks": _dec(crit.max_marks),
                    "criterion_id": str(crit.rubric_criterion_id),
                    "error_code": crit.error_code,
                    "reason": crit.deduction_reason,
                },
                source_type="LEDGER",
            )
            db.add(ann)
            created.append(ann)

    await db.flush()
    return created


def build_student_report_payload(
    *,
    published: PublishedResult,
    student: Student | None,
    assessment: Assessment,
    qes: list[QuestionEvaluation],
    qv_by_id: dict[uuid.UUID, QuestionVersion],
    narrative: StudentNarrativeResult,
    narrative_source: str,
    generated_at: datetime,
) -> dict[str, Any]:
    by_code = {n.question_code: n for n in narrative.question_narratives}
    questions_out: list[dict[str, Any]] = []
    for qe in qes:
        qv = qv_by_id.get(qe.question_version_id)
        code = qv.display_label if qv else str(qe.question_version_id)
        prose = by_code.get(code)
        questions_out.append(
            {
                "question_id": str(qe.question_id),
                "question_version_id": str(qe.question_version_id),
                "question_code": code,
                "final_score": _dec(qe.final_human_approved_score),
                "max_mark": _dec(qe.max_mark),
                "feedback": qe.reviewer_feedback,
                "error_explanations": [str(c) for c in (qe.error_codes or [])],
                "corrected_approach": prose.corrected_approach if prose else None,
                "explanation": prose.explanation if prose else None,
            }
        )
    pct = 0.0
    if published.max_total_score and published.max_total_score > 0:
        pct = float(published.total_score / published.max_total_score * 100)
    return {
        "published_result_id": str(published.id),
        "student": {
            "id": str(student.id) if student else str(published.student_id or uuid.UUID(int=0)),
            "display_name": student.full_name if student else "Unknown",
        },
        "assessment": {
            "id": str(assessment.id),
            "title": assessment.title,
            "code": assessment.code,
            "assessment_version_id": str(published.assessment_version_id),
        },
        "total_score": _dec(published.total_score),
        "max_total_score": _dec(published.max_total_score),
        "percentage": round(pct, 2),
        "questions": questions_out,
        "strengths": list(narrative.strengths),
        "areas_for_improvement": list(narrative.areas_for_improvement),
        "next_steps": list(narrative.next_steps),
        "ledger_snapshot_hash": published.ledger_snapshot_hash,
        "narrative_source": narrative_source,
        "evaluation_run_id": str(published.evaluation_run_id),
        "generated_at": generated_at.isoformat(),
        "published_at": None,
    }


def build_parent_report_payload(
    *,
    published: PublishedResult,
    student: Student | None,
    assessment: Assessment,
    narrative: ParentNarrativeResult,
    narrative_source: str,
    generated_at: datetime,
) -> dict[str, Any]:
    pct = 0.0
    if published.max_total_score and published.max_total_score > 0:
        pct = float(published.total_score / published.max_total_score * 100)
    # Scores always injected server-side from approved ledger.
    return {
        "published_result_id": str(published.id),
        "student_display_name": student.full_name if student else "Unknown",
        "assessment_title": assessment.title,
        "total_score": _dec(published.total_score),
        "max_total_score": _dec(published.max_total_score),
        "percentage": round(pct, 2),
        "score_summary": narrative.score_summary
        or (
            f"{student.full_name if student else 'Student'} scored "
            f"{published.total_score} out of {published.max_total_score}."
        ),
        "what_went_well": list(narrative.what_went_well),
        "what_to_practice": list(narrative.what_to_practice),
        "how_family_can_help": list(narrative.how_family_can_help),
        "next_step": narrative.next_step,
        "ledger_snapshot_hash": published.ledger_snapshot_hash,
        "narrative_source": narrative_source,
        "generated_at": generated_at.isoformat(),
        "published_at": None,
    }


def build_teacher_report_payload(
    *,
    published: PublishedResult,
    student: Student | None,
    assessment: Assessment,
    qes: list[QuestionEvaluation],
    qv_by_id: dict[uuid.UUID, QuestionVersion],
    criteria_by_qe: dict[uuid.UUID, list[CriterionEvaluation]],
    actions_by_qe: dict[uuid.UUID, list[ReviewAction]],
    generated_at: datetime,
) -> dict[str, Any]:
    questions_out: list[dict[str, Any]] = []
    for qe in qes:
        qv = qv_by_id.get(qe.question_version_id)
        code = qv.display_label if qv else str(qe.question_version_id)
        questions_out.append(
            {
                "question_id": str(qe.question_id),
                "question_version_id": str(qe.question_version_id),
                "question_code": code,
                "final_score": _dec(qe.final_human_approved_score),
                "max_mark": _dec(qe.max_mark),
                "workflow_state": qe.workflow_state,
                "criterion_decisions": [
                    {
                        "criterion_code": c.criterion_code,
                        "criterion_label": c.criterion_label,
                        "final_marks": _dec(c.final_marks),
                        "max_marks": _dec(c.max_marks),
                        "decision": c.decision,
                        "error_code": c.error_code,
                        "deduction_reason": c.deduction_reason,
                    }
                    for c in criteria_by_qe.get(qe.id, [])
                ],
                "error_codes": [str(c) for c in (qe.error_codes or [])],
                "deduction_reasons": [str(d) for d in (qe.deduction_reasons or [])],
                "first_divergence_step": qe.first_divergence_step,
                "ecf_applied": bool(qe.ecf_applied),
                "ecf_details": qe.ecf_chain or None,
                "alternative_method_id": qe.alternative_method_id,
                "alternative_method_label": qe.alternative_method_label,
                "review_actions": [
                    {
                        "action_type": a.action_type,
                        "reason": a.reason,
                        "previous_score": _dec(a.previous_score),
                        "new_score": _dec(a.new_score),
                        "created_at": (
                            a.created_at.isoformat() if a.created_at else generated_at.isoformat()
                        ),
                    }
                    for a in actions_by_qe.get(qe.id, [])
                ],
                "transcription_outcome": (qe.evidence_metadata or {}).get("transcription_outcome"),
                "curriculum_refs": [],
                "confidences": {
                    "identity": _dec(qe.identity_confidence),
                    "mapping": _dec(qe.mapping_confidence),
                    "transcription": _dec(qe.transcription_confidence),
                    "evaluation": _dec(qe.evaluation_confidence),
                    "math_verification": _dec(qe.math_verification_confidence),
                },
            }
        )
    return {
        "published_result_id": str(published.id),
        "student": {
            "id": str(student.id) if student else str(published.student_id or uuid.UUID(int=0)),
            "display_name": student.full_name if student else "Unknown",
        },
        "assessment": {
            "id": str(assessment.id),
            "title": assessment.title,
            "code": assessment.code,
            "assessment_version_id": str(published.assessment_version_id),
        },
        "total_score": _dec(published.total_score),
        "max_total_score": _dec(published.max_total_score),
        "questions": questions_out,
        "ledger_snapshot_hash": published.ledger_snapshot_hash,
        "evaluation_run_id": str(published.evaluation_run_id),
        "generated_at": generated_at.isoformat(),
        "published_at": None,
    }


async def run_publication_pipeline(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
    job_id: uuid.UUID,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    storage = ObjectStorage(settings)

    job = await db.scalar(
        select(PipelineJob).where(
            PipelineJob.id == job_id,
            PipelineJob.tenant_id == tenant_id,
        )
    )
    submission = await db.scalar(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.tenant_id == tenant_id,
        )
    )
    if job is None or submission is None:
        return

    published = await db.scalar(
        select(PublishedResult)
        .where(
            PublishedResult.tenant_id == tenant_id,
            PublishedResult.submission_id == submission_id,
            PublishedResult.status.in_(["READY", "GENERATING", "FAILED"]),
        )
        .order_by(PublishedResult.version_number.desc())
        .limit(1)
    )
    if published is None:
        job.status = "FAILED"
        job.error_code = "PUBLISHED_RESULT_MISSING"
        job.error_detail = "No READY published result for job"
        job.finished_at = datetime.now(UTC)
        await db.commit()
        return

    job.status = "RUNNING"
    job.started_at = datetime.now(UTC)
    published.status = "GENERATING"
    published.failure_code = None
    published.failure_detail = None
    published_id = published.id
    await db.commit()

    try:
        # 1 verify APPROVED
        if submission.workflow_state != "APPROVED":
            raise PublicationError(
                "INVALID_WORKFLOW_STATE",
                "Publication pipeline requires APPROVED submission",
            )

        # 2 freeze snapshot
        run, qes, criteria_all, canonical = await load_approved_ledger_snapshot(
            db, tenant_id=tenant_id, submission=submission
        )
        snapshot_hash = compute_ledger_snapshot_hash(canonical)
        if snapshot_hash != published.ledger_snapshot_hash:
            raise PublicationError(
                "SNAPSHOT_MISMATCH",
                "Ledger snapshot changed since prepare",
            )

        # 3 reconcile
        total, max_total = reconcile_totals(qes)
        published.total_score = total
        published.max_total_score = max_total

        criteria_by_qe: dict[uuid.UUID, list[CriterionEvaluation]] = {}
        for c in criteria_all:
            criteria_by_qe.setdefault(c.question_evaluation_id, []).append(c)

        pages, regions_by_id = await _load_pages_and_regions(
            db, tenant_id=tenant_id, submission_id=submission.id
        )
        if not pages:
            raise PublicationError("PAGES_MISSING", "Submission has no normalized pages")

        # Clear prior ledger annotations for this version (regenerate path)
        existing_anns = list(
            (
                await db.scalars(
                    select(Annotation).where(
                        Annotation.published_result_id == published.id,
                        Annotation.source_type == "LEDGER",
                    )
                )
            ).all()
        )
        for ann in existing_anns:
            await db.delete(ann)
        await db.flush()

        # 4 deterministic LEDGER annotations
        annotations = await _create_ledger_annotations(
            db,
            tenant_id=tenant_id,
            submission=submission,
            published=published,
            qes=qes,
            criteria_by_qe=criteria_by_qe,
            regions_by_id=regions_by_id,
            pages=pages,
        )

        # 5 evaluated PDF
        page_bytes: list[bytes] = []
        page_ids: list[str] = []
        for page in pages:
            if not page.image_storage_key:
                raise PublicationError(
                    "PAGE_IMAGE_MISSING",
                    f"Page {page.page_index} missing image",
                )
            page_bytes.append(storage.get_bytes(page.image_storage_key))
            page_ids.append(str(page.id))

        ann_dicts = [
            {
                "annotation_type": a.annotation_type,
                "submission_page_id": str(a.submission_page_id),
                "x": a.x,
                "y": a.y,
                "width": a.width,
                "height": a.height,
                "payload": a.payload or {},
            }
            for a in annotations
        ]
        annotated_pdf = render_evaluated_paper(page_bytes, ann_dicts, page_id_by_index=page_ids)

        # Context for reports
        assessment = await db.scalar(
            select(Assessment).where(
                Assessment.id == submission.assessment_id,
                Assessment.tenant_id == tenant_id,
            )
        )
        if assessment is None:
            raise PublicationError("ASSESSMENT_MISSING", "Assessment not found")
        student = None
        if submission.student_id:
            student = await db.scalar(
                select(Student).where(
                    Student.id == submission.student_id,
                    Student.tenant_id == tenant_id,
                )
            )
        qv_ids = [qe.question_version_id for qe in qes]
        qvs = list(
            (await db.scalars(select(QuestionVersion).where(QuestionVersion.id.in_(qv_ids)))).all()
        )
        qv_by_id = {qv.id: qv for qv in qvs}
        actions = list(
            (
                await db.scalars(
                    select(ReviewAction).where(
                        ReviewAction.tenant_id == tenant_id,
                        ReviewAction.submission_id == submission.id,
                    )
                )
            ).all()
        )
        actions_by_qe: dict[uuid.UUID, list[ReviewAction]] = {}
        for a in actions:
            actions_by_qe.setdefault(a.question_evaluation_id, []).append(a)

        # 6–7 deterministic facts + optional narrative
        generated_at = datetime.now(UTC)
        narrative_contexts = []
        for qe in qes:
            qv = qv_by_id.get(qe.question_version_id)
            code = qv.display_label if qv else str(qe.question_version_id)
            narrative_contexts.append(
                StudentNarrativeQuestionContext(
                    question_code=code,
                    feedback=qe.reviewer_feedback,
                    error_explanations=[str(c) for c in (qe.error_codes or [])],
                    performance_band=_performance_band(
                        qe.final_human_approved_score or Decimal("0"),
                        qe.max_mark,
                    ),
                )
            )
        full_count = sum(1 for c in narrative_contexts if c.performance_band == "full")
        none_count = sum(1 for c in narrative_contexts if c.performance_band == "none")
        overview: Literal["strong", "mixed", "needs_practice"]
        if full_count == len(narrative_contexts) and narrative_contexts:
            overview = "strong"
        elif none_count == len(narrative_contexts):
            overview = "needs_practice"
        else:
            overview = "mixed"

        student_input = StudentNarrativeInput(
            assessment_title=assessment.title,
            student_display_name=student.full_name if student else "Student",
            questions=narrative_contexts,
        )
        parent_input = ParentNarrativeInput(
            assessment_title=assessment.title,
            student_display_name=student.full_name if student else "Student",
            question_summaries=[c.question_code for c in narrative_contexts],
            performance_overview=overview,
        )

        narrative_source = "RULES_FALLBACK"
        student_nar = _rules_student_narrative(
            assessment_title=assessment.title, questions=narrative_contexts
        )
        parent_nar = _rules_parent_narrative(
            student_display_name=student.full_name if student else "Student",
            assessment_title=assessment.title,
            overview=overview,
        )

        provider = get_narrative_provider(settings)
        if provider is not None:
            try:
                started = datetime.now(UTC)
                student_nar = await provider.generate_student_explanation(student_input)
                parent_nar = await provider.generate_parent_summary(parent_input)
                finished = datetime.now(UTC)
                narrative_source = "FIXED" if provider.provider_name == "fixed" else "AI"
                meta = metadata_from_provider(provider, "generate_student_explanation")
                await record_ai_execution(
                    db,
                    tenant_id=tenant_id,
                    operation="generate_student_explanation",
                    status="SUCCEEDED",
                    request_summary=redacted_request_summary(
                        operation="generate_student_explanation",
                        entity_ids={
                            "submission_id": str(submission.id),
                            "published_result_id": str(published.id),
                        },
                    ),
                    response_summary={
                        "strengths_count": len(student_nar.strengths),
                        "questions": len(student_nar.question_narratives),
                    },
                    submission_id=submission.id,
                    evaluation_run_id=run.id,
                    published_result_id=published.id,
                    input_hash=canonical_input_hash(student_input.model_dump(mode="json")),
                    latency_ms=int((finished - started).total_seconds() * 1000),
                    started_at=started,
                    finished_at=finished,
                    provider=meta.provider,
                    model=meta.model,
                    model_version=meta.model_version,
                    prompt_template_version=meta.prompt_template_version,
                )
            except (ProviderUnavailable, Exception) as exc:  # noqa: BLE001
                narrative_source = "RULES_FALLBACK"
                student_nar = _rules_student_narrative(
                    assessment_title=assessment.title, questions=narrative_contexts
                )
                parent_nar = _rules_parent_narrative(
                    student_display_name=student.full_name if student else "Student",
                    assessment_title=assessment.title,
                    overview=overview,
                )
                fail_meta = metadata_from_provider(provider, "generate_student_explanation")
                await record_ai_execution(
                    db,
                    tenant_id=tenant_id,
                    operation="generate_student_explanation",
                    status="FAILED",
                    request_summary=redacted_request_summary(
                        operation="generate_student_explanation",
                        entity_ids={"submission_id": str(submission.id)},
                    ),
                    response_summary={"fallback": "RULES_FALLBACK"},
                    submission_id=submission.id,
                    published_result_id=published.id,
                    error_class=type(exc).__name__,
                    provider=fail_meta.provider,
                    model=fail_meta.model,
                    model_version=fail_meta.model_version,
                    prompt_template_version=fail_meta.prompt_template_version,
                )

        # 8 teacher report (deterministic, full ledger)
        student_payload = build_student_report_payload(
            published=published,
            student=student,
            assessment=assessment,
            qes=qes,
            qv_by_id=qv_by_id,
            narrative=student_nar,
            narrative_source=narrative_source,
            generated_at=generated_at,
        )
        parent_payload = build_parent_report_payload(
            published=published,
            student=student,
            assessment=assessment,
            narrative=parent_nar,
            narrative_source=narrative_source,
            generated_at=generated_at,
        )
        teacher_payload = build_teacher_report_payload(
            published=published,
            student=student,
            assessment=assessment,
            qes=qes,
            qv_by_id=qv_by_id,
            criteria_by_qe=criteria_by_qe,
            actions_by_qe=actions_by_qe,
            generated_at=generated_at,
        )

        # 9 validate
        validate_report_payload("student", student_payload)
        validate_report_payload("parent", parent_payload)
        validate_report_payload("teacher", teacher_payload)

        # 10 render PDFs
        student_pdf = render_student_report_pdf(student_payload)
        parent_pdf = render_parent_report_pdf(parent_payload)
        teacher_pdf = render_teacher_report_pdf(teacher_payload)

        # 11 hash + put_export_bytes (immutable)
        version = published.version_number
        artifacts = {
            "annotated": (annotated_pdf, "annotated-paper.pdf"),
            "student": (student_pdf, "student-report.pdf"),
            "parent": (parent_pdf, "parent-report.pdf"),
            "teacher": (teacher_pdf, "teacher-report.pdf"),
        }
        hashes: dict[str, str] = {}
        keys: dict[str, str] = {}
        sizes: dict[str, int] = {}
        for name, (data, filename) in artifacts.items():
            key = publication_export_key(tenant_id, submission.id, version, filename)
            digest = _sha256_bytes(data)
            put = storage.put_export_bytes(key=key, body=data, content_type="application/pdf")
            hashes[name] = digest
            keys[name] = put.key
            sizes[name] = put.byte_size

        # 12 re-read verify hashes
        for name, key in keys.items():
            reread = storage.get_bytes(key)
            if _sha256_bytes(reread) != hashes[name]:
                raise PublicationError(
                    "ARTIFACT_HASH_MISMATCH",
                    f"Stored {name} PDF hash mismatch after write",
                )
            if not reread.startswith(b"%PDF"):
                raise PublicationError("INVALID_PDF", f"{name} artifact is not a PDF")

        published.annotated_pdf_s3_key = keys["annotated"]
        published.annotated_pdf_sha256 = hashes["annotated"]
        published.annotated_pdf_byte_size = sizes["annotated"]
        published.student_report_s3_key = keys["student"]
        published.student_report_sha256 = hashes["student"]
        published.student_report_byte_size = sizes["student"]
        published.student_report_payload = student_payload
        published.parent_report_s3_key = keys["parent"]
        published.parent_report_sha256 = hashes["parent"]
        published.parent_report_byte_size = sizes["parent"]
        published.parent_report_payload = parent_payload
        published.teacher_report_s3_key = keys["teacher"]
        published.teacher_report_sha256 = hashes["teacher"]
        published.teacher_report_byte_size = sizes["teacher"]
        published.teacher_report_payload = teacher_payload
        published.narrative_source = narrative_source
        published.generated_at = generated_at
        published.status = "GENERATED"

        job.status = "SUCCEEDED"
        job.finished_at = datetime.now(UTC)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        job_row = await db.scalar(select(PipelineJob).where(PipelineJob.id == job_id))
        pub_row = await db.scalar(select(PublishedResult).where(PublishedResult.id == published_id))
        sub_row = await db.scalar(select(Submission).where(Submission.id == submission_id))
        code = str(getattr(exc, "code", type(exc).__name__))[:100]
        detail = str(exc)[:4000]
        if job_row is not None:
            job_row.status = "FAILED"
            job_row.error_code = code
            job_row.error_detail = detail
            job_row.finished_at = datetime.now(UTC)
        if pub_row is not None:
            pub_row.status = "FAILED"
            pub_row.failure_code = code
            pub_row.failure_detail = detail
        if sub_row is not None:
            # Publication failure must never leave APPROVED
            sub_row.workflow_state = "APPROVED"
        await db.commit()


async def regenerate_publication(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> tuple[PublishedResult, PipelineJob]:
    current = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if current is None:
        raise PublicationError("NOT_FOUND", "Published result not found")
    if current.status == "PUBLISHED":
        raise PublicationError(
            "ALREADY_PUBLISHED",
            "Cannot regenerate a PUBLISHED result",
        )

    submission = await db.scalar(
        select(Submission).where(
            Submission.id == current.submission_id,
            Submission.tenant_id == tenant_id,
        )
    )
    if submission is None or submission.workflow_state != "APPROVED":
        raise PublicationError(
            "INVALID_WORKFLOW_STATE",
            "Regenerate requires APPROVED submission",
        )

    run, qes, _criteria, canonical = await load_approved_ledger_snapshot(
        db, tenant_id=tenant_id, submission=submission
    )
    snapshot_hash = compute_ledger_snapshot_hash(canonical)
    total, max_total = reconcile_totals(qes)
    version_number = current.version_number + 1

    result = PublishedResult(
        tenant_id=tenant_id,
        submission_id=submission.id,
        student_id=submission.student_id,
        assessment_id=submission.assessment_id,
        assessment_version_id=submission.assessment_version_id,
        evaluation_run_id=run.id,
        version_number=version_number,
        status="READY",
        ledger_snapshot_hash=snapshot_hash,
        total_score=total,
        max_total_score=max_total,
        generated_by=actor_user_id,
        supersedes_result_id=current.id,
    )
    db.add(result)
    await db.flush()

    job = PipelineJob(
        tenant_id=tenant_id,
        submission_id=submission.id,
        stage="PUBLICATION",
        status="QUEUED",
        attempt=1,
        idempotency_key=f"publication:{submission.id}:v{version_number}",
    )
    db.add(job)
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="PublishedResult",
        entity_id=result.id,
        action="publication_regenerated",
        after={
            "supersedes_result_id": str(current.id),
            "version_number": version_number,
        },
    )
    await db.flush()
    return result, job


async def publish_result(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    settings: Settings | None = None,
) -> tuple[PublishedResult, Any]:
    settings = settings or get_settings()
    storage = ObjectStorage(settings)

    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        raise PublicationError("NOT_FOUND", "Published result not found")
    if published.status == "PUBLISHED":
        raise PublicationError("ALREADY_PUBLISHED", "Result is already PUBLISHED")
    if published.status != "GENERATED":
        raise PublicationError(
            "NOT_GENERATED",
            "Publish requires GENERATED status",
        )

    submission = await db.scalar(
        select(Submission).where(
            Submission.id == published.submission_id,
            Submission.tenant_id == tenant_id,
        )
    )
    if submission is None:
        raise PublicationError("NOT_FOUND", "Submission not found")
    if submission.workflow_state != "APPROVED":
        raise PublicationError(
            "INVALID_WORKFLOW_STATE",
            "Publish requires submission still APPROVED",
        )

    _run, _qes, _criteria, canonical = await load_approved_ledger_snapshot(
        db, tenant_id=tenant_id, submission=submission
    )
    current_hash = compute_ledger_snapshot_hash(canonical)
    if current_hash != published.ledger_snapshot_hash:
        raise PublicationError(
            "STALE_SNAPSHOT",
            "Ledger snapshot no longer matches; regenerate before publish",
        )

    artifact_specs = [
        (published.annotated_pdf_s3_key, published.annotated_pdf_sha256),
        (published.student_report_s3_key, published.student_report_sha256),
        (published.parent_report_s3_key, published.parent_report_sha256),
        (published.teacher_report_s3_key, published.teacher_report_sha256),
    ]
    for key, expected in artifact_specs:
        if not key or not expected:
            raise PublicationError("ARTIFACT_MISSING", "Publication artifacts incomplete")
        data = storage.get_bytes(key)
        if _sha256_bytes(data) != expected:
            raise PublicationError(
                "ARTIFACT_HASH_MISMATCH",
                "Artifact hash verification failed",
            )

    now = datetime.now(UTC)
    if published.supersedes_result_id is not None:
        prior = await db.scalar(
            select(PublishedResult).where(
                PublishedResult.id == published.supersedes_result_id,
                PublishedResult.tenant_id == tenant_id,
            )
        )
        if prior is not None and prior.status == "PUBLISHED":
            prior.status = "SUPERSEDED"
            await add_audit_event(
                db,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                entity_type="PublishedResult",
                entity_id=prior.id,
                action="publication_superseded",
                after={
                    "status": "SUPERSEDED",
                    "superseded_by": str(published.id),
                },
            )

    published.status = "PUBLISHED"
    published.published_by = actor_user_id
    published.published_at = now
    # Stamp published_at into payloads
    for attr in (
        "student_report_payload",
        "parent_report_payload",
        "teacher_report_payload",
    ):
        payload = dict(getattr(published, attr) or {})
        payload["published_at"] = now.isoformat()
        setattr(published, attr, payload)

    submission.workflow_state = "PUBLISHED"
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="PublishedResult",
        entity_id=published.id,
        action="publication_published",
        after={
            "submission_id": str(submission.id),
            "ledger_snapshot_hash": published.ledger_snapshot_hash,
        },
    )
    # Ensure ANALYTICS PipelineJob in the same transaction (B8).
    from app.services.analytics import ensure_analytics_job

    analytics_job = await ensure_analytics_job(db, tenant_id=tenant_id, published=published)
    await db.flush()
    return published, analytics_job


async def add_manual_annotation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    annotation_type: str,
    submission_page_id: uuid.UUID,
    x: float,
    y: float,
    width: float,
    height: float,
    payload: dict[str, Any] | None = None,
) -> Annotation:
    if annotation_type not in {"COMMENT", "HIGHLIGHT"}:
        raise PublicationError(
            "INVALID_ANNOTATION_TYPE",
            "Manual annotations may only be COMMENT or HIGHLIGHT",
        )
    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        raise PublicationError("NOT_FOUND", "Published result not found")
    if published.status == "PUBLISHED":
        raise PublicationError(
            "IMMUTABLE",
            "Annotations are immutable when PUBLISHED",
        )
    if published.status != "GENERATED":
        raise PublicationError(
            "INVALID_STATUS",
            "Manual annotations only allowed while GENERATED",
        )

    # Reject score-changing payloads
    payload = dict(payload or {})
    for banned in ("final_marks", "max_marks", "proposed_ai_score", "score"):
        if banned in payload:
            raise PublicationError(
                "SCORE_MUTATION_FORBIDDEN",
                "Manual annotations cannot change scores",
            )

    page = await db.scalar(
        select(SubmissionPage).where(
            SubmissionPage.id == submission_page_id,
            SubmissionPage.tenant_id == tenant_id,
            SubmissionPage.submission_id == published.submission_id,
        )
    )
    if page is None:
        raise PublicationError("NOT_FOUND", "Submission page not found")

    x, y, width, height = _clamp_geom(x, y, width, height)
    ann = Annotation(
        tenant_id=tenant_id,
        submission_id=published.submission_id,
        submission_page_id=page.id,
        published_result_id=published.id,
        annotation_type=annotation_type,
        x=x,
        y=y,
        width=width,
        height=height,
        payload=payload,
        source_type="HUMAN",
        created_by=actor_user_id,
    )
    db.add(ann)
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="Annotation",
        entity_id=ann.id,
        action="manual_annotation_added",
        after={
            "published_result_id": str(published.id),
            "annotation_type": annotation_type,
        },
    )
    await db.flush()
    return ann


def _dump_published(result: PublishedResult) -> dict[str, Any]:
    return {
        "id": str(result.id),
        "submission_id": str(result.submission_id),
        "student_id": str(result.student_id) if result.student_id else None,
        "assessment_id": str(result.assessment_id),
        "assessment_version_id": str(result.assessment_version_id),
        "evaluation_run_id": str(result.evaluation_run_id),
        "version_number": result.version_number,
        "status": result.status,
        "ledger_snapshot_hash": result.ledger_snapshot_hash,
        "total_score": _dec(result.total_score),
        "max_total_score": _dec(result.max_total_score),
        "narrative_source": result.narrative_source,
        "generated_at": result.generated_at.isoformat() if result.generated_at else None,
        "published_at": result.published_at.isoformat() if result.published_at else None,
        "failure_code": result.failure_code,
        "failure_detail": result.failure_detail,
        "artifacts": {
            "ANNOTATED_PDF": {
                "available": bool(result.annotated_pdf_s3_key),
                "sha256": result.annotated_pdf_sha256,
                "byte_size": result.annotated_pdf_byte_size,
            },
            "STUDENT_REPORT_PDF": {
                "available": bool(result.student_report_s3_key),
                "sha256": result.student_report_sha256,
                "byte_size": result.student_report_byte_size,
            },
            "PARENT_REPORT_PDF": {
                "available": bool(result.parent_report_s3_key),
                "sha256": result.parent_report_sha256,
                "byte_size": result.parent_report_byte_size,
            },
            "TEACHER_REPORT_PDF": {
                "available": bool(result.teacher_report_s3_key),
                "sha256": result.teacher_report_sha256,
                "byte_size": result.teacher_report_byte_size,
            },
        },
    }


async def get_publication_workspace(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
) -> dict[str, Any]:
    results = list(
        (
            await db.scalars(
                select(PublishedResult)
                .where(
                    PublishedResult.tenant_id == tenant_id,
                    PublishedResult.submission_id == submission.id,
                )
                .order_by(PublishedResult.version_number.desc())
            )
        ).all()
    )
    latest = results[0] if results else None
    annotations: list[dict[str, Any]] = []
    if latest is not None:
        anns = list(
            (
                await db.scalars(
                    select(Annotation).where(
                        Annotation.tenant_id == tenant_id,
                        Annotation.published_result_id == latest.id,
                    )
                )
            ).all()
        )
        annotations = [
            {
                "id": str(a.id),
                "annotation_type": a.annotation_type,
                "submission_page_id": str(a.submission_page_id),
                "question_evaluation_id": (
                    str(a.question_evaluation_id) if a.question_evaluation_id else None
                ),
                "answer_region_id": str(a.answer_region_id) if a.answer_region_id else None,
                "x": a.x,
                "y": a.y,
                "width": a.width,
                "height": a.height,
                "payload": a.payload or {},
                "source_type": a.source_type,
            }
            for a in anns
        ]
    return {
        "submission_id": str(submission.id),
        "workflow_state": submission.workflow_state,
        "latest": _dump_published(latest) if latest else None,
        "versions": [_dump_published(r) for r in results],
        "annotations": annotations,
    }


async def get_published_result_for_consumer(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
) -> dict[str, Any]:
    published = await db.scalar(
        select(PublishedResult)
        .where(
            PublishedResult.tenant_id == tenant_id,
            PublishedResult.submission_id == submission_id,
            PublishedResult.status == "PUBLISHED",
        )
        .order_by(PublishedResult.version_number.desc())
        .limit(1)
    )
    if published is None:
        raise PublicationError("NOT_FOUND", "No published result")
    return _dump_published(published)


async def resolve_audience_report(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    assessment_id: uuid.UUID,
    audience: str,
) -> dict[str, Any]:
    published = await db.scalar(
        select(PublishedResult)
        .where(
            PublishedResult.tenant_id == tenant_id,
            PublishedResult.student_id == student_id,
            PublishedResult.assessment_id == assessment_id,
            PublishedResult.status == "PUBLISHED",
        )
        .order_by(PublishedResult.version_number.desc())
        .limit(1)
    )
    if published is None:
        raise PublicationError("NOT_FOUND", "No published report for student/assessment")
    if audience == "student":
        return dict(published.student_report_payload or {})
    if audience == "parent":
        return dict(published.parent_report_payload or {})
    if audience == "teacher":
        return dict(published.teacher_report_payload or {})
    raise PublicationError("INVALID_AUDIENCE", f"Unknown audience {audience}")


async def get_report_preview(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
    audience: str,
) -> dict[str, Any]:
    """Reviewer preview — GENERATED or PUBLISHED ok."""
    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        raise PublicationError("NOT_FOUND", "Published result not found")
    if published.status not in {"GENERATED", "PUBLISHED"}:
        raise PublicationError(
            "NOT_READY",
            "Report preview requires GENERATED or PUBLISHED",
        )
    if audience == "student":
        return dict(published.student_report_payload or {})
    if audience == "parent":
        return dict(published.parent_report_payload or {})
    if audience == "teacher":
        return dict(published.teacher_report_payload or {})
    raise PublicationError("INVALID_AUDIENCE", f"Unknown audience {audience}")


async def get_artifact_bytes(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
    artifact_type: str,
    settings: Settings | None = None,
) -> tuple[bytes, str]:
    if artifact_type not in ARTIFACT_TYPES:
        raise PublicationError("INVALID_ARTIFACT_TYPE", f"Unknown artifact {artifact_type}")
    settings = settings or get_settings()
    storage = ObjectStorage(settings)
    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        raise PublicationError("NOT_FOUND", "Published result not found")
    if published.status not in {"GENERATED", "PUBLISHED"}:
        raise PublicationError("NOT_READY", "Artifacts not ready")

    mapping = {
        "ANNOTATED_PDF": (
            published.annotated_pdf_s3_key,
            published.annotated_pdf_sha256,
            "annotated-paper.pdf",
        ),
        "STUDENT_REPORT_PDF": (
            published.student_report_s3_key,
            published.student_report_sha256,
            "student-report.pdf",
        ),
        "PARENT_REPORT_PDF": (
            published.parent_report_s3_key,
            published.parent_report_sha256,
            "parent-report.pdf",
        ),
        "TEACHER_REPORT_PDF": (
            published.teacher_report_s3_key,
            published.teacher_report_sha256,
            "teacher-report.pdf",
        ),
    }
    key, expected, filename = mapping[artifact_type]
    if not key or not expected:
        raise PublicationError("ARTIFACT_MISSING", "Artifact not available")
    data = storage.get_bytes(key)
    if _sha256_bytes(data) != expected:
        raise PublicationError("ARTIFACT_HASH_MISMATCH", "Artifact hash mismatch")
    return data, filename


async def get_scoped_published_result(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    published_result_id: uuid.UUID,
) -> PublishedResult:
    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        raise PublicationError("NOT_FOUND", "Published result not found")
    return published
