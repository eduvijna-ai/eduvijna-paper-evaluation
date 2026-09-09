"""B13 curriculum resource catalog and student assignment service (PEV-041)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Curriculum,
    CurriculumNode,
    CurriculumResource,
    CurriculumResourceNode,
    LearningRecommendation,
    Student,
    StudentResourceAssignment,
)
from app.services.audit import add_audit_event

__all__ = [
    "ResourceError",
    "reject_open_web_content_ref",
    "list_resources",
    "get_resource",
    "create_resource",
    "update_resource",
    "replace_resource_nodes",
    "approve_resource",
    "activate_resource",
    "deactivate_resource",
    "list_student_assignments",
    "create_assignment",
    "cancel_assignment",
    "serialize_resource",
    "serialize_assignment",
    "list_assigned_for_workspace",
]


class ResourceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _utcnow() -> datetime:
    return datetime.now(UTC)


def reject_open_web_content_ref(content_ref: str) -> None:
    """Reject open-web discovery refs; content_ref must be an opaque internal key."""
    lowered = content_ref.lower()
    if lowered.startswith(("http://", "https://", "//")):
        raise ResourceError(
            "RESOURCE_OPEN_WEB_REJECTED",
            "content_ref must not be an open-web URL",
        )


async def _get_curriculum(
    db: AsyncSession, *, tenant_id: uuid.UUID, curriculum_id: uuid.UUID
) -> Curriculum:
    curriculum = await db.scalar(
        select(Curriculum).where(
            Curriculum.id == curriculum_id, Curriculum.tenant_id == tenant_id
        )
    )
    if curriculum is None:
        raise ResourceError("NOT_FOUND", "Curriculum not found")
    return curriculum


async def _get_student(
    db: AsyncSession, *, tenant_id: uuid.UUID, student_id: uuid.UUID
) -> Student:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise ResourceError("NOT_FOUND", "Student not found")
    return student


async def _load_resource(
    db: AsyncSession, *, tenant_id: uuid.UUID, resource_id: uuid.UUID
) -> CurriculumResource:
    resource = await db.scalar(
        select(CurriculumResource).where(
            CurriculumResource.id == resource_id,
            CurriculumResource.tenant_id == tenant_id,
        )
    )
    if resource is None:
        raise ResourceError("NOT_FOUND", "Curriculum resource not found")
    return resource


async def _node_ids_for_resource(
    db: AsyncSession, *, tenant_id: uuid.UUID, resource_id: uuid.UUID
) -> list[uuid.UUID]:
    rows = list(
        (
            await db.scalars(
                select(CurriculumResourceNode.curriculum_node_id)
                .where(
                    CurriculumResourceNode.tenant_id == tenant_id,
                    CurriculumResourceNode.resource_id == resource_id,
                )
                .order_by(CurriculumResourceNode.curriculum_node_id)
            )
        ).all()
    )
    return list(rows)


async def _validate_nodes(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    curriculum_id: uuid.UUID,
    node_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    if not node_ids:
        raise ResourceError(
            "RESOURCE_NODES_REQUIRED",
            "At least one curriculum node mapping is required",
        )
    unique_ids = list(dict.fromkeys(node_ids))
    rows = list(
        (
            await db.scalars(
                select(CurriculumNode).where(
                    CurriculumNode.tenant_id == tenant_id,
                    CurriculumNode.curriculum_id == curriculum_id,
                    CurriculumNode.id.in_(unique_ids),
                )
            )
        ).all()
    )
    found = {row.id for row in rows}
    missing = [str(nid) for nid in unique_ids if nid not in found]
    if missing:
        raise ResourceError(
            "RESOURCE_NODE_INVALID",
            "Curriculum nodes must belong to the resource curriculum and tenant",
        )
    return unique_ids


async def _replace_nodes(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    resource_id: uuid.UUID,
    node_ids: list[uuid.UUID],
) -> None:
    await db.execute(
        delete(CurriculumResourceNode).where(
            CurriculumResourceNode.tenant_id == tenant_id,
            CurriculumResourceNode.resource_id == resource_id,
        )
    )
    for node_id in node_ids:
        db.add(
            CurriculumResourceNode(
                tenant_id=tenant_id,
                resource_id=resource_id,
                curriculum_node_id=node_id,
            )
        )


def serialize_resource(
    resource: CurriculumResource, node_ids: list[uuid.UUID]
) -> dict[str, Any]:
    return {
        "id": str(resource.id),
        "curriculum_id": str(resource.curriculum_id),
        "code": resource.code,
        "title": resource.title,
        "description": resource.description,
        "resource_kind": resource.resource_kind,
        "status": resource.status,
        "content_ref": resource.content_ref,
        "curriculum_node_ids": [str(nid) for nid in node_ids],
        "created_by": str(resource.created_by) if resource.created_by else None,
        "approved_by": str(resource.approved_by) if resource.approved_by else None,
        "approved_at": resource.approved_at.isoformat() if resource.approved_at else None,
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }


async def serialize_resource_async(
    db: AsyncSession, *, tenant_id: uuid.UUID, resource: CurriculumResource
) -> dict[str, Any]:
    await db.refresh(resource)
    node_ids = await _node_ids_for_resource(
        db, tenant_id=tenant_id, resource_id=resource.id
    )
    return serialize_resource(resource, node_ids)


def serialize_assignment(
    assignment: StudentResourceAssignment, resource_payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": str(assignment.id),
        "student_id": str(assignment.student_id),
        "resource_id": str(assignment.resource_id),
        "resource": resource_payload,
        "learning_recommendation_id": (
            str(assignment.learning_recommendation_id)
            if assignment.learning_recommendation_id
            else None
        ),
        "status": assignment.status,
        "assigned_by": str(assignment.assigned_by) if assignment.assigned_by else None,
        "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
        "cancelled_at": (
            assignment.cancelled_at.isoformat() if assignment.cancelled_at else None
        ),
        "cancelled_by": (
            str(assignment.cancelled_by) if assignment.cancelled_by else None
        ),
    }


async def serialize_assignment_async(
    db: AsyncSession, *, tenant_id: uuid.UUID, assignment: StudentResourceAssignment
) -> dict[str, Any]:
    await db.refresh(assignment)
    resource = await _load_resource(
        db, tenant_id=tenant_id, resource_id=assignment.resource_id
    )
    resource_payload = await serialize_resource_async(
        db, tenant_id=tenant_id, resource=resource
    )
    return serialize_assignment(assignment, resource_payload)


async def list_resources(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    curriculum_id: uuid.UUID | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    q = select(CurriculumResource).where(CurriculumResource.tenant_id == tenant_id)
    if curriculum_id is not None:
        q = q.where(CurriculumResource.curriculum_id == curriculum_id)
    if status is not None:
        q = q.where(CurriculumResource.status == status)
    q = q.order_by(CurriculumResource.created_at.desc(), CurriculumResource.code)
    rows = list((await db.scalars(q)).all())
    items = [
        await serialize_resource_async(db, tenant_id=tenant_id, resource=row)
        for row in rows
    ]
    return {
        "curriculum_id": str(curriculum_id) if curriculum_id else None,
        "status_filter": status,
        "items": items,
    }


async def get_resource(
    db: AsyncSession, *, tenant_id: uuid.UUID, resource_id: uuid.UUID
) -> dict[str, Any]:
    resource = await _load_resource(db, tenant_id=tenant_id, resource_id=resource_id)
    return await serialize_resource_async(db, tenant_id=tenant_id, resource=resource)


async def create_resource(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    curriculum_id: uuid.UUID,
    code: str,
    title: str,
    resource_kind: str,
    content_ref: str,
    curriculum_node_ids: list[uuid.UUID],
    description: str | None = None,
) -> dict[str, Any]:
    await _get_curriculum(db, tenant_id=tenant_id, curriculum_id=curriculum_id)
    reject_open_web_content_ref(content_ref)
    node_ids = await _validate_nodes(
        db,
        tenant_id=tenant_id,
        curriculum_id=curriculum_id,
        node_ids=curriculum_node_ids,
    )

    resource = CurriculumResource(
        tenant_id=tenant_id,
        curriculum_id=curriculum_id,
        code=code.strip(),
        title=title.strip(),
        description=description,
        resource_kind=resource_kind,
        status="DRAFT",
        content_ref=content_ref.strip(),
        created_by=actor_user_id,
    )
    try:
        async with db.begin_nested():
            db.add(resource)
            await db.flush()
    except IntegrityError as exc:
        raise ResourceError(
            "RESOURCE_DUPLICATE_CODE",
            "A resource with this code already exists for the curriculum",
        ) from exc

    await _replace_nodes(
        db, tenant_id=tenant_id, resource_id=resource.id, node_ids=node_ids
    )
    await db.flush()

    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="CurriculumResource",
        entity_id=resource.id,
        action="resource_created",
        after={
            "code": resource.code,
            "status": resource.status,
            "curriculum_id": str(curriculum_id),
        },
    )
    return await serialize_resource_async(db, tenant_id=tenant_id, resource=resource)


async def update_resource(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    resource_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    resource = await _load_resource(db, tenant_id=tenant_id, resource_id=resource_id)
    before = {
        "title": resource.title,
        "description": resource.description,
        "resource_kind": resource.resource_kind,
        "content_ref": resource.content_ref,
        "status": resource.status,
    }

    title = payload.get("title")
    resource_kind = payload.get("resource_kind")
    content_ref = payload.get("content_ref")
    has_description = "description" in payload
    description = payload.get("description") if has_description else None

    if resource.status == "DRAFT":
        if title is not None:
            resource.title = str(title).strip()
        if has_description:
            resource.description = description
        if resource_kind is not None:
            resource.resource_kind = str(resource_kind)
        if content_ref is not None:
            reject_open_web_content_ref(str(content_ref))
            resource.content_ref = str(content_ref).strip()
    elif resource.status in {"APPROVED", "ACTIVE", "DEACTIVATED"}:
        if resource_kind is not None or content_ref is not None:
            raise ResourceError(
                "RESOURCE_IMMUTABLE_FIELDS",
                "resource_kind and content_ref may only change while DRAFT",
            )
        if title is not None:
            resource.title = str(title).strip()
        if has_description:
            resource.description = description
    else:
        raise ResourceError("RESOURCE_INVALID_STATUS", "Unknown resource status")

    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="CurriculumResource",
        entity_id=resource.id,
        action="resource_updated",
        before=before,
        after={
            "title": resource.title,
            "description": resource.description,
            "resource_kind": resource.resource_kind,
            "content_ref": resource.content_ref,
            "status": resource.status,
        },
    )
    return await serialize_resource_async(db, tenant_id=tenant_id, resource=resource)


async def replace_resource_nodes(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    resource_id: uuid.UUID,
    curriculum_node_ids: list[uuid.UUID],
) -> dict[str, Any]:
    resource = await _load_resource(db, tenant_id=tenant_id, resource_id=resource_id)
    if resource.status == "DEACTIVATED":
        raise ResourceError(
            "RESOURCE_NODES_LOCKED",
            "Node mappings cannot be replaced when resource is DEACTIVATED",
        )
    node_ids = await _validate_nodes(
        db,
        tenant_id=tenant_id,
        curriculum_id=resource.curriculum_id,
        node_ids=curriculum_node_ids,
    )
    before = [
        str(nid)
        for nid in await _node_ids_for_resource(
            db, tenant_id=tenant_id, resource_id=resource.id
        )
    ]
    await _replace_nodes(
        db, tenant_id=tenant_id, resource_id=resource.id, node_ids=node_ids
    )
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="CurriculumResource",
        entity_id=resource.id,
        action="resource_nodes_replaced",
        before={"curriculum_node_ids": before},
        after={"curriculum_node_ids": [str(nid) for nid in node_ids]},
    )
    return await serialize_resource_async(db, tenant_id=tenant_id, resource=resource)


async def approve_resource(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    resource_id: uuid.UUID,
) -> dict[str, Any]:
    resource = await _load_resource(db, tenant_id=tenant_id, resource_id=resource_id)
    if resource.status != "DRAFT":
        raise ResourceError(
            "RESOURCE_INVALID_STATUS",
            "Only DRAFT resources can be approved",
        )
    node_ids = await _node_ids_for_resource(
        db, tenant_id=tenant_id, resource_id=resource.id
    )
    if not node_ids:
        raise ResourceError(
            "RESOURCE_NODES_REQUIRED",
            "At least one curriculum node mapping is required to approve",
        )
    resource.status = "APPROVED"
    resource.approved_by = actor_user_id
    resource.approved_at = _utcnow()
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="CurriculumResource",
        entity_id=resource.id,
        action="resource_approved",
        after={"status": "APPROVED"},
    )
    return await serialize_resource_async(db, tenant_id=tenant_id, resource=resource)


async def activate_resource(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    resource_id: uuid.UUID,
) -> dict[str, Any]:
    resource = await _load_resource(db, tenant_id=tenant_id, resource_id=resource_id)
    if resource.status != "APPROVED":
        raise ResourceError(
            "RESOURCE_INVALID_STATUS",
            "Only APPROVED resources can be activated",
        )
    resource.status = "ACTIVE"
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="CurriculumResource",
        entity_id=resource.id,
        action="resource_activated",
        after={"status": "ACTIVE"},
    )
    return await serialize_resource_async(db, tenant_id=tenant_id, resource=resource)


async def deactivate_resource(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    resource_id: uuid.UUID,
) -> dict[str, Any]:
    resource = await _load_resource(db, tenant_id=tenant_id, resource_id=resource_id)
    if resource.status not in {"ACTIVE", "APPROVED"}:
        raise ResourceError(
            "RESOURCE_INVALID_STATUS",
            "Only ACTIVE or APPROVED resources can be deactivated",
        )
    resource.status = "DEACTIVATED"
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="CurriculumResource",
        entity_id=resource.id,
        action="resource_deactivated",
        after={"status": "DEACTIVATED"},
    )
    return await serialize_resource_async(db, tenant_id=tenant_id, resource=resource)


async def list_student_assignments(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_id: uuid.UUID | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    await _get_student(db, tenant_id=tenant_id, student_id=student_id)
    q = (
        select(StudentResourceAssignment)
        .join(
            CurriculumResource,
            CurriculumResource.id == StudentResourceAssignment.resource_id,
        )
        .where(
            StudentResourceAssignment.tenant_id == tenant_id,
            StudentResourceAssignment.student_id == student_id,
        )
    )
    if curriculum_id is not None:
        q = q.where(CurriculumResource.curriculum_id == curriculum_id)
    if status is not None:
        q = q.where(StudentResourceAssignment.status == status)
    q = q.order_by(StudentResourceAssignment.assigned_at.desc())
    rows = list((await db.scalars(q)).all())
    items = [
        await serialize_assignment_async(db, tenant_id=tenant_id, assignment=row)
        for row in rows
    ]
    return {
        "student_id": str(student_id),
        "curriculum_id": str(curriculum_id) if curriculum_id else None,
        "items": items,
    }


async def _find_assigned_grain(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    resource_id: uuid.UUID,
    learning_recommendation_id: uuid.UUID | None,
) -> StudentResourceAssignment | None:
    # NULLS NOT DISTINCT semantics mirrored in application lookup.
    stmt = select(StudentResourceAssignment).where(
        StudentResourceAssignment.tenant_id == tenant_id,
        StudentResourceAssignment.student_id == student_id,
        StudentResourceAssignment.resource_id == resource_id,
        StudentResourceAssignment.status == "ASSIGNED",
    )
    if learning_recommendation_id is None:
        stmt = stmt.where(
            StudentResourceAssignment.learning_recommendation_id.is_(None)
        )
    else:
        stmt = stmt.where(
            StudentResourceAssignment.learning_recommendation_id
            == learning_recommendation_id
        )
    result = await db.scalar(stmt)
    return result if isinstance(result, StudentResourceAssignment) else None


async def create_assignment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    student_id: uuid.UUID,
    resource_id: uuid.UUID,
    learning_recommendation_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    await _get_student(db, tenant_id=tenant_id, student_id=student_id)
    resource = await _load_resource(db, tenant_id=tenant_id, resource_id=resource_id)

    existing = await _find_assigned_grain(
        db,
        tenant_id=tenant_id,
        student_id=student_id,
        resource_id=resource_id,
        learning_recommendation_id=learning_recommendation_id,
    )
    if existing is not None:
        return await serialize_assignment_async(
            db, tenant_id=tenant_id, assignment=existing
        )

    if resource.status != "ACTIVE":
        raise ResourceError(
            "RESOURCE_NOT_ASSIGNABLE",
            "Only ACTIVE curriculum resources can be assigned",
        )

    if learning_recommendation_id is not None:
        recommendation = await db.scalar(
            select(LearningRecommendation).where(
                LearningRecommendation.id == learning_recommendation_id,
                LearningRecommendation.tenant_id == tenant_id,
            )
        )
        if recommendation is None:
            raise ResourceError("NOT_FOUND", "Learning recommendation not found")
        if recommendation.student_id != student_id:
            raise ResourceError(
                "RESOURCE_RECOMMENDATION_INCOMPATIBLE",
                "Recommendation belongs to a different student",
            )
        if recommendation.status != "ACTIVE":
            raise ResourceError(
                "RESOURCE_RECOMMENDATION_INCOMPATIBLE",
                "Recommendation must be ACTIVE",
            )
        node_ids = await _node_ids_for_resource(
            db, tenant_id=tenant_id, resource_id=resource.id
        )
        if recommendation.target_node_id not in set(node_ids):
            raise ResourceError(
                "RESOURCE_RECOMMENDATION_INCOMPATIBLE",
                "Recommendation target node is not mapped on the resource",
            )

    assignment = StudentResourceAssignment(
        tenant_id=tenant_id,
        student_id=student_id,
        resource_id=resource_id,
        learning_recommendation_id=learning_recommendation_id,
        status="ASSIGNED",
        assigned_by=actor_user_id,
        assigned_at=_utcnow(),
    )
    try:
        async with db.begin_nested():
            db.add(assignment)
            await db.flush()
    except IntegrityError:
        # Race on the ASSIGNED grain unique index — return the winner.
        existing = await _find_assigned_grain(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            resource_id=resource_id,
            learning_recommendation_id=learning_recommendation_id,
        )
        if existing is not None:
            return await serialize_assignment_async(
                db, tenant_id=tenant_id, assignment=existing
            )
        raise ResourceError(
            "RESOURCE_ASSIGNMENT_CONFLICT",
            "Assignment conflicts with an existing record",
        ) from None

    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="StudentResourceAssignment",
        entity_id=assignment.id,
        action="ASSIGN_RESOURCE",
        after={
            "student_id": str(student_id),
            "resource_id": str(resource_id),
            "learning_recommendation_id": (
                str(learning_recommendation_id) if learning_recommendation_id else None
            ),
            "status": "ASSIGNED",
        },
    )
    return await serialize_assignment_async(
        db, tenant_id=tenant_id, assignment=assignment
    )


async def cancel_assignment(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    assignment_id: uuid.UUID,
) -> dict[str, Any]:
    assignment = await db.scalar(
        select(StudentResourceAssignment).where(
            StudentResourceAssignment.id == assignment_id,
            StudentResourceAssignment.tenant_id == tenant_id,
        )
    )
    if assignment is None:
        raise ResourceError("NOT_FOUND", "Resource assignment not found")
    if assignment.status != "ASSIGNED":
        raise ResourceError(
            "RESOURCE_ASSIGNMENT_ALREADY_CANCELLED",
            "Assignment is already cancelled",
        )
    assignment.status = "CANCELLED"
    assignment.cancelled_by = actor_user_id
    assignment.cancelled_at = _utcnow()
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="StudentResourceAssignment",
        entity_id=assignment.id,
        action="CANCEL_RESOURCE_ASSIGNMENT",
        after={"status": "CANCELLED"},
    )
    return await serialize_assignment_async(
        db, tenant_id=tenant_id, assignment=assignment
    )


async def list_assigned_for_workspace(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    curriculum_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """ASSIGNED assignments for student+curriculum, stable order by assigned_at desc."""
    rows = list(
        (
            await db.scalars(
                select(StudentResourceAssignment)
                .join(
                    CurriculumResource,
                    and_(
                        CurriculumResource.id == StudentResourceAssignment.resource_id,
                        CurriculumResource.tenant_id == tenant_id,
                    ),
                )
                .where(
                    StudentResourceAssignment.tenant_id == tenant_id,
                    StudentResourceAssignment.student_id == student_id,
                    StudentResourceAssignment.status == "ASSIGNED",
                    CurriculumResource.curriculum_id == curriculum_id,
                )
                .order_by(StudentResourceAssignment.assigned_at.desc())
            )
        ).all()
    )
    return [
        await serialize_assignment_async(db, tenant_id=tenant_id, assignment=row)
        for row in rows
    ]
