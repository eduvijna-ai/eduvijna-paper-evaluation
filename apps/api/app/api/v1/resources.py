# ruff: noqa: B008
"""B13 curriculum resource catalog and student assignment API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.session import get_db_session
from app.services.resources import (
    ResourceError,
    activate_resource,
    approve_resource,
    cancel_assignment,
    create_assignment,
    create_resource,
    deactivate_resource,
    get_resource,
    list_resources,
    list_student_assignments,
    replace_resource_nodes,
    update_resource,
)

router = APIRouter(tags=["learning-resources"])
Db = Annotated[AsyncSession, Depends(get_db_session)]

RESOURCE_KINDS = (
    "PRACTICE_SET",
    "WORKED_EXAMPLE",
    "CONCEPT_NOTE",
    "INTERNAL_PACKET",
)
RESOURCE_STATUSES = ("DRAFT", "APPROVED", "ACTIVE", "DEACTIVATED")
ASSIGNMENT_STATUSES = ("ASSIGNED", "CANCELLED")


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )


def _map_resource_error(exc: ResourceError) -> HTTPException:
    if exc.code == "NOT_FOUND":
        return _http_error(404, exc.code, exc.message)
    if exc.code in {
        "RESOURCE_OPEN_WEB_REJECTED",
        "RESOURCE_DUPLICATE_CODE",
        "RESOURCE_NOT_ASSIGNABLE",
        "RESOURCE_RECOMMENDATION_INCOMPATIBLE",
        "RESOURCE_INVALID_STATUS",
        "RESOURCE_IMMUTABLE_FIELDS",
        "RESOURCE_NODES_REQUIRED",
        "RESOURCE_NODE_INVALID",
        "RESOURCE_NODES_LOCKED",
        "RESOURCE_ASSIGNMENT_ALREADY_CANCELLED",
        "RESOURCE_ASSIGNMENT_CONFLICT",
    }:
        return _http_error(409, exc.code, exc.message)
    return _http_error(400, exc.code, exc.message)


class CurriculumResourceCreateInput(BaseModel):
    curriculum_id: uuid.UUID
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    resource_kind: str
    content_ref: str = Field(min_length=1, max_length=512)
    curriculum_node_ids: list[uuid.UUID] = Field(min_length=1)


class CurriculumResourceUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    resource_kind: str | None = None
    content_ref: str | None = Field(default=None, min_length=1, max_length=512)


class CurriculumResourceNodesReplaceInput(BaseModel):
    curriculum_node_ids: list[uuid.UUID] = Field(min_length=1)


class StudentResourceAssignmentCreateInput(BaseModel):
    resource_id: uuid.UUID
    learning_recommendation_id: uuid.UUID | None = None


@router.get("/learning/resources")
async def list_curriculum_resources(
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:read")),
    curriculum_id: uuid.UUID | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    if status is not None and status not in RESOURCE_STATUSES:
        raise _http_error(422, "INVALID_STATUS", "Invalid resource status filter")
    try:
        return await list_resources(
            db,
            tenant_id=auth.tenant_id,
            curriculum_id=curriculum_id,
            status=status,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc


@router.post("/learning/resources", status_code=201)
async def create_curriculum_resource(
    body: CurriculumResourceCreateInput,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    if body.resource_kind not in RESOURCE_KINDS:
        raise _http_error(422, "INVALID_RESOURCE_KIND", "Invalid resource_kind")
    try:
        result = await create_resource(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            curriculum_id=body.curriculum_id,
            code=body.code,
            title=body.title,
            description=body.description,
            resource_kind=body.resource_kind,
            content_ref=body.content_ref,
            curriculum_node_ids=body.curriculum_node_ids,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc
    await db.commit()
    return result


@router.get("/learning/resources/{resource_id}")
async def get_curriculum_resource(
    resource_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:read")),
) -> dict[str, Any]:
    try:
        return await get_resource(
            db, tenant_id=auth.tenant_id, resource_id=resource_id
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc


@router.patch("/learning/resources/{resource_id}")
async def patch_curriculum_resource(
    resource_id: uuid.UUID,
    body: CurriculumResourceUpdateInput,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    if "resource_kind" in payload and payload["resource_kind"] not in RESOURCE_KINDS:
        raise _http_error(422, "INVALID_RESOURCE_KIND", "Invalid resource_kind")
    try:
        result = await update_resource(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            resource_id=resource_id,
            payload=payload,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc
    await db.commit()
    return result


@router.post("/learning/resources/{resource_id}/approve")
async def approve_curriculum_resource(
    resource_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:approve")),
) -> dict[str, Any]:
    try:
        result = await approve_resource(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            resource_id=resource_id,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc
    await db.commit()
    return result


@router.post("/learning/resources/{resource_id}/activate")
async def activate_curriculum_resource(
    resource_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:approve")),
) -> dict[str, Any]:
    try:
        result = await activate_resource(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            resource_id=resource_id,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc
    await db.commit()
    return result


@router.post("/learning/resources/{resource_id}/deactivate")
async def deactivate_curriculum_resource(
    resource_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:approve")),
) -> dict[str, Any]:
    try:
        result = await deactivate_resource(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            resource_id=resource_id,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc
    await db.commit()
    return result


@router.put("/learning/resources/{resource_id}/nodes")
async def put_curriculum_resource_nodes(
    resource_id: uuid.UUID,
    body: CurriculumResourceNodesReplaceInput,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    try:
        result = await replace_resource_nodes(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            resource_id=resource_id,
            curriculum_node_ids=body.curriculum_node_ids,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc
    await db.commit()
    return result


@router.get("/learning/students/{student_id}/resource-assignments")
async def list_student_resource_assignments(
    student_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:read")),
    curriculum_id: uuid.UUID | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    if status is not None and status not in ASSIGNMENT_STATUSES:
        raise _http_error(422, "INVALID_STATUS", "Invalid assignment status filter")
    try:
        return await list_student_assignments(
            db,
            tenant_id=auth.tenant_id,
            student_id=student_id,
            curriculum_id=curriculum_id,
            status=status,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc


@router.post("/learning/students/{student_id}/resource-assignments")
async def create_student_resource_assignment(
    student_id: uuid.UUID,
    body: StudentResourceAssignmentCreateInput,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:assign")),
) -> dict[str, Any]:
    try:
        result = await create_assignment(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            student_id=student_id,
            resource_id=body.resource_id,
            learning_recommendation_id=body.learning_recommendation_id,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc
    await db.commit()
    return result


@router.post("/learning/resource-assignments/{assignment_id}/cancel")
async def cancel_student_resource_assignment(
    assignment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("learning:assign")),
) -> dict[str, Any]:
    try:
        result = await cancel_assignment(
            db,
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            assignment_id=assignment_id,
        )
    except ResourceError as exc:
        raise _map_resource_error(exc) from exc
    await db.commit()
    return result
