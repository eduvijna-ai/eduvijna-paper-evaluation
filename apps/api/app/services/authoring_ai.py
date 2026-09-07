"""B10 authoring AI prepare / run / apply services."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import get_authoring_provider
from app.ai.tracing import canonical_input_hash, record_ai_execution, redacted_request_summary
from app.ai.types import (
    MAX_AUTHORING_TREE_DEPTH,
    MAX_AUTHORING_TREE_NODES,
    AnswerKeyProposalInput,
    CurriculumMappingProposalInput,
    CurriculumNodeHint,
    ProposedQuestionNode,
    QuestionPaperParseInput,
    QuestionPaperParseResult,
    RubricProposalInput,
)
from app.db.models import (
    AnswerKey,
    AnswerKeyVersion,
    Assessment,
    AssessmentArtifact,
    AssessmentVersion,
    AuthoringAiRun,
    CurriculumNode,
    Question,
    QuestionCurriculumMapping,
    QuestionVersion,
    Rubric,
    RubricCriterion,
    RubricVersion,
)
from app.middleware.correlation import get_correlation_id
from app.services.academic_freeze import (
    SERVER_AI_PROPOSED_SOURCE,
    answer_key_audit_payload,
    ensure_academic_config_mutable,
    rubric_criterion_audit_payload,
    rubric_version_audit_payload,
)
from app.services.audit import add_audit_event
from app.services.rubric_reconciliation import reconcile_rubric

logger = logging.getLogger(__name__)


class AuthoringAiError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_mutable(assessment: Assessment) -> None:
    try:
        ensure_academic_config_mutable(assessment)
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        raise AuthoringAiError(
            str(detail.get("code") or "ASSESSMENT_ACADEMIC_CONFIG_FROZEN"),
            str(detail.get("message") or "Assessment academic config is frozen"),
        ) from exc


def _dump(item: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attribute in inspect(item).mapper.column_attrs:
        result[attribute.columns[0].name] = getattr(item, attribute.key)
    return result


def dump_authoring_run(run: AuthoringAiRun) -> dict[str, Any]:
    return _dump(run)


def validate_question_tree(
    roots: list[ProposedQuestionNode],
    *,
    assessment_max_marks: Decimal,
) -> None:
    """Validate proposed tree: unique codes, hierarchy bounds, leaf marks sum."""
    codes: set[str] = set()
    node_count = 0
    leaf_total = Decimal("0.00")

    def walk(node: ProposedQuestionNode, depth: int) -> None:
        nonlocal node_count, leaf_total
        if depth > MAX_AUTHORING_TREE_DEPTH:
            raise AuthoringAiError(
                "QUESTION_TREE_DEPTH_EXCEEDED",
                f"Question tree exceeds max depth {MAX_AUTHORING_TREE_DEPTH}",
            )
        node_count += 1
        if node_count > MAX_AUTHORING_TREE_NODES:
            raise AuthoringAiError(
                "QUESTION_TREE_TOO_LARGE",
                f"Question tree exceeds max nodes {MAX_AUTHORING_TREE_NODES}",
            )
        code = node.stable_code.strip()
        if not code:
            raise AuthoringAiError(
                "QUESTION_TREE_INVALID_CODE", "stable_code must be non-empty"
            )
        if code in codes:
            raise AuthoringAiError(
                "QUESTION_TREE_DUPLICATE_CODE",
                f"Duplicate stable_code {code!r}",
            )
        codes.add(code)
        if node.scoring_mode == "LEAF_SCORABLE":
            if node.children:
                raise AuthoringAiError(
                    "QUESTION_TREE_INVALID_HIERARCHY",
                    f"LEAF_SCORABLE node {code!r} cannot have children",
                )
            leaf_total += Decimal(node.max_marks)
        elif node.scoring_mode == "CONTAINER_DERIVED":
            if not node.children:
                raise AuthoringAiError(
                    "QUESTION_TREE_INVALID_HIERARCHY",
                    f"CONTAINER_DERIVED node {code!r} requires children",
                )
        else:
            raise AuthoringAiError(
                "QUESTION_TREE_INVALID_SCORING_MODE",
                f"Unsupported scoring_mode for {code!r}",
            )
        for child in node.children:
            walk(child, depth + 1)

    if not roots:
        raise AuthoringAiError("QUESTION_TREE_EMPTY", "Question tree has no roots")
    for root in roots:
        walk(root, 1)

    expected = Decimal(assessment_max_marks).quantize(Decimal("0.01"))
    actual = leaf_total.quantize(Decimal("0.01"))
    if actual != expected:
        raise AuthoringAiError(
            "QUESTION_TREE_MARKS_MISMATCH",
            f"Leaf marks total {actual} != assessment max {expected}",
        )


def _tree_payload(result: QuestionPaperParseResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


def _parse_roots_from_payload(payload: dict[str, Any] | None) -> list[ProposedQuestionNode]:
    if not payload or "roots" not in payload:
        raise AuthoringAiError(
            "QUESTION_TREE_EMPTY", "proposal_payload is missing roots"
        )
    parsed = QuestionPaperParseResult.model_validate(payload)
    return list(parsed.roots)


async def _get_version(
    db: AsyncSession, *, tenant_id: uuid.UUID, version_id: uuid.UUID
) -> AssessmentVersion:
    version = await db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.id == version_id,
            AssessmentVersion.tenant_id == tenant_id,
        )
    )
    if version is None:
        raise AuthoringAiError("NOT_FOUND", "Assessment version not found")
    return version


async def _get_assessment(
    db: AsyncSession, *, tenant_id: uuid.UUID, assessment_id: uuid.UUID
) -> Assessment:
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.tenant_id == tenant_id
        )
    )
    if assessment is None:
        raise AuthoringAiError("NOT_FOUND", "Assessment not found")
    return assessment


async def _get_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> AuthoringAiRun:
    run = await db.scalar(
        select(AuthoringAiRun).where(
            AuthoringAiRun.id == run_id, AuthoringAiRun.tenant_id == tenant_id
        )
    )
    if run is None:
        raise AuthoringAiError("NOT_FOUND", "Authoring AI run not found")
    return run


async def get_authoring_run(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> AuthoringAiRun:
    return await _get_run(db, tenant_id=tenant_id, run_id=run_id)


async def _get_question_version(
    db: AsyncSession, *, tenant_id: uuid.UUID, question_version_id: uuid.UUID
) -> QuestionVersion:
    qv = await db.scalar(
        select(QuestionVersion).where(
            QuestionVersion.id == question_version_id,
            QuestionVersion.tenant_id == tenant_id,
        )
    )
    if qv is None:
        raise AuthoringAiError("NOT_FOUND", "Question version not found")
    return qv


async def _audit(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    entity: Any,
    action: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type=entity.__class__.__name__,
        entity_id=entity.id,
        action=action,
        after=payload,
        correlation_id=correlation_id,
    )


async def mark_unavailable(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run: AuthoringAiRun,
    operation: str,
) -> None:
    run.status = "UNAVAILABLE"
    run.failure_code = "AI_PROVIDER_UNAVAILABLE"
    run.failure_detail = "No authoring AI provider is configured"
    run.finished_at = _utcnow()
    await record_ai_execution(
        db,
        tenant_id=tenant_id,
        operation=operation,
        provider="none",
        status="UNAVAILABLE",
        request_summary=redacted_request_summary(
            operation=operation,
            entity_ids={
                "authoring_ai_run_id": str(run.id),
                "assessment_version_id": str(run.assessment_version_id),
                "question_version_id": (
                    str(run.question_version_id) if run.question_version_id else None
                ),
            },
        ),
        response_summary={"error_code": "AI_PROVIDER_UNAVAILABLE"},
        authoring_ai_run_id=run.id,
        assessment_version_id=run.assessment_version_id,
        assessment_artifact_id=run.assessment_artifact_id,
        error_class="AI_PROVIDER_UNAVAILABLE",
    )


async def prepare_parse_question_paper(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_version_id: uuid.UUID,
    requested_by: uuid.UUID,
    correlation_id: str | None = None,
) -> AuthoringAiRun:
    version = await _get_version(
        db, tenant_id=tenant_id, version_id=assessment_version_id
    )
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=version.assessment_id
    )
    if assessment.status != "DRAFT" or version.status != "DRAFT":
        raise AuthoringAiError(
            "ASSESSMENT_NOT_DRAFT",
            "Question paper parse requires DRAFT assessment and version",
        )
    existing_questions = await db.scalar(
        select(func.count())
        .select_from(QuestionVersion)
        .where(
            QuestionVersion.tenant_id == tenant_id,
            QuestionVersion.assessment_version_id == version.id,
        )
    )
    if int(existing_questions or 0) > 0:
        raise AuthoringAiError(
            "QUESTION_PAPER_STRUCTURE_EXISTS",
            "Assessment version already has questions",
        )

    artifact: AssessmentArtifact | None = None
    if version.question_paper_artifact_id is not None:
        artifact = await db.scalar(
            select(AssessmentArtifact).where(
                AssessmentArtifact.id == version.question_paper_artifact_id,
                AssessmentArtifact.tenant_id == tenant_id,
            )
        )

    input_hash = canonical_input_hash(
        {
            "operation": "PARSE_QUESTION_PAPER",
            "assessment_version_id": str(version.id),
            "artifact_id": str(artifact.id) if artifact else None,
            "content_sha256": artifact.content_sha256 if artifact else None,
            "max_marks": str(version.max_marks),
        }
    )
    existing = await db.scalar(
        select(AuthoringAiRun).where(
            AuthoringAiRun.tenant_id == tenant_id,
            AuthoringAiRun.assessment_version_id == version.id,
            AuthoringAiRun.operation == "PARSE_QUESTION_PAPER",
            AuthoringAiRun.input_hash == input_hash,
            AuthoringAiRun.status.in_(
                ("QUEUED", "RUNNING", "REVIEW_REQUIRED", "SUCCEEDED")
            ),
        )
    )
    if existing is not None:
        return existing

    run = AuthoringAiRun(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        assessment_version_id=version.id,
        assessment_artifact_id=artifact.id if artifact else None,
        operation="PARSE_QUESTION_PAPER",
        status="QUEUED",
        input_hash=input_hash,
        requested_by=requested_by,
        requested_at=_utcnow(),
        correlation_id=correlation_id or get_correlation_id(),
    )
    db.add(run)
    await db.flush()
    return run


async def run_parse_pipeline(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> None:
    run = await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    if run.operation != "PARSE_QUESTION_PAPER":
        raise AuthoringAiError("INVALID_OPERATION", "Run is not a parse operation")
    if run.status in {"REVIEW_REQUIRED", "SUCCEEDED", "UNAVAILABLE"}:
        return

    provider = get_authoring_provider()
    if provider is None:
        await mark_unavailable(
            db, tenant_id=tenant_id, run=run, operation="parse_question_paper"
        )
        await db.commit()
        return

    run.status = "RUNNING"
    run.started_at = _utcnow()
    await db.flush()

    version = await _get_version(
        db, tenant_id=tenant_id, version_id=run.assessment_version_id
    )
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=run.assessment_id
    )
    artifact: AssessmentArtifact | None = None
    if run.assessment_artifact_id is not None:
        artifact = await db.scalar(
            select(AssessmentArtifact).where(
                AssessmentArtifact.id == run.assessment_artifact_id,
                AssessmentArtifact.tenant_id == tenant_id,
            )
        )

    ai_input = QuestionPaperParseInput(
        assessment_id=assessment.id,
        assessment_version_id=version.id,
        assessment_title=assessment.title,
        max_marks=version.max_marks,
        assessment_artifact_id=artifact.id if artifact else None,
        content_sha256=artifact.content_sha256 if artifact else None,
        mime_type=artifact.mime_type if artifact else None,
        original_filename=artifact.original_filename if artifact else None,
    )
    started = _utcnow()
    try:
        result = await provider.parse_question_paper(ai_input)
        validate_question_tree(list(result.roots), assessment_max_marks=version.max_marks)
        run.proposal_payload = _tree_payload(result)
        run.status = "REVIEW_REQUIRED"
        run.finished_at = _utcnow()
        await record_ai_execution(
            db,
            tenant_id=tenant_id,
            operation="parse_question_paper",
            provider=provider.provider_name,
            status="SUCCEEDED",
            request_summary=redacted_request_summary(
                operation="parse_question_paper",
                entity_ids={
                    "authoring_ai_run_id": str(run.id),
                    "assessment_version_id": str(version.id),
                },
            ),
            response_summary={"root_count": len(result.roots)},
            authoring_ai_run_id=run.id,
            assessment_version_id=version.id,
            assessment_artifact_id=run.assessment_artifact_id,
            input_hash=run.input_hash,
            started_at=started,
            finished_at=_utcnow(),
        )
        await db.commit()
    except AuthoringAiError as exc:
        run.status = "FAILED"
        run.failure_code = exc.code
        run.failure_detail = exc.message
        run.finished_at = _utcnow()
        await record_ai_execution(
            db,
            tenant_id=tenant_id,
            operation="parse_question_paper",
            provider=provider.provider_name,
            status="FAILED",
            request_summary=redacted_request_summary(
                operation="parse_question_paper",
                entity_ids={"authoring_ai_run_id": str(run.id)},
            ),
            response_summary={"error_code": exc.code},
            authoring_ai_run_id=run.id,
            assessment_version_id=version.id,
            error_class=exc.code,
            started_at=started,
            finished_at=_utcnow(),
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("parse pipeline failed run_id=%s", run.id)
        run.status = "FAILED"
        run.failure_code = "AUTHORING_AI_FAILED"
        run.failure_detail = str(exc)[:500]
        run.finished_at = _utcnow()
        await db.commit()


async def update_question_tree_proposal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    roots: list[ProposedQuestionNode],
    notes: str | None = None,
) -> AuthoringAiRun:
    run = await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    if run.operation != "PARSE_QUESTION_PAPER":
        raise AuthoringAiError("INVALID_OPERATION", "Run is not a parse operation")
    if run.status != "REVIEW_REQUIRED":
        raise AuthoringAiError(
            "AUTHORING_RUN_NOT_EDITABLE",
            "Question tree proposal can only be edited while REVIEW_REQUIRED",
        )
    version = await _get_version(
        db, tenant_id=tenant_id, version_id=run.assessment_version_id
    )
    validate_question_tree(roots, assessment_max_marks=version.max_marks)
    payload = QuestionPaperParseResult(roots=roots, notes=notes).model_dump(mode="json")
    run.proposal_payload = payload
    await db.flush()
    return run


async def apply_question_tree(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    applied_by: uuid.UUID,
) -> AuthoringAiRun:
    run = await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    if run.operation != "PARSE_QUESTION_PAPER":
        raise AuthoringAiError("INVALID_OPERATION", "Run is not a parse operation")
    if run.status == "SUCCEEDED":
        return run
    if run.status != "REVIEW_REQUIRED":
        raise AuthoringAiError(
            "AUTHORING_RUN_NOT_APPLICABLE",
            "Question tree can only be applied from REVIEW_REQUIRED",
        )
    version = await _get_version(
        db, tenant_id=tenant_id, version_id=run.assessment_version_id
    )
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=run.assessment_id
    )
    if assessment.status != "DRAFT" or version.status != "DRAFT":
        raise AuthoringAiError(
            "ASSESSMENT_NOT_DRAFT", "Apply requires DRAFT assessment and version"
        )
    existing_questions = await db.scalar(
        select(func.count())
        .select_from(QuestionVersion)
        .where(
            QuestionVersion.tenant_id == tenant_id,
            QuestionVersion.assessment_version_id == version.id,
        )
    )
    if int(existing_questions or 0) > 0:
        raise AuthoringAiError(
            "QUESTION_PAPER_STRUCTURE_EXISTS",
            "Assessment version already has questions",
        )

    roots = _parse_roots_from_payload(run.proposal_payload)
    validate_question_tree(roots, assessment_max_marks=version.max_marks)

    async def create_node(
        node: ProposedQuestionNode, parent_qv_id: uuid.UUID | None
    ) -> QuestionVersion:
        question = await db.scalar(
            select(Question).where(
                Question.tenant_id == tenant_id,
                Question.assessment_id == assessment.id,
                Question.stable_code == node.stable_code,
            )
        )
        if question is None:
            question = Question(
                tenant_id=tenant_id,
                assessment_id=assessment.id,
                stable_code=node.stable_code,
            )
            db.add(question)
            await db.flush()
        qv = QuestionVersion(
            tenant_id=tenant_id,
            assessment_version_id=version.id,
            question_id=question.id,
            parent_question_version_id=parent_qv_id,
            display_label=node.display_label,
            sequence=node.sequence,
            prompt_text=node.prompt_text,
            max_marks=node.max_marks,
            question_type=node.question_type,
            scoring_mode=node.scoring_mode,
            instructions=node.instructions,
        )
        db.add(qv)
        await db.flush()
        await _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=applied_by,
            entity=qv,
            action="created",
            payload={
                "action": "created",
                "source": "authoring_ai_apply",
                "authoring_ai_run_id": str(run.id),
                "stable_code": node.stable_code,
            },
            correlation_id=run.correlation_id,
        )
        for child in node.children:
            await create_node(child, qv.id)
        return qv

    for root in roots:
        await create_node(root, None)

    run.status = "SUCCEEDED"
    run.finished_at = _utcnow()
    await _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=applied_by,
        entity=run,
        action="applied",
        payload={
            "action": "applied",
            "authoring_ai_run_id": str(run.id),
            "assessment_version_id": str(version.id),
        },
        correlation_id=run.correlation_id,
    )
    await db.flush()
    return run


async def _assert_no_existing_material(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_id: uuid.UUID,
    question_version_id: uuid.UUID,
    kind: str,
) -> None:
    if kind == "answer_key":
        key = await db.scalar(
            select(AnswerKey).where(
                AnswerKey.tenant_id == tenant_id,
                AnswerKey.assessment_id == assessment_id,
            )
        )
        if key is None:
            return
        active = await db.scalar(
            select(AnswerKeyVersion).where(
                AnswerKeyVersion.answer_key_id == key.id,
                AnswerKeyVersion.question_version_id == question_version_id,
                AnswerKeyVersion.status.in_(
                    ("DRAFT", "REVIEW_REQUIRED", "APPROVED")
                ),
            )
        )
        if active is not None and (
            active.source_type == "TEACHER" or active.status == "APPROVED"
        ):
            raise AuthoringAiError(
                "AUTHORING_MATERIAL_ALREADY_EXISTS",
                "Teacher or approved answer key already exists for this question",
            )
        if active is not None and active.source_type == SERVER_AI_PROPOSED_SOURCE:
            raise AuthoringAiError(
                "AUTHORING_MATERIAL_ALREADY_EXISTS",
                "An AI-proposed answer key already exists for this question",
            )
    elif kind == "rubric":
        rubric = await db.scalar(
            select(Rubric).where(
                Rubric.tenant_id == tenant_id,
                Rubric.assessment_id == assessment_id,
                Rubric.question_version_id == question_version_id,
            )
        )
        if rubric is None:
            return
        active = await db.scalar(
            select(RubricVersion).where(
                RubricVersion.rubric_id == rubric.id,
                RubricVersion.question_version_id == question_version_id,
                RubricVersion.status.in_(("DRAFT", "REVIEW_REQUIRED", "APPROVED")),
            )
        )
        if active is not None and (
            active.source_type == "TEACHER" or active.status == "APPROVED"
        ):
            raise AuthoringAiError(
                "AUTHORING_MATERIAL_ALREADY_EXISTS",
                "Teacher or approved rubric already exists for this question",
            )
        if active is not None and active.source_type == SERVER_AI_PROPOSED_SOURCE:
            raise AuthoringAiError(
                "AUTHORING_MATERIAL_ALREADY_EXISTS",
                "An AI-proposed rubric already exists for this question",
            )


async def prepare_propose_answer_key(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    question_version_id: uuid.UUID,
    assessment_version_id: uuid.UUID | None,
    requested_by: uuid.UUID,
    instructions: str | None = None,
    correlation_id: str | None = None,
) -> AuthoringAiRun:
    qv = await _get_question_version(
        db, tenant_id=tenant_id, question_version_id=question_version_id
    )
    version_id = assessment_version_id or qv.assessment_version_id
    version = await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    if qv.assessment_version_id != version.id:
        raise AuthoringAiError("NOT_FOUND", "Question version not found")
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=version.assessment_id
    )
    _ensure_mutable(assessment)
    await _assert_no_existing_material(
        db,
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        question_version_id=qv.id,
        kind="answer_key",
    )
    question = await db.scalar(
        select(Question).where(Question.id == qv.question_id, Question.tenant_id == tenant_id)
    )
    stable = question.stable_code if question else str(qv.id)
    input_hash = canonical_input_hash(
        {
            "operation": "PROPOSE_ANSWER_KEY",
            "question_version_id": str(qv.id),
            "assessment_version_id": str(version.id),
            "prompt_len": len(qv.prompt_text or ""),
            "instructions_len": len(instructions or ""),
        }
    )
    existing = await db.scalar(
        select(AuthoringAiRun).where(
            AuthoringAiRun.tenant_id == tenant_id,
            AuthoringAiRun.operation == "PROPOSE_ANSWER_KEY",
            AuthoringAiRun.input_hash == input_hash,
            AuthoringAiRun.status.in_(
                ("QUEUED", "RUNNING", "REVIEW_REQUIRED", "SUCCEEDED")
            ),
        )
    )
    if existing is not None:
        return existing

    run = AuthoringAiRun(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        assessment_version_id=version.id,
        question_version_id=qv.id,
        operation="PROPOSE_ANSWER_KEY",
        status="QUEUED",
        input_hash=input_hash,
        proposal_payload={"instructions": instructions, "stable_code": stable},
        requested_by=requested_by,
        requested_at=_utcnow(),
        correlation_id=correlation_id or get_correlation_id(),
    )
    db.add(run)
    await db.flush()
    return run


async def run_propose_answer_key_pipeline(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> None:
    run = await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    if run.operation != "PROPOSE_ANSWER_KEY":
        raise AuthoringAiError("INVALID_OPERATION", "Run is not an answer-key proposal")
    if run.status in {"REVIEW_REQUIRED", "SUCCEEDED", "UNAVAILABLE"}:
        return

    provider = get_authoring_provider()
    if provider is None:
        await mark_unavailable(
            db, tenant_id=tenant_id, run=run, operation="propose_answer_key"
        )
        await db.commit()
        return

    run.status = "RUNNING"
    run.started_at = _utcnow()
    await db.flush()

    assert run.question_version_id is not None
    qv = await _get_question_version(
        db, tenant_id=tenant_id, question_version_id=run.question_version_id
    )
    version = await _get_version(
        db, tenant_id=tenant_id, version_id=run.assessment_version_id
    )
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=run.assessment_id
    )
    question = await db.scalar(
        select(Question).where(Question.id == qv.question_id, Question.tenant_id == tenant_id)
    )
    stable = question.stable_code if question else "Q"
    instructions = None
    if isinstance(run.proposal_payload, dict):
        instructions = run.proposal_payload.get("instructions")

    started = _utcnow()
    try:
        await _assert_no_existing_material(
            db,
            tenant_id=tenant_id,
            assessment_id=assessment.id,
            question_version_id=qv.id,
            kind="answer_key",
        )
        result = await provider.propose_answer_key(
            AnswerKeyProposalInput(
                assessment_version_id=version.id,
                question_version_id=qv.id,
                stable_code=stable,
                display_label=qv.display_label,
                prompt_text=qv.prompt_text,
                max_marks=qv.max_marks,
                question_type=qv.question_type,
                instructions=instructions,
            )
        )
        key = await db.scalar(
            select(AnswerKey).where(
                AnswerKey.tenant_id == tenant_id,
                AnswerKey.assessment_id == assessment.id,
            )
        )
        if key is None:
            key = AnswerKey(tenant_id=tenant_id, assessment_id=assessment.id)
            db.add(key)
            await db.flush()
        latest = await db.scalar(
            select(func.max(AnswerKeyVersion.version_number)).where(
                AnswerKeyVersion.answer_key_id == key.id
            )
        )
        akv = AnswerKeyVersion(
            tenant_id=tenant_id,
            answer_key_id=key.id,
            assessment_version_id=version.id,
            question_version_id=qv.id,
            version_number=int(latest or 0) + 1,
            answer_text=result.answer_text,
            structured_answer=result.structured_answer,
            source_type=SERVER_AI_PROPOSED_SOURCE,
            status="REVIEW_REQUIRED",
            created_by=run.requested_by,
        )
        db.add(akv)
        await db.flush()
        await _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=run.requested_by,
            entity=akv,
            action="created",
            payload=answer_key_audit_payload(akv, "created"),
            correlation_id=run.correlation_id,
        )
        if assessment.status == "DRAFT":
            assessment.status = "RUBRIC_REVIEW"
        run.answer_key_version_id = akv.id
        run.proposal_payload = {
            "answer_text_length": len(result.answer_text),
            "has_structured_answer": result.structured_answer is not None,
        }
        run.status = "REVIEW_REQUIRED"
        run.finished_at = _utcnow()
        await record_ai_execution(
            db,
            tenant_id=tenant_id,
            operation="propose_answer_key",
            provider=provider.provider_name,
            status="SUCCEEDED",
            request_summary=redacted_request_summary(
                operation="propose_answer_key",
                entity_ids={
                    "authoring_ai_run_id": str(run.id),
                    "question_version_id": str(qv.id),
                },
            ),
            response_summary={"answer_key_version_id": str(akv.id)},
            authoring_ai_run_id=run.id,
            assessment_version_id=version.id,
            answer_key_version_id=akv.id,
            input_hash=run.input_hash,
            started_at=started,
            finished_at=_utcnow(),
        )
        await db.commit()
    except AuthoringAiError as exc:
        run.status = "FAILED"
        run.failure_code = exc.code
        run.failure_detail = exc.message
        run.finished_at = _utcnow()
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("answer key propose failed run_id=%s", run.id)
        run.status = "FAILED"
        run.failure_code = "AUTHORING_AI_FAILED"
        run.failure_detail = str(exc)[:500]
        run.finished_at = _utcnow()
        await db.commit()


async def prepare_propose_rubric(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    question_version_id: uuid.UUID,
    assessment_version_id: uuid.UUID | None,
    requested_by: uuid.UUID,
    instructions: str | None = None,
    correlation_id: str | None = None,
) -> AuthoringAiRun:
    qv = await _get_question_version(
        db, tenant_id=tenant_id, question_version_id=question_version_id
    )
    version_id = assessment_version_id or qv.assessment_version_id
    version = await _get_version(db, tenant_id=tenant_id, version_id=version_id)
    if qv.assessment_version_id != version.id:
        raise AuthoringAiError("NOT_FOUND", "Question version not found")
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=version.assessment_id
    )
    _ensure_mutable(assessment)
    await _assert_no_existing_material(
        db,
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        question_version_id=qv.id,
        kind="rubric",
    )
    question = await db.scalar(
        select(Question).where(Question.id == qv.question_id, Question.tenant_id == tenant_id)
    )
    stable = question.stable_code if question else str(qv.id)
    input_hash = canonical_input_hash(
        {
            "operation": "PROPOSE_RUBRIC",
            "question_version_id": str(qv.id),
            "assessment_version_id": str(version.id),
            "instructions_len": len(instructions or ""),
        }
    )
    existing = await db.scalar(
        select(AuthoringAiRun).where(
            AuthoringAiRun.tenant_id == tenant_id,
            AuthoringAiRun.operation == "PROPOSE_RUBRIC",
            AuthoringAiRun.input_hash == input_hash,
            AuthoringAiRun.status.in_(
                ("QUEUED", "RUNNING", "REVIEW_REQUIRED", "SUCCEEDED")
            ),
        )
    )
    if existing is not None:
        return existing

    run = AuthoringAiRun(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        assessment_version_id=version.id,
        question_version_id=qv.id,
        operation="PROPOSE_RUBRIC",
        status="QUEUED",
        input_hash=input_hash,
        proposal_payload={"instructions": instructions, "stable_code": stable},
        requested_by=requested_by,
        requested_at=_utcnow(),
        correlation_id=correlation_id or get_correlation_id(),
    )
    db.add(run)
    await db.flush()
    return run


async def run_propose_rubric_pipeline(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> None:
    run = await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    if run.operation != "PROPOSE_RUBRIC":
        raise AuthoringAiError("INVALID_OPERATION", "Run is not a rubric proposal")
    if run.status in {"REVIEW_REQUIRED", "SUCCEEDED", "UNAVAILABLE"}:
        return

    provider = get_authoring_provider()
    if provider is None:
        await mark_unavailable(
            db, tenant_id=tenant_id, run=run, operation="propose_rubric"
        )
        await db.commit()
        return

    run.status = "RUNNING"
    run.started_at = _utcnow()
    await db.flush()

    assert run.question_version_id is not None
    qv = await _get_question_version(
        db, tenant_id=tenant_id, question_version_id=run.question_version_id
    )
    version = await _get_version(
        db, tenant_id=tenant_id, version_id=run.assessment_version_id
    )
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=run.assessment_id
    )
    question = await db.scalar(
        select(Question).where(Question.id == qv.question_id, Question.tenant_id == tenant_id)
    )
    stable = question.stable_code if question else "Q"
    instructions = None
    if isinstance(run.proposal_payload, dict):
        instructions = run.proposal_payload.get("instructions")

    started = _utcnow()
    try:
        await _assert_no_existing_material(
            db,
            tenant_id=tenant_id,
            assessment_id=assessment.id,
            question_version_id=qv.id,
            kind="rubric",
        )
        answer = await db.scalar(
            select(AnswerKeyVersion).where(
                AnswerKeyVersion.tenant_id == tenant_id,
                AnswerKeyVersion.question_version_id == qv.id,
                AnswerKeyVersion.status.in_(("DRAFT", "REVIEW_REQUIRED", "APPROVED")),
            )
        )
        result = await provider.propose_rubric(
            RubricProposalInput(
                assessment_version_id=version.id,
                question_version_id=qv.id,
                stable_code=stable,
                display_label=qv.display_label,
                prompt_text=qv.prompt_text,
                max_marks=qv.max_marks,
                question_type=qv.question_type,
                answer_text=answer.answer_text if answer else None,
                instructions=instructions,
            )
        )
        ok, total = reconcile_rubric(
            [
                type(
                    "C",
                    (),
                    {
                        "max_marks": c.max_marks,
                        "scoring_mode": c.scoring_mode,
                    },
                )()
                for c in result.criteria
            ],
            qv.max_marks,
        )
        if not ok:
            raise AuthoringAiError(
                "RUBRIC_MARKS_MISMATCH",
                f"Proposed rubric criteria total {total} != question max {qv.max_marks}",
            )

        rubric = await db.scalar(
            select(Rubric).where(
                Rubric.tenant_id == tenant_id,
                Rubric.assessment_id == assessment.id,
                Rubric.question_version_id == qv.id,
            )
        )
        if rubric is None:
            rubric = Rubric(
                tenant_id=tenant_id,
                assessment_id=assessment.id,
                question_version_id=qv.id,
                title=result.title,
                provenance=SERVER_AI_PROPOSED_SOURCE,
            )
            db.add(rubric)
            await db.flush()
        latest = await db.scalar(
            select(func.max(RubricVersion.version_number)).where(
                RubricVersion.rubric_id == rubric.id
            )
        )
        rv = RubricVersion(
            tenant_id=tenant_id,
            rubric_id=rubric.id,
            question_version_id=qv.id,
            version_number=int(latest or 0) + 1,
            status="REVIEW_REQUIRED",
            source_type=SERVER_AI_PROPOSED_SOURCE,
            created_by=run.requested_by,
        )
        db.add(rv)
        await db.flush()
        await _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=run.requested_by,
            entity=rv,
            action="created",
            payload=rubric_version_audit_payload(rv, "created"),
            correlation_id=run.correlation_id,
        )
        for crit in result.criteria:
            criterion = RubricCriterion(
                tenant_id=tenant_id,
                rubric_version_id=rv.id,
                criterion_code=crit.criterion_code,
                description=crit.description,
                max_marks=crit.max_marks,
                sequence=crit.sequence,
                scoring_mode=crit.scoring_mode,
                partial_credit_allowed=crit.partial_credit_allowed,
                ecf_policy=crit.ecf_policy,
                accepted_equivalents=list(crit.accepted_equivalents),
            )
            db.add(criterion)
            await db.flush()
            await _audit(
                db,
                tenant_id=tenant_id,
                actor_user_id=run.requested_by,
                entity=criterion,
                action="created",
                payload=rubric_criterion_audit_payload(criterion, "created"),
                correlation_id=run.correlation_id,
            )
        if assessment.status == "DRAFT":
            assessment.status = "RUBRIC_REVIEW"
        run.rubric_version_id = rv.id
        run.proposal_payload = {
            "title": result.title,
            "criterion_count": len(result.criteria),
        }
        run.status = "REVIEW_REQUIRED"
        run.finished_at = _utcnow()
        await record_ai_execution(
            db,
            tenant_id=tenant_id,
            operation="propose_rubric",
            provider=provider.provider_name,
            status="SUCCEEDED",
            request_summary=redacted_request_summary(
                operation="propose_rubric",
                entity_ids={
                    "authoring_ai_run_id": str(run.id),
                    "question_version_id": str(qv.id),
                },
            ),
            response_summary={"rubric_version_id": str(rv.id)},
            authoring_ai_run_id=run.id,
            assessment_version_id=version.id,
            rubric_version_id=rv.id,
            input_hash=run.input_hash,
            started_at=started,
            finished_at=_utcnow(),
        )
        await db.commit()
    except AuthoringAiError as exc:
        run.status = "FAILED"
        run.failure_code = exc.code
        run.failure_detail = exc.message
        run.finished_at = _utcnow()
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("rubric propose failed run_id=%s", run.id)
        run.status = "FAILED"
        run.failure_code = "AUTHORING_AI_FAILED"
        run.failure_detail = str(exc)[:500]
        run.finished_at = _utcnow()
        await db.commit()


async def prepare_suggest_curriculum_mapping(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    question_version_id: uuid.UUID,
    curriculum_id: uuid.UUID | None,
    requested_by: uuid.UUID,
    instructions: str | None = None,
    correlation_id: str | None = None,
) -> AuthoringAiRun:
    qv = await _get_question_version(
        db, tenant_id=tenant_id, question_version_id=question_version_id
    )
    version = await _get_version(
        db, tenant_id=tenant_id, version_id=qv.assessment_version_id
    )
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=version.assessment_id
    )
    _ensure_mutable(assessment)
    resolved_curriculum = curriculum_id or assessment.curriculum_id
    question = await db.scalar(
        select(Question).where(Question.id == qv.question_id, Question.tenant_id == tenant_id)
    )
    stable = question.stable_code if question else str(qv.id)
    input_hash = canonical_input_hash(
        {
            "operation": "SUGGEST_CURRICULUM_MAPPING",
            "question_version_id": str(qv.id),
            "curriculum_id": str(resolved_curriculum),
            "instructions_len": len(instructions or ""),
        }
    )
    existing = await db.scalar(
        select(AuthoringAiRun).where(
            AuthoringAiRun.tenant_id == tenant_id,
            AuthoringAiRun.operation == "SUGGEST_CURRICULUM_MAPPING",
            AuthoringAiRun.input_hash == input_hash,
            AuthoringAiRun.status.in_(
                ("QUEUED", "RUNNING", "REVIEW_REQUIRED", "SUCCEEDED")
            ),
        )
    )
    if existing is not None:
        return existing

    run = AuthoringAiRun(
        tenant_id=tenant_id,
        assessment_id=assessment.id,
        assessment_version_id=version.id,
        question_version_id=qv.id,
        operation="SUGGEST_CURRICULUM_MAPPING",
        status="QUEUED",
        input_hash=input_hash,
        proposal_payload={
            "instructions": instructions,
            "curriculum_id": str(resolved_curriculum),
            "stable_code": stable,
        },
        requested_by=requested_by,
        requested_at=_utcnow(),
        correlation_id=correlation_id or get_correlation_id(),
    )
    db.add(run)
    await db.flush()
    return run


async def run_suggest_curriculum_mapping_pipeline(
    db: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> None:
    run = await _get_run(db, tenant_id=tenant_id, run_id=run_id)
    if run.operation != "SUGGEST_CURRICULUM_MAPPING":
        raise AuthoringAiError(
            "INVALID_OPERATION", "Run is not a curriculum-mapping proposal"
        )
    if run.status in {"REVIEW_REQUIRED", "SUCCEEDED", "UNAVAILABLE"}:
        return

    provider = get_authoring_provider()
    if provider is None:
        await mark_unavailable(
            db,
            tenant_id=tenant_id,
            run=run,
            operation="suggest_curriculum_mapping",
        )
        await db.commit()
        return

    run.status = "RUNNING"
    run.started_at = _utcnow()
    await db.flush()

    assert run.question_version_id is not None
    qv = await _get_question_version(
        db, tenant_id=tenant_id, question_version_id=run.question_version_id
    )
    assessment = await _get_assessment(
        db, tenant_id=tenant_id, assessment_id=run.assessment_id
    )
    curriculum_id = assessment.curriculum_id
    if isinstance(run.proposal_payload, dict) and run.proposal_payload.get(
        "curriculum_id"
    ):
        curriculum_id = uuid.UUID(str(run.proposal_payload["curriculum_id"]))
    nodes = list(
        (
            await db.scalars(
                select(CurriculumNode)
                .where(
                    CurriculumNode.tenant_id == tenant_id,
                    CurriculumNode.curriculum_id == curriculum_id,
                    CurriculumNode.status == "active",
                )
                .order_by(CurriculumNode.sequence)
                .limit(50)
            )
        ).all()
    )
    question = await db.scalar(
        select(Question).where(Question.id == qv.question_id, Question.tenant_id == tenant_id)
    )
    stable = question.stable_code if question else "Q"
    instructions = None
    if isinstance(run.proposal_payload, dict):
        instructions = run.proposal_payload.get("instructions")

    started = _utcnow()
    try:
        result = await provider.suggest_curriculum_mapping(
            CurriculumMappingProposalInput(
                question_version_id=qv.id,
                curriculum_id=curriculum_id,
                prompt_text=qv.prompt_text,
                stable_code=stable,
                candidate_nodes=[
                    CurriculumNodeHint(
                        curriculum_node_id=n.id,
                        code=n.code,
                        name=n.name,
                        node_type=n.node_type,
                    )
                    for n in nodes
                ],
                instructions=instructions,
            )
        )
        # Store proposal only — teacher applies mappings manually; do not auto-write.
        # Optionally create mappings as REVIEW suggestions via payload.
        created = 0
        for mapping in result.mappings:
            exists = await db.scalar(
                select(QuestionCurriculumMapping).where(
                    QuestionCurriculumMapping.tenant_id == tenant_id,
                    QuestionCurriculumMapping.question_version_id == qv.id,
                    QuestionCurriculumMapping.curriculum_node_id
                    == mapping.curriculum_node_id,
                    QuestionCurriculumMapping.mapping_type == mapping.mapping_type,
                )
            )
            if exists is not None:
                continue
            row = QuestionCurriculumMapping(
                tenant_id=tenant_id,
                question_version_id=qv.id,
                curriculum_node_id=mapping.curriculum_node_id,
                mapping_type=mapping.mapping_type,
                weight=mapping.weight,
            )
            db.add(row)
            created += 1
        run.proposal_payload = {
            "mappings": [m.model_dump(mode="json") for m in result.mappings],
            "created_count": created,
        }
        run.status = "REVIEW_REQUIRED" if result.mappings else "SUCCEEDED"
        run.finished_at = _utcnow()
        await record_ai_execution(
            db,
            tenant_id=tenant_id,
            operation="suggest_curriculum_mapping",
            provider=provider.provider_name,
            status="SUCCEEDED",
            request_summary=redacted_request_summary(
                operation="suggest_curriculum_mapping",
                entity_ids={
                    "authoring_ai_run_id": str(run.id),
                    "question_version_id": str(qv.id),
                },
            ),
            response_summary={
                "mapping_count": len(result.mappings),
                "created_count": created,
            },
            authoring_ai_run_id=run.id,
            assessment_version_id=run.assessment_version_id,
            input_hash=run.input_hash,
            started_at=started,
            finished_at=_utcnow(),
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("curriculum mapping propose failed run_id=%s", run.id)
        run.status = "FAILED"
        run.failure_code = "AUTHORING_AI_FAILED"
        run.failure_detail = str(exc)[:500]
        run.finished_at = _utcnow()
        await db.commit()
