"""Transcription pipeline services (B5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.registry import get_structure_provider, structure_provider_active
from app.ai.tracing import (
    canonical_input_hash,
    record_ai_execution,
    redacted_request_summary,
    redacted_transcription_response_summary,
)
from app.ai.types import ProviderUnavailable, TranscriptionInput
from app.core.config import Settings, get_settings
from app.db.models import (
    AnswerRegion,
    AnswerRegionTranscription,
    PipelineJob,
    QuestionAnswerMapping,
    QuestionAnswerMappingRegion,
    QuestionVersion,
    Submission,
    SubmissionPage,
)
from app.services.audit import add_audit_event
from app.services.crop_generation import ensure_region_crop
from app.services.storage import ObjectStorage


class TranscriptionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def ensure_transcription_job_and_state(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
    settings: Settings | None = None,
) -> PipelineJob | None:
    """Initialize transcription after mapping finalize. Idempotent."""
    settings = settings or get_settings()
    if submission.workflow_state != "READY_FOR_EVALUATION":
        raise TranscriptionError(
            "INVALID_WORKFLOW_STATE",
            "Transcription requires READY_FOR_EVALUATION",
        )

    if submission.transcription_state == "READY":
        return None

    if submission.transcription_state in {"QUEUED", "RUNNING"}:
        job = await db.scalar(
            select(PipelineJob)
            .where(
                PipelineJob.tenant_id == tenant_id,
                PipelineJob.submission_id == submission.id,
                PipelineJob.stage == "TRANSCRIPTION",
            )
            .order_by(PipelineJob.created_at.desc())
            .limit(1)
        )
        return job

    if not structure_provider_active(settings):
        submission.transcription_state = "REVIEW_REQUIRED"
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=None,
            entity_type="Submission",
            entity_id=submission.id,
            action="transcription_manual_required",
            after={"reason": "provider_none"},
        )
        await db.flush()
        return None

    existing = await db.scalar(
        select(PipelineJob)
        .where(
            PipelineJob.tenant_id == tenant_id,
            PipelineJob.idempotency_key == f"transcription:{submission.id}:v1",
        )
        .limit(1)
    )
    if existing is not None:
        if existing.status in {"QUEUED", "RUNNING"}:
            submission.transcription_state = "QUEUED"
            return existing
        if existing.status == "FAILED":
            existing.status = "QUEUED"
            existing.attempt = existing.attempt + 1
            existing.error_code = None
            existing.error_detail = None
            existing.started_at = None
            existing.finished_at = None
            submission.transcription_state = "QUEUED"
            await db.flush()
            return existing
        if existing.status == "SUCCEEDED" and submission.transcription_state != "READY":
            # Allow prepare/retry to re-queue after partial failure states.
            if submission.transcription_state in {"FAILED", "UNAVAILABLE", "NOT_STARTED"}:
                existing.status = "QUEUED"
                existing.attempt = existing.attempt + 1
                existing.error_code = None
                existing.error_detail = None
                existing.started_at = None
                existing.finished_at = None
                submission.transcription_state = "QUEUED"
                await db.flush()
                return existing
        return existing

    job = PipelineJob(
        tenant_id=tenant_id,
        submission_id=submission.id,
        stage="TRANSCRIPTION",
        status="QUEUED",
        attempt=1,
        idempotency_key=f"transcription:{submission.id}:v1",
    )
    db.add(job)
    submission.transcription_state = "QUEUED"
    await db.flush()
    return job


async def run_transcription_pipeline(
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
        raise TranscriptionError("NOT_FOUND", "Submission or job not found")

    if job.status == "SUCCEEDED" and submission.transcription_state in {
        "REVIEW_REQUIRED",
        "READY",
    }:
        return

    job.status = "RUNNING"
    job.started_at = datetime.now(UTC)
    job.attempt = max(job.attempt, 1)
    submission.transcription_state = "RUNNING"
    await db.commit()

    try:
        if not structure_provider_active(settings):
            submission.transcription_state = "REVIEW_REQUIRED"
            job.status = "SUCCEEDED"
            job.finished_at = datetime.now(UTC)
            await db.commit()
            return

        provider = get_structure_provider(settings)
        mappings = list(
            (
                await db.scalars(
                    select(QuestionAnswerMapping).where(
                        QuestionAnswerMapping.tenant_id == tenant_id,
                        QuestionAnswerMapping.submission_id == submission_id,
                        QuestionAnswerMapping.disposition == "ANSWERED",
                        QuestionAnswerMapping.mapping_state == "CONFIRMED",
                    )
                )
            ).all()
        )
        mappings.sort(key=lambda m: str(m.question_version_id))

        for mapping in mappings:
            links = list(
                (
                    await db.scalars(
                        select(QuestionAnswerMappingRegion)
                        .where(
                            QuestionAnswerMappingRegion.tenant_id == tenant_id,
                            QuestionAnswerMappingRegion.mapping_id == mapping.id,
                        )
                        .order_by(QuestionAnswerMappingRegion.sequence.asc())
                    )
                ).all()
            )
            qv = await db.scalar(
                select(QuestionVersion).where(
                    QuestionVersion.id == mapping.question_version_id,
                    QuestionVersion.tenant_id == tenant_id,
                )
            )
            for link in links:
                region = await db.scalar(
                    select(AnswerRegion).where(
                        AnswerRegion.id == link.answer_region_id,
                        AnswerRegion.tenant_id == tenant_id,
                    )
                )
                if region is None or region.ignored:
                    continue
                if region.region_type in {"IDENTITY", "SCRATCH"}:
                    continue
                if region.region_type == "DIAGRAM":
                    # Diagrams await human visual_only acknowledgment; no auto OCR.
                    continue

                page = await db.scalar(
                    select(SubmissionPage).where(
                        SubmissionPage.id == region.submission_page_id,
                        SubmissionPage.tenant_id == tenant_id,
                    )
                )
                if page is None:
                    continue

                # Skip if an active AI proposal already exists for this region.
                existing = await db.scalar(
                    select(AnswerRegionTranscription)
                    .where(
                        AnswerRegionTranscription.tenant_id == tenant_id,
                        AnswerRegionTranscription.answer_region_id == region.id,
                        AnswerRegionTranscription.source_type == "AI",
                        AnswerRegionTranscription.status.in_(
                            ["PROPOSED", "REVIEW_REQUIRED", "CONFIRMED"]
                        ),
                    )
                    .order_by(AnswerRegionTranscription.version_number.desc())
                    .limit(1)
                )
                if existing is not None:
                    continue

                crop_key, crop_hash = await ensure_region_crop(
                    db,
                    tenant_id=tenant_id,
                    submission_id=submission.id,
                    region=region,
                    page=page,
                    storage=storage,
                    settings=settings,
                )
                # Verify hash still matches stored object.
                stored = storage.get_bytes(crop_key)
                from app.services.upload_validation import sha256_bytes

                if sha256_bytes(stored) != crop_hash:
                    raise TranscriptionError(
                        "CROP_INTEGRITY_MISMATCH",
                        "Crop hash does not match stored bytes",
                    )

                request = TranscriptionInput(
                    submission_id=submission.id,
                    answer_region_id=region.id,
                    question_label=qv.display_label if qv else None,
                    question_type=None,
                    crop_content_sha256=crop_hash,
                )
                started = datetime.now(UTC)
                input_hash = canonical_input_hash(request.model_dump(mode="json"))
                response_summary: dict[str, Any]
                try:
                    result = await provider.transcribe_answer(request)
                    status = "SUCCEEDED"
                    error_class = None
                    response_summary = redacted_transcription_response_summary(
                        confidence=float(result.transcription_confidence),
                        unreadable=result.unreadable,
                        text=result.text,
                        segment_count=len(result.segments),
                    )
                except ProviderUnavailable as exc:
                    status = "UNAVAILABLE"
                    error_class = "ProviderUnavailable"
                    result = None
                    response_summary = {"error": str(exc)[:200]}
                except Exception as exc:
                    status = "FAILED"
                    error_class = type(exc).__name__
                    result = None
                    response_summary = {"error": str(exc)[:200]}

                finished = datetime.now(UTC)
                exec_row = await record_ai_execution(
                    db,
                    tenant_id=tenant_id,
                    operation="transcribe_answer",
                    provider=provider.provider_name,
                    status=status,
                    request_summary=redacted_request_summary(
                        operation="transcribe_answer",
                        entity_ids={
                            "submission_id": str(submission.id),
                            "answer_region_id": str(region.id),
                        },
                        input_refs={"crop_content_sha256": crop_hash},
                    ),
                    response_summary=response_summary,
                    submission_id=submission.id,
                    answer_region_id=region.id,
                    model=settings.ai_model_transcription,
                    input_refs={
                        "crop_storage_key": crop_key,
                        "crop_content_sha256": crop_hash,
                    },
                    input_hash=input_hash,
                    latency_ms=int((finished - started).total_seconds() * 1000),
                    error_class=error_class,
                    started_at=started,
                    finished_at=finished,
                )

                if result is None:
                    continue

                max_version = await db.scalar(
                    select(
                        func.coalesce(
                            func.max(AnswerRegionTranscription.version_number), 0
                        )
                    ).where(
                        AnswerRegionTranscription.tenant_id == tenant_id,
                        AnswerRegionTranscription.answer_region_id == region.id,
                    )
                )
                version_number = int(max_version or 0) + 1
                row = AnswerRegionTranscription(
                    tenant_id=tenant_id,
                    answer_region_id=region.id,
                    version_number=version_number,
                    source_type="AI",
                    text=result.text,
                    latex=result.latex,
                    segments=[s.model_dump(mode="json") for s in result.segments],
                    transcription_confidence=result.transcription_confidence,
                    unreadable=result.unreadable,
                    visual_only=False,
                    status="REVIEW_REQUIRED",
                    ai_execution_record_id=exec_row.id,
                    created_by=None,
                )
                db.add(row)
                # Projection for backward compatibility — never auto-confirm.
                region.transcription = result.text
                region.transcription_confidence = result.transcription_confidence

        submission.transcription_state = "REVIEW_REQUIRED"
        job.status = "SUCCEEDED"
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        job.error_detail = None
        await add_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=None,
            entity_type="Submission",
            entity_id=submission.id,
            action="transcription_pipeline_succeeded",
            after={"job_id": str(job.id)},
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        job = await db.scalar(select(PipelineJob).where(PipelineJob.id == job_id))
        submission = await db.scalar(
            select(Submission).where(Submission.id == submission_id)
        )
        if job is not None and submission is not None:
            code = getattr(exc, "code", "TRANSCRIPTION_FAILED")
            message = getattr(exc, "message", str(exc))
            job.status = "FAILED"
            job.error_code = str(code)[:100]
            job.error_detail = str(message)[:4000]
            job.finished_at = datetime.now(UTC)
            submission.transcription_state = "FAILED"
            await db.commit()
        raise


def _latest_active_transcription(
    rows: list[AnswerRegionTranscription],
) -> AnswerRegionTranscription | None:
    active = [r for r in rows if r.status != "SUPERSEDED"]
    if not active:
        return None
    return max(active, key=lambda r: r.version_number)


async def build_transcription_workspace(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
) -> dict[str, Any]:
    mappings = list(
        (
            await db.scalars(
                select(QuestionAnswerMapping).where(
                    QuestionAnswerMapping.tenant_id == tenant_id,
                    QuestionAnswerMapping.submission_id == submission.id,
                )
            )
        ).all()
    )
    mappings.sort(key=lambda m: str(m.question_version_id))

    items: list[dict[str, Any]] = []
    reviewed = 0
    required = 0

    for mapping in mappings:
        qv = await db.scalar(
            select(QuestionVersion).where(QuestionVersion.id == mapping.question_version_id)
        )
        links = list(
            (
                await db.scalars(
                    select(QuestionAnswerMappingRegion)
                    .where(
                        QuestionAnswerMappingRegion.tenant_id == tenant_id,
                        QuestionAnswerMappingRegion.mapping_id == mapping.id,
                    )
                    .order_by(QuestionAnswerMappingRegion.sequence.asc())
                )
            ).all()
        )
        region_payloads: list[dict[str, Any]] = []
        if mapping.disposition == "BLANK":
            items.append(
                {
                    "question_version_id": str(mapping.question_version_id),
                    "question_label": qv.display_label if qv else str(mapping.question_version_id),
                    "disposition": mapping.disposition,
                    "mapping_state": mapping.mapping_state,
                    "regions": [],
                    "requires_transcription": False,
                }
            )
            continue

        for link in links:
            region = await db.scalar(
                select(AnswerRegion).where(
                    AnswerRegion.id == link.answer_region_id,
                    AnswerRegion.tenant_id == tenant_id,
                )
            )
            if region is None:
                continue
            if region.region_type in {"IDENTITY", "SCRATCH"} or region.ignored:
                continue

            needs = region.region_type in {"ANSWER", "DIAGRAM"}
            if needs:
                required += 1

            versions = list(
                (
                    await db.scalars(
                        select(AnswerRegionTranscription)
                        .where(
                            AnswerRegionTranscription.tenant_id == tenant_id,
                            AnswerRegionTranscription.answer_region_id == region.id,
                        )
                        .order_by(AnswerRegionTranscription.version_number.asc())
                    )
                ).all()
            )
            active = _latest_active_transcription(versions)
            ai_proposal = next(
                (
                    v
                    for v in reversed(versions)
                    if v.source_type == "AI" and v.status != "SUPERSEDED"
                ),
                None,
            )
            if active is not None and active.status == "CONFIRMED":
                reviewed += 1

            page = await db.scalar(
                select(SubmissionPage).where(SubmissionPage.id == region.submission_page_id)
            )
            crop_url = (
                f"/api/v1/answer-regions/{region.id}/crop"
                if region.crop_storage_key
                else None
            )
            page_url = (
                f"/api/v1/submissions/{submission.id}/pages/{page.page_index}/image"
                if page is not None
                else None
            )

            def dump_tx(tx: AnswerRegionTranscription | None) -> dict[str, Any] | None:
                if tx is None:
                    return None
                return {
                    "id": str(tx.id),
                    "answer_region_id": str(tx.answer_region_id),
                    "version_number": tx.version_number,
                    "source_type": tx.source_type,
                    "text": tx.text,
                    "latex": tx.latex,
                    "segments": tx.segments or [],
                    "transcription_confidence": (
                        float(tx.transcription_confidence)
                        if tx.transcription_confidence is not None
                        else None
                    ),
                    "unreadable": tx.unreadable,
                    "visual_only": tx.visual_only,
                    "status": tx.status,
                    "confirmed_by": str(tx.confirmed_by) if tx.confirmed_by else None,
                    "confirmed_at": tx.confirmed_at.isoformat() if tx.confirmed_at else None,
                    "created_at": tx.created_at.isoformat(),
                    "updated_at": tx.updated_at.isoformat(),
                }

            region_payloads.append(
                {
                    "id": str(region.id),
                    "label": region.label,
                    "region_type": region.region_type,
                    "source_type": region.source_type,
                    "detection_confidence": float(region.detection_confidence),
                    "bbox": {
                        "x": float(region.bbox_x),
                        "y": float(region.bbox_y),
                        "width": float(region.bbox_width),
                        "height": float(region.bbox_height),
                    },
                    "crop_url": crop_url,
                    "page_image_url": page_url,
                    "page_index": page.page_index if page else None,
                    "latest_ai_proposal": dump_tx(ai_proposal),
                    "active_transcription": dump_tx(active),
                    "requires_transcription": needs,
                }
            )

        items.append(
            {
                "question_version_id": str(mapping.question_version_id),
                "question_label": qv.display_label if qv else str(mapping.question_version_id),
                "disposition": mapping.disposition,
                "mapping_state": mapping.mapping_state,
                "regions": region_payloads,
                "requires_transcription": mapping.disposition == "ANSWERED",
            }
        )

    from app.ai.registry import structure_provider_active as spa

    return {
        "submission_id": str(submission.id),
        "workflow_state": submission.workflow_state,
        "transcription_state": submission.transcription_state,
        "automated_transcription_active": spa(),
        "progress": {
            "reviewed": reviewed,
            "required": required,
            "label": f"{reviewed} of {required} evidence regions reviewed",
        },
        "items": items,
    }


async def put_manual_transcription(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    region: AnswerRegion,
    text: str | None,
    latex: str | None,
    unreadable: bool,
    visual_only: bool,
) -> AnswerRegionTranscription:
    versions = list(
        (
            await db.scalars(
                select(AnswerRegionTranscription).where(
                    AnswerRegionTranscription.tenant_id == tenant_id,
                    AnswerRegionTranscription.answer_region_id == region.id,
                    AnswerRegionTranscription.status.in_(
                        ["PROPOSED", "REVIEW_REQUIRED", "CONFIRMED"]
                    ),
                )
            )
        ).all()
    )
    prior = _latest_active_transcription(versions)
    for v in versions:
        if v.status != "SUPERSEDED":
            v.status = "SUPERSEDED"

    max_version = await db.scalar(
        select(func.coalesce(func.max(AnswerRegionTranscription.version_number), 0)).where(
            AnswerRegionTranscription.tenant_id == tenant_id,
            AnswerRegionTranscription.answer_region_id == region.id,
        )
    )
    row = AnswerRegionTranscription(
        tenant_id=tenant_id,
        answer_region_id=region.id,
        version_number=int(max_version or 0) + 1,
        source_type="HUMAN",
        text=None if (unreadable or visual_only) else text,
        latex=None if (unreadable or visual_only) else latex,
        segments=[],
        transcription_confidence=None,
        unreadable=unreadable,
        visual_only=visual_only,
        status="REVIEW_REQUIRED",
        supersedes_transcription_id=prior.id if prior else None,
        created_by=user_id,
    )
    db.add(row)
    region.transcription = row.text
    # Do not fabricate human confidence as 1.0 — leave projection at prior AI or 0.
    if row.transcription_confidence is None:
        pass
    await db.flush()
    return row


async def confirm_transcription(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    transcription: AnswerRegionTranscription,
) -> AnswerRegionTranscription:
    if transcription.tenant_id != tenant_id:
        raise TranscriptionError("NOT_FOUND", "Transcription not found")
    if transcription.status == "SUPERSEDED":
        raise TranscriptionError("SUPERSEDED", "Cannot confirm a superseded transcription")
    # Never rewrite AI confidence on confirm.
    transcription.status = "CONFIRMED"
    transcription.confirmed_by = user_id
    transcription.confirmed_at = datetime.now(UTC)
    await db.flush()
    return transcription


async def finalize_transcription(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
) -> Submission:
    if submission.workflow_state != "READY_FOR_EVALUATION":
        raise TranscriptionError(
            "INVALID_WORKFLOW_STATE",
            "Submission must be READY_FOR_EVALUATION",
        )
    if submission.transcription_state in {"QUEUED", "RUNNING"}:
        raise TranscriptionError(
            "TRANSCRIPTION_RUNNING",
            "Transcription worker is still running",
        )

    mappings = list(
        (
            await db.scalars(
                select(QuestionAnswerMapping).where(
                    QuestionAnswerMapping.tenant_id == tenant_id,
                    QuestionAnswerMapping.submission_id == submission.id,
                )
            )
        ).all()
    )
    for mapping in mappings:
        if mapping.mapping_state != "CONFIRMED":
            raise TranscriptionError(
                "MAPPING_NOT_CONFIRMED",
                "All leaf mappings must remain CONFIRMED",
            )
        if mapping.disposition == "BLANK":
            continue
        links = list(
            (
                await db.scalars(
                    select(QuestionAnswerMappingRegion).where(
                        QuestionAnswerMappingRegion.tenant_id == tenant_id,
                        QuestionAnswerMappingRegion.mapping_id == mapping.id,
                    )
                )
            ).all()
        )
        for link in links:
            region = await db.scalar(
                select(AnswerRegion).where(
                    AnswerRegion.id == link.answer_region_id,
                    AnswerRegion.tenant_id == tenant_id,
                )
            )
            if region is None or region.ignored:
                continue
            if region.region_type in {"IDENTITY", "SCRATCH"}:
                continue
            versions = list(
                (
                    await db.scalars(
                        select(AnswerRegionTranscription).where(
                            AnswerRegionTranscription.tenant_id == tenant_id,
                            AnswerRegionTranscription.answer_region_id == region.id,
                        )
                    )
                ).all()
            )
            active = _latest_active_transcription(versions)
            if active is None or active.status != "CONFIRMED":
                raise TranscriptionError(
                    "TRANSCRIPTION_INCOMPLETE",
                    f"Region {region.id} lacks a confirmed transcription outcome",
                )
            if not (active.unreadable or active.visual_only or (active.text is not None)):
                raise TranscriptionError(
                    "TRANSCRIPTION_INCOMPLETE",
                    f"Region {region.id} confirmation missing outcome",
                )
            # Stale crop check for transcribed (non-visual) evidence.
            if region.crop_storage_key and region.crop_content_sha256:
                from app.services.crop_generation import bbox_fingerprint, derived_region_crop_key

                expected = derived_region_crop_key(
                    tenant_id,
                    submission.id,
                    region.id,
                    bbox_fingerprint(
                        x=region.bbox_x,
                        y=region.bbox_y,
                        width=region.bbox_width,
                        height=region.bbox_height,
                    ),
                )
                if region.crop_storage_key != expected:
                    raise TranscriptionError(
                        "CROP_STALE",
                        f"Region {region.id} crop is stale relative to bbox",
                    )

    submission.transcription_state = "READY"
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=None,
        entity_type="Submission",
        entity_id=submission.id,
        action="transcription_finalized",
        after={
            "transcription_state": "READY",
            "workflow_state": submission.workflow_state,
            "evaluation_enqueued": False,
        },
    )
    await db.flush()
    return submission
