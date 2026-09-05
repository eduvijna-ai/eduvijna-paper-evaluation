import uuid
from typing import Any, Protocol

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AiExecutionRecord


class AiProposalProvider(Protocol):
    async def propose_answer_key(self, request: dict[str, Any]) -> dict[str, Any]: ...
    async def propose_rubric(self, request: dict[str, Any]) -> dict[str, Any]: ...
    async def suggest_curriculum_mapping(self, request: dict[str, Any]) -> dict[str, Any]: ...


async def unavailable(
    db: AsyncSession, *, tenant_id: uuid.UUID, operation: str, request: dict[str, Any]
) -> None:
    db.add(
        AiExecutionRecord(
            tenant_id=tenant_id,
            operation=operation,
            provider="none",
            status="UNAVAILABLE",
            request_summary=request,
            response_summary={"error_code": "AI_PROVIDER_UNAVAILABLE"},
        )
    )
    await db.commit()
    raise HTTPException(
        503,
        {
            "code": "AI_PROVIDER_UNAVAILABLE",
            "message": "No AI proposal provider is configured",
        },
    )
