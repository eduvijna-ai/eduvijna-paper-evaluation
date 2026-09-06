# ruff: noqa: B008
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.models import Rubric, RubricVersion
from app.db.session import get_db_session

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db_session)]


def _dump_version(item: RubricVersion) -> dict[str, Any]:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "rubric_id": item.rubric_id,
        "question_version_id": item.question_version_id,
        "version_number": item.version_number,
        "status": item.status,
        "source_type": item.source_type,
        "created_by": item.created_by,
        "approved_by": item.approved_by,
        "approved_at": item.approved_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/rubrics/{rubric_id}/versions")
async def list_rubric_versions(
    rubric_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:read")),
) -> list[dict[str, Any]]:
    rubric = await db.scalar(
        select(Rubric).where(
            Rubric.id == rubric_id,
            Rubric.tenant_id == auth.tenant_id,
        )
    )
    if rubric is None:
        raise HTTPException(404, "Resource not found")

    rows = await db.scalars(
        select(RubricVersion)
        .where(
            RubricVersion.rubric_id == rubric.id,
            RubricVersion.tenant_id == auth.tenant_id,
        )
        .order_by(RubricVersion.version_number)
    )
    return [_dump_version(item) for item in rows]
