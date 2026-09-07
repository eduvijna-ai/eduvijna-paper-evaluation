"""AI page analysis + region/mapping proposals for B5."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.execution_metadata import metadata_from_provider
from app.ai.registry import get_structure_provider, structure_provider_active
from app.ai.tracing import (
    canonical_input_hash,
    record_ai_execution,
    redacted_request_summary,
)
from app.ai.types import (
    PageAnalysisInput,
    ProviderUnavailable,
    RegionMappingInput,
)
from app.core.config import Settings, get_settings
from app.db.models import (
    AnswerRegion,
    QuestionAnswerMapping,
    QuestionAnswerMappingRegion,
    QuestionVersion,
    Submission,
    SubmissionPage,
    SubmissionPageAnalysis,
)
from app.services.audit import add_audit_event


async def apply_ai_mapping_proposals(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission: Submission,
    pages: list[SubmissionPage],
    leaves: list[QuestionVersion],
    settings: Settings | None = None,
) -> dict[str, bool | int]:
    """Analyze pages, propose regions/mappings when a structure provider is active.

    Idempotent: never silently overwrite human regions/mappings.
    """
    settings = settings or get_settings()
    automated_region = False
    automated_mapping = False
    region_count = 0
    mapping_count = 0

    if not structure_provider_active(settings):
        return {
            "automated_region_detection_active": False,
            "automated_mapping_active": False,
            "ai_region_count": 0,
            "ai_mapping_count": 0,
        }

    provider = get_structure_provider(settings)
    question_labels = [q.display_label or str(q.id) for q in leaves][:100]

    existing_regions = list(
        (
            await db.scalars(
                select(AnswerRegion).where(
                    AnswerRegion.tenant_id == tenant_id,
                    AnswerRegion.submission_page_id.in_([p.id for p in pages] or [uuid.uuid4()]),
                )
            )
        ).all()
    )
    has_human_regions = any(r.source_type == "HUMAN" for r in existing_regions)
    has_any_regions = len(existing_regions) > 0

    created_region_ids: list[uuid.UUID] = []

    if not has_any_regions and not has_human_regions:
        for page in sorted(pages, key=lambda p: p.page_index):
            request = PageAnalysisInput(
                submission_id=submission.id,
                page_id=page.id,
                page_index=page.page_index,
                question_labels=question_labels,
            )
            started = datetime.now(UTC)
            input_hash = canonical_input_hash(request.model_dump(mode="json"))
            response_summary: dict[str, Any]
            try:
                result = await provider.analyze_page(request)
                status = "SUCCEEDED"
                error_class = None
                response_summary = {
                    "zone_count": len(result.proposed_zones),
                    "label_count": len(result.printed_labels),
                }
            except ProviderUnavailable as exc:
                status = "UNAVAILABLE"
                error_class = "ProviderUnavailable"
                response_summary = {"error": str(exc)[:200]}
                result = None
            except Exception as exc:
                status = "FAILED"
                error_class = type(exc).__name__
                response_summary = {"error": str(exc)[:200]}
                result = None

            finished = datetime.now(UTC)
            meta = metadata_from_provider(provider, "analyze_page")
            exec_row = await record_ai_execution(
                db,
                tenant_id=tenant_id,
                operation="analyze_page",
                status=status,
                request_summary=redacted_request_summary(
                    operation="analyze_page",
                    entity_ids={
                        "submission_id": str(submission.id),
                        "page_id": str(page.id),
                    },
                ),
                response_summary=response_summary,
                submission_id=submission.id,
                input_refs={"page_id": str(page.id), "page_index": page.page_index},
                input_hash=input_hash,
                latency_ms=int((finished - started).total_seconds() * 1000),
                error_class=error_class,
                started_at=started,
                finished_at=finished,
                provider=meta.provider,
                model=meta.model,
                model_version=meta.model_version,
                prompt_template_version=meta.prompt_template_version,
            )

            existing_analysis = await db.scalar(
                select(SubmissionPageAnalysis).where(
                    SubmissionPageAnalysis.tenant_id == tenant_id,
                    SubmissionPageAnalysis.submission_page_id == page.id,
                    SubmissionPageAnalysis.analysis_version == 1,
                )
            )
            payload = result.model_dump(mode="json") if result else {}
            if existing_analysis is None:
                db.add(
                    SubmissionPageAnalysis(
                        tenant_id=tenant_id,
                        submission_page_id=page.id,
                        analysis_version=1,
                        status=(
                            status if status in {"SUCCEEDED", "FAILED", "UNAVAILABLE"} else "FAILED"
                        ),
                        result_json=payload,
                        ai_execution_record_id=exec_row.id,
                    )
                )
            else:
                existing_analysis.status = (
                    status
                    if status
                    in {
                        "SUCCEEDED",
                        "FAILED",
                        "UNAVAILABLE",
                    }
                    else "FAILED"
                )
                existing_analysis.result_json = payload
                existing_analysis.ai_execution_record_id = exec_row.id

            if result is None:
                continue

            automated_region = True
            for zone in result.proposed_zones:
                region = AnswerRegion(
                    tenant_id=tenant_id,
                    submission_page_id=page.id,
                    label=zone.label[:255],
                    bbox_x=Decimal(str(zone.bbox.x)),
                    bbox_y=Decimal(str(zone.bbox.y)),
                    bbox_width=Decimal(str(zone.bbox.width)),
                    bbox_height=Decimal(str(zone.bbox.height)),
                    region_type=zone.region_type,
                    source_type="AI",
                    detection_confidence=zone.confidence,
                    is_continuation=zone.is_continuation,
                    created_by=submission.uploaded_by,
                )
                db.add(region)
                await db.flush()
                created_region_ids.append(region.id)
                region_count += 1

    # Refresh region list for mapping.
    all_regions = list(
        (
            await db.scalars(
                select(AnswerRegion).where(
                    AnswerRegion.tenant_id == tenant_id,
                    AnswerRegion.submission_page_id.in_([p.id for p in pages] or [uuid.uuid4()]),
                    AnswerRegion.ignored.is_(False),
                )
            )
        ).all()
    )
    answer_regions = [r for r in all_regions if r.region_type == "ANSWER"]

    existing_mappings = list(
        (
            await db.scalars(
                select(QuestionAnswerMapping).where(
                    QuestionAnswerMapping.tenant_id == tenant_id,
                    QuestionAnswerMapping.submission_id == submission.id,
                )
            )
        ).all()
    )
    if existing_mappings:
        return {
            "automated_region_detection_active": automated_region,
            "automated_mapping_active": False,
            "ai_region_count": region_count,
            "ai_mapping_count": 0,
        }

    if not answer_regions or not leaves:
        return {
            "automated_region_detection_active": automated_region,
            "automated_mapping_active": False,
            "ai_region_count": region_count,
            "ai_mapping_count": 0,
        }

    leaf_ids = [q.id for q in leaves]
    region_ids = [r.id for r in answer_regions]
    allowed_region_ids = set(region_ids)
    allowed_qv = set(leaf_ids)

    map_request = RegionMappingInput(
        submission_id=submission.id,
        assessment_version_id=submission.assessment_version_id,
        question_version_ids=leaf_ids,
        region_ids=region_ids,
    )
    started = datetime.now(UTC)
    input_hash = canonical_input_hash(map_request.model_dump(mode="json"))
    map_response_summary: dict[str, Any]
    try:
        map_result = await provider.map_answer_regions(map_request)
        status = "SUCCEEDED"
        error_class = None
        map_response_summary = {
            "mapping_count": len(map_result.mappings),
            "confidence": float(map_result.mapping_confidence),
            "unmapped_count": len(map_result.unmapped_region_ids),
        }
    except ProviderUnavailable as exc:
        status = "UNAVAILABLE"
        error_class = "ProviderUnavailable"
        map_response_summary = {"error": str(exc)[:200]}
        map_result = None
    except Exception as exc:
        status = "FAILED"
        error_class = type(exc).__name__
        map_response_summary = {"error": str(exc)[:200]}
        map_result = None

    finished = datetime.now(UTC)
    map_meta = metadata_from_provider(provider, "map_answer_regions")
    await record_ai_execution(
        db,
        tenant_id=tenant_id,
        operation="map_answer_regions",
        status=status,
        request_summary=redacted_request_summary(
            operation="map_answer_regions",
            entity_ids={
                "submission_id": str(submission.id),
                "assessment_version_id": str(submission.assessment_version_id),
            },
        ),
        response_summary=map_response_summary,
        submission_id=submission.id,
        input_refs={
            "region_count": len(region_ids),
            "question_count": len(leaf_ids),
        },
        input_hash=input_hash,
        latency_ms=int((finished - started).total_seconds() * 1000),
        error_class=error_class,
        started_at=started,
        finished_at=finished,
        provider=map_meta.provider,
        model=map_meta.model,
        model_version=map_meta.model_version,
        prompt_template_version=map_meta.prompt_template_version,
    )

    if map_result is None:
        return {
            "automated_region_detection_active": automated_region,
            "automated_mapping_active": False,
            "ai_region_count": region_count,
            "ai_mapping_count": 0,
        }

    questions_by_qv = {qv.id: qv for qv in leaves}

    used_regions: set[uuid.UUID] = set()
    for proposed in map_result.mappings:
        if proposed.question_version_id not in allowed_qv:
            continue
        valid_regions = [
            rid
            for rid in proposed.region_ids
            if rid in allowed_region_ids and rid not in used_regions
        ]
        if not valid_regions:
            continue
        qv = questions_by_qv[proposed.question_version_id]
        mapping = QuestionAnswerMapping(
            tenant_id=tenant_id,
            submission_id=submission.id,
            question_id=qv.question_id,
            question_version_id=qv.id,
            disposition="ANSWERED",
            mapping_state="REVIEW_REQUIRED",
            mapping_confidence=proposed.mapping_confidence,
            mapped_by="AI",
            confirmed_by=None,
            confirmed_at=None,
        )
        db.add(mapping)
        await db.flush()
        for seq, rid in enumerate(valid_regions):
            used_regions.add(rid)
            db.add(
                QuestionAnswerMappingRegion(
                    tenant_id=tenant_id,
                    mapping_id=mapping.id,
                    answer_region_id=rid,
                    sequence=seq,
                )
            )
        mapping_count += 1
        automated_mapping = True

    submission.mapping_confidence = map_result.mapping_confidence
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=None,
        entity_type="Submission",
        entity_id=submission.id,
        action="ai_mapping_proposals_applied",
        after={
            "ai_region_count": region_count,
            "ai_mapping_count": mapping_count,
            "provider": provider.provider_name,
        },
    )
    return {
        "automated_region_detection_active": automated_region,
        "automated_mapping_active": automated_mapping,
        "ai_region_count": region_count,
        "ai_mapping_count": mapping_count,
    }
