from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

router = APIRouter(tags=["system"])


class StatusResponse(BaseModel):
    status: str


@router.get("/health", response_model=StatusResponse)
async def health() -> StatusResponse:
    return StatusResponse(status="ok")


@router.get("/ready", response_model=StatusResponse)
async def ready(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatusResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    return StatusResponse(status="ready")
