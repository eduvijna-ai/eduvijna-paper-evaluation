# ruff: noqa: B008
"""B4 answer-region and question-mapping review APIs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.models import (
    AnswerRegion,
    Assessment,
    AuditEvent,
    PipelineJob,
    Question,
    QuestionAnswerMapping,
    QuestionAnswerMappingRegion,
    QuestionVersion,
    Student,
    Submission,
    SubmissionPage,
)
from app.db.session import get_db_session
from app.services.mapping_prepare import leaf_scorable_questions
from app.tasks import enqueue_mapping_preparation

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db_session)]

ASSIGNABLE_REGION_TYPES = frozenset({"ANSWER", "DIAGRAM"})


class NormalizedBBoxIn(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> NormalizedBBoxIn:
        if self.x + self.width > 1 + 1e-9 or self.y + self.height > 1 + 1e-9:
            raise ValueError("bbox must stay within the normalized page")
        return self


class AnswerRegionCreateIn(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    region_type: Literal["ANSWER", "SCRATCH", "DIAGRAM", "IDENTITY"]
    bbox: NormalizedBBoxIn


class AnswerRegionPatchIn(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    region_type: Literal["ANSWER", "SCRATCH", "DIAGRAM", "IDENTITY"] | None = None
    bbox: NormalizedBBoxIn | None = None
    crossed_out: bool | None = None
    ignored: bool | None = None
    is_continuation: bool | None = None


class PagePatchIn(BaseModel):
    is_continuation: bool


class QuestionMappingIn(BaseModel):
    disposition: Literal["ANSWERED", "BLANK"]
    region_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("region_ids")
    @classmethod
    def unique_regions(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("region_ids must be unique")
        return value


def _http_error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    detail.update(extra)
    return HTTPException(status_code=status, detail=detail)


async def _audit(
    db: AsyncSession,
    auth: AuthContext,
    entity: Any,
    action: str,
    payload: dict[str, Any],
) -> None:
    db.add(
        AuditEvent(
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            entity_type=entity.__class__.__name__,
            entity_id=entity.id,
            action=action,
            payload_json=payload,
        )
    )


def _dump_submission(
    item: Submission,
    *,
    assessment_title: str | None = None,
    student_display_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "tenant_id": str(item.tenant_id),
        "assessment_id": str(item.assessment_id),
        "assessment_version_id": str(item.assessment_version_id),
        "assessment_title": assessment_title,
        "student_id": str(item.student_id) if item.student_id else None,
        "student_display_name": student_display_name,
        "workflow_state": item.workflow_state,
        "student_match_state": item.student_match_state,
        "roll_number_detected": item.roll_number_detected,
        "name_detected": item.name_detected,
        "identity_confidence": float(item.identity_confidence),
        "mapping_confidence": float(item.mapping_confidence),
        "source_storage_key": item.source_storage_key,
        "source_content_sha256": item.source_content_sha256,
        "original_filename": item.original_filename,
        "mime_type": item.mime_type,
        "byte_size": item.byte_size,
        "storage_status": item.storage_status,
        "page_count": item.page_count,
        "bundle_name": item.bundle_name,
        "uploaded_by": str(item.uploaded_by),
        "uploaded_at": item.uploaded_at.isoformat(),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _dump_page(page: SubmissionPage) -> dict[str, Any]:
    return {
        "id": str(page.id),
        "tenant_id": str(page.tenant_id),
        "submission_id": str(page.submission_id),
        "page_index": page.page_index,
        "page_number": page.page_index + 1,
        "label": f"Page {page.page_index + 1}",
        "width": page.width,
        "height": page.height,
        "is_continuation": page.is_continuation,
        "created_at": page.created_at.isoformat(),
    }


def _dump_region(region: AnswerRegion, page: SubmissionPage) -> dict[str, Any]:
    x = float(region.bbox_x)
    y = float(region.bbox_y)
    width = float(region.bbox_width)
    height = float(region.bbox_height)
    return {
        "id": str(region.id),
        "tenant_id": str(region.tenant_id),
        "submission_page_id": str(region.submission_page_id),
        "page_id": str(region.submission_page_id),
        "page_number": page.page_index + 1,
        "label": region.label,
        "bbox": {"x": x, "y": y, "width": width, "height": height},
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "region_type": region.region_type,
        "source_type": region.source_type,
        "detection_confidence": float(region.detection_confidence),
        "confidence": float(region.detection_confidence),
        "crossed_out": region.crossed_out,
        "ignored": region.ignored,
        "is_continuation": region.is_continuation,
        "transcription": region.transcription,
        "transcription_confidence": float(region.transcription_confidence),
        "question_id": None,
        "created_by": str(region.created_by),
        "created_at": region.created_at.isoformat(),
        "updated_at": region.updated_at.isoformat(),
    }


async def _scoped_submission(
    db: AsyncSession, submission_id: uuid.UUID, tenant_id: uuid.UUID
) -> Submission:
    item = await db.scalar(
        select(Submission).where(
            Submission.id == submission_id,
            Submission.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    return item


async def _assessment_title(db: AsyncSession, assessment_id: uuid.UUID) -> str | None:
    title = await db.scalar(select(Assessment.title).where(Assessment.id == assessment_id))
    return str(title) if title is not None else None


async def _student_name(db: AsyncSession, student_id: uuid.UUID | None) -> str | None:
    if student_id is None:
        return None
    name = await db.scalar(select(Student.full_name).where(Student.id == student_id))
    return str(name) if name is not None else None


async def ensure_mapping_job_and_enqueue(
    db: AsyncSession,
    *,
    auth: AuthContext,
    submission: Submission,
) -> PipelineJob:
    key = f"mapping:{submission.id}:v1"
    job = await db.scalar(
        select(PipelineJob).where(
            PipelineJob.tenant_id == auth.tenant_id,
            PipelineJob.idempotency_key == key,
        )
    )
    if job is None:
        job = PipelineJob(
            tenant_id=auth.tenant_id,
            submission_id=submission.id,
            stage="MAPPING",
            status="QUEUED",
            attempt=1,
            idempotency_key=key,
        )
        db.add(job)
        await db.flush()
    elif job.status == "FAILED":
        job.status = "QUEUED"
        job.attempt = job.attempt + 1
        job.error_code = None
        job.error_detail = None
        job.started_at = None
        job.finished_at = None
        await db.flush()
    return job


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 6)))


async def _load_version_questions(
    db: AsyncSession, *, tenant_id: uuid.UUID, assessment_version_id: uuid.UUID
) -> list[QuestionVersion]:
    return list(
        (
            await db.scalars(
                select(QuestionVersion)
                .where(
                    QuestionVersion.tenant_id == tenant_id,
                    QuestionVersion.assessment_version_id == assessment_version_id,
                )
                .order_by(QuestionVersion.sequence.asc())
            )
        ).all()
    )


def _build_question_tree(
    versions: list[QuestionVersion],
    questions_by_id: dict[uuid.UUID, Question],
) -> list[dict[str, Any]]:
    parent_ids = {
        v.parent_question_version_id
        for v in versions
        if v.parent_question_version_id is not None
    }
    by_id: dict[uuid.UUID, dict[str, Any]] = {}
    for version in versions:
        question = questions_by_id[version.question_id]
        is_leaf = version.id not in parent_ids and version.scoring_mode == "LEAF_SCORABLE"
        by_id[version.id] = {
            "id": str(version.id),
            "question_version_id": str(version.id),
            "question_id": str(version.question_id),
            "assessment_id": str(question.assessment_id),
            "parent_id": (
                str(version.parent_question_version_id)
                if version.parent_question_version_id
                else None
            ),
            "code": version.display_label or question.stable_code,
            "prompt": version.prompt_text,
            "max_mark": float(version.max_marks),
            "sort_order": version.sequence,
            "scoring_mode": version.scoring_mode,
            "is_leaf_scorable": is_leaf,
            "curriculum_node_ids": [],
            "children": [],
        }
    roots: list[dict[str, Any]] = []
    for version in versions:
        node = by_id[version.id]
        parent = version.parent_question_version_id
        if parent is None or parent not in by_id:
            roots.append(node)
        else:
            by_id[parent]["children"].append(node)
    return roots


async def _reopen_mappings_for_region(
    db: AsyncSession, *, auth: AuthContext, region_id: uuid.UUID
) -> None:
    links = list(
        (
            await db.scalars(
                select(QuestionAnswerMappingRegion).where(
                    QuestionAnswerMappingRegion.tenant_id == auth.tenant_id,
                    QuestionAnswerMappingRegion.answer_region_id == region_id,
                )
            )
        ).all()
    )
    for link in links:
        mapping = await db.scalar(
            select(QuestionAnswerMapping).where(
                QuestionAnswerMapping.id == link.mapping_id,
                QuestionAnswerMapping.tenant_id == auth.tenant_id,
            )
        )
        if mapping is None:
            continue
        if mapping.mapping_state == "CONFIRMED":
            mapping.mapping_state = "REVIEW_REQUIRED"
            mapping.confirmed_by = None
            mapping.confirmed_at = None
            await _audit(
                db,
                auth,
                mapping,
                "mapping_reopened_after_region_edit",
                {"region_id": str(region_id)},
            )


@router.post("/submissions/{submission_id}/mapping/prepare")
async def prepare_mapping(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:review")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    if item.student_match_state != "CONFIRMED":
        raise _http_error(
            409,
            "IDENTITY_NOT_CONFIRMED",
            "Identity must be confirmed before mapping review",
        )
    job = await ensure_mapping_job_and_enqueue(db, auth=auth, submission=item)
    await _audit(
        db,
        auth,
        item,
        "mapping_prepare_enqueued",
        {"job_id": str(job.id)},
    )
    await db.commit()
    task_id = await enqueue_mapping_preparation(
        tenant_id=auth.tenant_id,
        submission_id=item.id,
        job_id=job.id,
    )
    if task_id:
        job.celery_task_id = task_id
        await db.commit()
    await db.refresh(item)
    return _dump_submission(
        item,
        assessment_title=await _assessment_title(db, item.assessment_id),
        student_display_name=await _student_name(db, item.student_id),
    )


@router.get("/submissions/{submission_id}/mapping")
async def get_mapping_workspace(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:read")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    pages = list(
        (
            await db.scalars(
                select(SubmissionPage)
                .where(
                    SubmissionPage.tenant_id == auth.tenant_id,
                    SubmissionPage.submission_id == item.id,
                )
                .order_by(SubmissionPage.page_index.asc())
            )
        ).all()
    )
    page_by_id = {page.id: page for page in pages}
    regions = list(
        (
            await db.scalars(
                select(AnswerRegion)
                .where(
                    AnswerRegion.tenant_id == auth.tenant_id,
                    AnswerRegion.submission_page_id.in_([p.id for p in pages] or [uuid.uuid4()]),
                )
                .order_by(AnswerRegion.created_at.asc())
            )
        ).all()
    )
    versions = await _load_version_questions(
        db, tenant_id=auth.tenant_id, assessment_version_id=item.assessment_version_id
    )
    question_rows = list(
        (
            await db.scalars(
                select(Question).where(
                    Question.tenant_id == auth.tenant_id,
                    Question.id.in_([v.question_id for v in versions] or [uuid.uuid4()]),
                )
            )
        ).all()
    )
    questions_by_id = {q.id: q for q in question_rows}
    leaves = leaf_scorable_questions(versions)
    leaf_ids = {leaf.id for leaf in leaves}

    mappings = list(
        (
            await db.scalars(
                select(QuestionAnswerMapping).where(
                    QuestionAnswerMapping.tenant_id == auth.tenant_id,
                    QuestionAnswerMapping.submission_id == item.id,
                )
            )
        ).all()
    )
    mapping_dumps: list[dict[str, Any]] = []
    confirmed = 0
    mapped_leaf_ids: set[uuid.UUID] = set()
    for mapping in mappings:
        links = list(
            (
                await db.scalars(
                    select(QuestionAnswerMappingRegion)
                    .where(
                        QuestionAnswerMappingRegion.tenant_id == auth.tenant_id,
                        QuestionAnswerMappingRegion.mapping_id == mapping.id,
                    )
                    .order_by(
                        QuestionAnswerMappingRegion.sequence.asc(),
                        QuestionAnswerMappingRegion.created_at.asc(),
                    )
                )
            ).all()
        )
        version = next((v for v in versions if v.id == mapping.question_version_id), None)
        question = questions_by_id.get(mapping.question_id)
        code = (
            version.display_label
            if version is not None
            else (question.stable_code if question else str(mapping.question_id))
        )
        if mapping.question_version_id in leaf_ids and mapping.mapping_state == "CONFIRMED":
            confirmed += 1
            mapped_leaf_ids.add(mapping.question_version_id)
        mapping_dumps.append(
            {
                "id": str(mapping.id),
                "submission_id": str(mapping.submission_id),
                "question_id": str(mapping.question_id),
                "question_version_id": str(mapping.question_version_id),
                "question_code": code,
                "disposition": mapping.disposition,
                "mapping_state": mapping.mapping_state,
                "status": mapping.mapping_state,
                "mapped_by": mapping.mapped_by,
                "mapping_confidence": float(mapping.mapping_confidence),
                "confidence": float(mapping.mapping_confidence),
                "region_ids": [str(link.answer_region_id) for link in links],
                "confirmed_by": str(mapping.confirmed_by) if mapping.confirmed_by else None,
                "confirmed_at": (
                    mapping.confirmed_at.isoformat() if mapping.confirmed_at else None
                ),
                "created_at": mapping.created_at.isoformat(),
                "updated_at": mapping.updated_at.isoformat(),
            }
        )

    unresolved = [
        (v.display_label or questions_by_id[v.question_id].stable_code)
        for v in leaves
        if v.id not in mapped_leaf_ids
        or not any(
            m.question_version_id == v.id and m.mapping_state == "CONFIRMED" for m in mappings
        )
    ]

    region_dumps = []
    for region in regions:
        page = page_by_id.get(region.submission_page_id)
        if page is None:
            continue
        dump = _dump_region(region, page)
        for mapping_dump in mapping_dumps:
            if str(region.id) in mapping_dump["region_ids"]:
                dump["question_id"] = mapping_dump["question_version_id"]
                break
        region_dumps.append(dump)

    return {
        "submission": _dump_submission(
            item,
            assessment_title=await _assessment_title(db, item.assessment_id),
            student_display_name=await _student_name(db, item.student_id),
        ),
        "pages": [_dump_page(page) for page in pages],
        "regions": region_dumps,
        "questions": _build_question_tree(versions, questions_by_id),
        "mappings": mapping_dumps,
        "mapping": [
            {
                "question_id": m["question_version_id"],
                "question_code": m["question_code"],
                "region_ids": m["region_ids"],
                "confidence": m["confidence"],
                "status": m["status"],
            }
            for m in mapping_dumps
        ],
        "completion": {
            "leaf_total": len(leaves),
            "confirmed_count": confirmed,
            "unresolved_question_codes": unresolved,
        },
        "assessment_version_id": str(item.assessment_version_id),
        "automated_region_detection_active": False,
        "automated_mapping_active": False,
    }


@router.post("/submission-pages/{page_id}/answer-regions", status_code=201)
async def create_answer_region(
    page_id: uuid.UUID,
    payload: AnswerRegionCreateIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:review")),
) -> dict[str, Any]:
    page = await db.scalar(
        select(SubmissionPage).where(
            SubmissionPage.id == page_id,
            SubmissionPage.tenant_id == auth.tenant_id,
        )
    )
    if page is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    region = AnswerRegion(
        tenant_id=auth.tenant_id,
        submission_page_id=page.id,
        label=payload.label.strip(),
        bbox_x=_to_decimal(payload.bbox.x),
        bbox_y=_to_decimal(payload.bbox.y),
        bbox_width=_to_decimal(payload.bbox.width),
        bbox_height=_to_decimal(payload.bbox.height),
        region_type=payload.region_type,
        source_type="HUMAN",
        detection_confidence=Decimal("0.0000"),
        crossed_out=False,
        ignored=False,
        is_continuation=False,
        transcription=None,
        transcription_confidence=Decimal("0.0000"),
        created_by=auth.user_id,
    )
    db.add(region)
    await db.flush()
    await _audit(
        db,
        auth,
        region,
        "answer_region_created",
        {"page_id": str(page.id), "region_type": region.region_type},
    )
    await db.commit()
    await db.refresh(region)
    return _dump_region(region, page)


@router.patch("/answer-regions/{region_id}")
async def patch_answer_region(
    region_id: uuid.UUID,
    payload: AnswerRegionPatchIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:review")),
) -> dict[str, Any]:
    region = await db.scalar(
        select(AnswerRegion).where(
            AnswerRegion.id == region_id,
            AnswerRegion.tenant_id == auth.tenant_id,
        )
    )
    if region is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    page = await db.scalar(
        select(SubmissionPage).where(
            SubmissionPage.id == region.submission_page_id,
            SubmissionPage.tenant_id == auth.tenant_id,
        )
    )
    if page is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")

    if payload.label is not None:
        region.label = payload.label.strip()
    if payload.region_type is not None:
        region.region_type = payload.region_type
    if payload.bbox is not None:
        region.bbox_x = _to_decimal(payload.bbox.x)
        region.bbox_y = _to_decimal(payload.bbox.y)
        region.bbox_width = _to_decimal(payload.bbox.width)
        region.bbox_height = _to_decimal(payload.bbox.height)
    if payload.crossed_out is not None:
        region.crossed_out = payload.crossed_out
    if payload.ignored is not None:
        region.ignored = payload.ignored
    if payload.is_continuation is not None:
        region.is_continuation = payload.is_continuation

    region.source_type = "HUMAN"
    region.detection_confidence = Decimal("0.0000")
    await _reopen_mappings_for_region(db, auth=auth, region_id=region.id)
    await _audit(db, auth, region, "answer_region_updated", {"fields": payload.model_dump()})
    await db.commit()
    await db.refresh(region)
    return _dump_region(region, page)


@router.delete("/answer-regions/{region_id}", status_code=204)
async def delete_answer_region(
    region_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:review")),
) -> None:
    region = await db.scalar(
        select(AnswerRegion).where(
            AnswerRegion.id == region_id,
            AnswerRegion.tenant_id == auth.tenant_id,
        )
    )
    if region is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    linked = await db.scalar(
        select(QuestionAnswerMappingRegion.id).where(
            QuestionAnswerMappingRegion.tenant_id == auth.tenant_id,
            QuestionAnswerMappingRegion.answer_region_id == region.id,
        )
    )
    if linked is not None:
        raise _http_error(
            409,
            "REGION_MAPPED",
            "Unmap this region from all questions before deleting it",
        )
    await _audit(db, auth, region, "answer_region_deleted", {})
    await db.delete(region)
    await db.commit()


@router.patch("/submission-pages/{page_id}")
async def patch_submission_page(
    page_id: uuid.UUID,
    payload: PagePatchIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:review")),
) -> dict[str, Any]:
    page = await db.scalar(
        select(SubmissionPage).where(
            SubmissionPage.id == page_id,
            SubmissionPage.tenant_id == auth.tenant_id,
        )
    )
    if page is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    page.is_continuation = payload.is_continuation
    await _audit(
        db,
        auth,
        page,
        "submission_page_updated",
        {"is_continuation": payload.is_continuation},
    )
    await db.commit()
    await db.refresh(page)
    return _dump_page(page)


@router.put("/submissions/{submission_id}/question-mappings/{question_version_id}")
async def upsert_question_mapping(
    submission_id: uuid.UUID,
    question_version_id: uuid.UUID,
    payload: QuestionMappingIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:review")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    version = await db.scalar(
        select(QuestionVersion).where(
            QuestionVersion.id == question_version_id,
            QuestionVersion.tenant_id == auth.tenant_id,
            QuestionVersion.assessment_version_id == item.assessment_version_id,
        )
    )
    if version is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")

    versions = await _load_version_questions(
        db, tenant_id=auth.tenant_id, assessment_version_id=item.assessment_version_id
    )
    leaves = {leaf.id for leaf in leaf_scorable_questions(versions)}
    if version.id not in leaves:
        raise _http_error(
            409,
            "NOT_LEAF_SCORABLE",
            "Only LEAF_SCORABLE question versions can be mapped",
        )

    if payload.disposition == "BLANK" and payload.region_ids:
        raise _http_error(
            422,
            "BLANK_REQUIRES_EMPTY_REGIONS",
            "BLANK disposition must not include region_ids",
        )
    if payload.disposition == "ANSWERED" and not payload.region_ids:
        raise _http_error(
            422,
            "ANSWERED_REQUIRES_REGIONS",
            "ANSWERED disposition requires one or more region_ids",
        )

    pages = list(
        (
            await db.scalars(
                select(SubmissionPage).where(
                    SubmissionPage.tenant_id == auth.tenant_id,
                    SubmissionPage.submission_id == item.id,
                )
            )
        ).all()
    )
    page_ids = {page.id for page in pages}

    regions: list[AnswerRegion] = []
    for region_id in payload.region_ids:
        region = await db.scalar(
            select(AnswerRegion).where(
                AnswerRegion.id == region_id,
                AnswerRegion.tenant_id == auth.tenant_id,
            )
        )
        if region is None or region.submission_page_id not in page_ids:
            raise _http_error(404, "NOT_FOUND", "Resource not found")
        if region.region_type not in ASSIGNABLE_REGION_TYPES:
            raise _http_error(
                409,
                "REGION_TYPE_NOT_ASSIGNABLE",
                "Only ANSWER and DIAGRAM regions can satisfy scored mappings",
            )
        if region.ignored:
            raise _http_error(
                409,
                "REGION_IGNORED",
                "Ignored regions cannot satisfy an ANSWERED mapping",
            )
        conflict = await db.scalar(
            select(QuestionAnswerMappingRegion).where(
                QuestionAnswerMappingRegion.tenant_id == auth.tenant_id,
                QuestionAnswerMappingRegion.answer_region_id == region.id,
            )
        )
        if conflict is not None:
            existing_mapping = await db.scalar(
                select(QuestionAnswerMapping).where(
                    QuestionAnswerMapping.id == conflict.mapping_id,
                    QuestionAnswerMapping.tenant_id == auth.tenant_id,
                )
            )
            if (
                existing_mapping is not None
                and existing_mapping.question_version_id != version.id
            ):
                raise _http_error(
                    409,
                    "REGION_ALREADY_MAPPED",
                    "Region is already assigned to another question mapping",
                )
        regions.append(region)

    mapping = await db.scalar(
        select(QuestionAnswerMapping).where(
            QuestionAnswerMapping.tenant_id == auth.tenant_id,
            QuestionAnswerMapping.submission_id == item.id,
            QuestionAnswerMapping.question_version_id == version.id,
        )
    )
    if mapping is None:
        mapping = QuestionAnswerMapping(
            tenant_id=auth.tenant_id,
            submission_id=item.id,
            question_id=version.question_id,
            question_version_id=version.id,
            disposition=payload.disposition,
            mapping_state="REVIEW_REQUIRED",
            mapping_confidence=Decimal("0.0000"),
            mapped_by="HUMAN",
        )
        db.add(mapping)
        await db.flush()
    else:
        mapping.disposition = payload.disposition
        mapping.mapping_state = "REVIEW_REQUIRED"
        mapping.mapping_confidence = Decimal("0.0000")
        mapping.mapped_by = "HUMAN"
        mapping.confirmed_by = None
        mapping.confirmed_at = None
        await db.execute(
            delete(QuestionAnswerMappingRegion).where(
                QuestionAnswerMappingRegion.tenant_id == auth.tenant_id,
                QuestionAnswerMappingRegion.mapping_id == mapping.id,
            )
        )

    for index, region in enumerate(regions):
        # Clear self-link leftovers if reusing same region on same mapping
        await db.execute(
            delete(QuestionAnswerMappingRegion).where(
                QuestionAnswerMappingRegion.tenant_id == auth.tenant_id,
                QuestionAnswerMappingRegion.answer_region_id == region.id,
            )
        )
        db.add(
            QuestionAnswerMappingRegion(
                tenant_id=auth.tenant_id,
                mapping_id=mapping.id,
                answer_region_id=region.id,
                sequence=index,
            )
        )

    await _audit(
        db,
        auth,
        mapping,
        "question_mapping_upserted",
        {
            "disposition": payload.disposition,
            "region_ids": [str(r.id) for r in regions],
            "question_version_id": str(version.id),
        },
    )
    await db.commit()
    await db.refresh(mapping)
    question = await db.scalar(select(Question).where(Question.id == mapping.question_id))
    return {
        "id": str(mapping.id),
        "submission_id": str(mapping.submission_id),
        "question_id": str(mapping.question_id),
        "question_version_id": str(mapping.question_version_id),
        "question_code": version.display_label
        or (question.stable_code if question else str(mapping.question_id)),
        "disposition": mapping.disposition,
        "mapping_state": mapping.mapping_state,
        "status": mapping.mapping_state,
        "mapped_by": mapping.mapped_by,
        "mapping_confidence": float(mapping.mapping_confidence),
        "confidence": float(mapping.mapping_confidence),
        "region_ids": [str(r.id) for r in regions],
        "confirmed_by": None,
        "confirmed_at": None,
        "created_at": mapping.created_at.isoformat(),
        "updated_at": mapping.updated_at.isoformat(),
    }


@router.post(
    "/submissions/{submission_id}/question-mappings/{question_version_id}/confirm"
)
async def confirm_question_mapping(
    submission_id: uuid.UUID,
    question_version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:review")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    mapping = await db.scalar(
        select(QuestionAnswerMapping).where(
            QuestionAnswerMapping.tenant_id == auth.tenant_id,
            QuestionAnswerMapping.submission_id == item.id,
            QuestionAnswerMapping.question_version_id == question_version_id,
        )
    )
    if mapping is None:
        raise _http_error(404, "NOT_FOUND", "Resource not found")
    links = list(
        (
            await db.scalars(
                select(QuestionAnswerMappingRegion).where(
                    QuestionAnswerMappingRegion.tenant_id == auth.tenant_id,
                    QuestionAnswerMappingRegion.mapping_id == mapping.id,
                )
            )
        ).all()
    )
    if mapping.disposition == "ANSWERED" and not links:
        raise _http_error(
            409,
            "ANSWERED_REQUIRES_REGIONS",
            "Cannot confirm ANSWERED mapping without regions",
        )
    if mapping.disposition == "BLANK" and links:
        raise _http_error(
            409,
            "BLANK_REQUIRES_EMPTY_REGIONS",
            "Cannot confirm BLANK mapping while regions are attached",
        )
    mapping.mapping_state = "CONFIRMED"
    mapping.confirmed_by = auth.user_id
    mapping.confirmed_at = datetime.now(UTC)
    mapping.mapping_confidence = Decimal("0.0000")
    mapping.mapped_by = "HUMAN"
    await _audit(
        db,
        auth,
        mapping,
        "question_mapping_confirmed",
        {"question_version_id": str(question_version_id)},
    )
    await db.commit()
    await db.refresh(mapping)
    version = await db.scalar(
        select(QuestionVersion).where(QuestionVersion.id == mapping.question_version_id)
    )
    return {
        "id": str(mapping.id),
        "submission_id": str(mapping.submission_id),
        "question_id": str(mapping.question_id),
        "question_version_id": str(mapping.question_version_id),
        "question_code": version.display_label if version else str(mapping.question_id),
        "disposition": mapping.disposition,
        "mapping_state": mapping.mapping_state,
        "status": mapping.mapping_state,
        "mapped_by": mapping.mapped_by,
        "mapping_confidence": float(mapping.mapping_confidence),
        "confidence": float(mapping.mapping_confidence),
        "region_ids": [str(link.answer_region_id) for link in links],
        "confirmed_by": str(mapping.confirmed_by),
        "confirmed_at": mapping.confirmed_at.isoformat() if mapping.confirmed_at else None,
        "created_at": mapping.created_at.isoformat(),
        "updated_at": mapping.updated_at.isoformat(),
    }


@router.post("/submissions/{submission_id}/mapping/finalize")
async def finalize_mapping(
    submission_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("mapping:review")),
) -> dict[str, Any]:
    item = await _scoped_submission(db, submission_id, auth.tenant_id)
    if item.workflow_state not in {"MAPPING_REVIEW", "READY_FOR_EVALUATION"}:
        raise _http_error(
            409,
            "INVALID_WORKFLOW_STATE",
            "Submission must be in MAPPING_REVIEW before finalization",
        )
    versions = await _load_version_questions(
        db, tenant_id=auth.tenant_id, assessment_version_id=item.assessment_version_id
    )
    leaves = leaf_scorable_questions(versions)
    questions_by_id = {
        q.id: q
        for q in (
            await db.scalars(
                select(Question).where(
                    Question.tenant_id == auth.tenant_id,
                    Question.id.in_([v.question_id for v in leaves] or [uuid.uuid4()]),
                )
            )
        ).all()
    }
    mappings = {
        m.question_version_id: m
        for m in (
            await db.scalars(
                select(QuestionAnswerMapping).where(
                    QuestionAnswerMapping.tenant_id == auth.tenant_id,
                    QuestionAnswerMapping.submission_id == item.id,
                )
            )
        ).all()
    }
    unresolved: list[str] = []
    for leaf in leaves:
        code = leaf.display_label or questions_by_id[leaf.question_id].stable_code
        mapping = mappings.get(leaf.id)
        if mapping is None or mapping.mapping_state != "CONFIRMED":
            unresolved.append(code)
            continue
        links = list(
            (
                await db.scalars(
                    select(QuestionAnswerMappingRegion).where(
                        QuestionAnswerMappingRegion.tenant_id == auth.tenant_id,
                        QuestionAnswerMappingRegion.mapping_id == mapping.id,
                    )
                )
            ).all()
        )
        if mapping.disposition == "ANSWERED" and not links:
            unresolved.append(code)
        elif mapping.disposition == "BLANK" and links:
            unresolved.append(code)

    if unresolved:
        raise _http_error(
            409,
            "MAPPING_INCOMPLETE",
            "Every LEAF_SCORABLE question must have a confirmed disposition",
            unresolved_question_codes=unresolved,
        )

    item.workflow_state = "READY_FOR_EVALUATION"
    item.mapping_confidence = Decimal("0.0000")
    await _audit(
        db,
        auth,
        item,
        "mapping_finalized",
        {
            "leaf_total": len(leaves),
            "workflow_state": "READY_FOR_EVALUATION",
            "evaluation_enqueued": False,
        },
    )
    await db.commit()
    await db.refresh(item)
    return _dump_submission(
        item,
        assessment_title=await _assessment_title(db, item.assessment_id),
        student_display_name=await _student_name(db, item.student_id),
    )
