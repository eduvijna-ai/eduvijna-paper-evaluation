"""Redacted AI execution tracing helpers."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AiExecutionRecord


def canonical_input_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def redacted_request_summary(
    *,
    operation: str,
    entity_ids: dict[str, str | None],
    input_refs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        **{k: v for k, v in entity_ids.items() if v is not None},
        "input_ref_keys": sorted((input_refs or {}).keys())[:20],
    }


def redacted_transcription_response_summary(
    *,
    confidence: float | None,
    unreadable: bool,
    text: str,
    segment_count: int,
) -> dict[str, Any]:
    return {
        "character_count": len(text),
        "segment_count": segment_count,
        "confidence": confidence,
        "unreadable": unreadable,
        "output_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def redacted_evaluation_response_summary(
    *,
    proposed_total: float | None,
    evaluation_confidence: float | None,
    criterion_count: int,
    error_codes: list[str],
    ecf_applied: bool,
    workflow_hint: str | None = None,
) -> dict[str, Any]:
    return {
        "proposed_total": proposed_total,
        "evaluation_confidence": evaluation_confidence,
        "criterion_count": criterion_count,
        "error_codes": error_codes[:20],
        "ecf_applied": ecf_applied,
        "workflow_hint": workflow_hint,
    }


async def record_ai_execution(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    operation: str,
    provider: str,
    status: str,
    request_summary: dict[str, Any],
    response_summary: dict[str, Any],
    submission_id: uuid.UUID | None = None,
    answer_region_id: uuid.UUID | None = None,
    evaluation_run_id: uuid.UUID | None = None,
    question_evaluation_id: uuid.UUID | None = None,
    model: str | None = None,
    model_version: str | None = None,
    prompt_template_version: str | None = None,
    input_refs: dict[str, Any] | None = None,
    input_hash: str | None = None,
    latency_ms: int | None = None,
    token_usage: dict[str, Any] | None = None,
    error_class: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> AiExecutionRecord:
    row = AiExecutionRecord(
        tenant_id=tenant_id,
        operation=operation,
        provider=provider,
        status=status,
        request_summary=request_summary,
        response_summary=response_summary,
        submission_id=submission_id,
        answer_region_id=answer_region_id,
        evaluation_run_id=evaluation_run_id,
        question_evaluation_id=question_evaluation_id,
        model=model,
        model_version=model_version,
        prompt_template_version=prompt_template_version,
        input_refs=input_refs or {},
        input_hash=input_hash,
        latency_ms=latency_ms,
        token_usage=token_usage or {},
        error_class=error_class,
        started_at=started_at,
        finished_at=finished_at or datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row
