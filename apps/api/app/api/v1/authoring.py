# ruff: noqa: B008
"""B10 assessment authoring upload APIs (question paper)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.session import get_db_session
from app.services.assessment_artifacts import dump_assessment_artifact, upload_question_paper

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/assessment-versions/{version_id}/question-paper", status_code=201)
async def upload_assessment_question_paper(
    version_id: uuid.UUID,
    db: Db,
    file: Annotated[UploadFile, File()],
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    artifact = await upload_question_paper(
        db, auth=auth, version_id=version_id, file=file
    )
    return dump_assessment_artifact(artifact)
