import uuid
from typing import Any, Protocol

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AiExecutionRecord
from app.services.academic_freeze import SERVER_AI_PROPOSED_SOURCE


class AnswerKeyProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version_id: uuid.UUID
    assessment_version_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=500)
    context: dict[str, str] = Field(default_factory=dict, max_length=20)


class RubricProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version_id: uuid.UUID
    assessment_version_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=500)
    context: dict[str, str] = Field(default_factory=dict, max_length=20)


class CurriculumMappingProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version_id: uuid.UUID
    curriculum_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=500)
    context: dict[str, str] = Field(default_factory=dict, max_length=20)


class AiProposalProvider(Protocol):
    async def propose_answer_key(self, request: AnswerKeyProposalRequest) -> dict[str, Any]: ...
    async def propose_rubric(self, request: RubricProposalRequest) -> dict[str, Any]: ...
    async def suggest_curriculum_mapping(
        self, request: CurriculumMappingProposalRequest
    ) -> dict[str, Any]: ...


def build_ai_request_summary(
    *,
    operation: str,
    request: BaseModel,
    requested_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Whitelist-only execution summary — never full academic content."""
    data = request.model_dump(mode="json")
    context = data.get("context") or {}
    instructions = data.get("instructions") or ""
    return {
        "operation": operation,
        "requested_by": str(requested_by) if requested_by else None,
        "assessment_version_id": data.get("assessment_version_id"),
        "question_version_id": data.get("question_version_id"),
        "curriculum_id": data.get("curriculum_id"),
        "instruction_length": len(instructions),
        "context_key_count": len(context),
        "context_keys": sorted(context.keys())[:20],
    }


def server_ai_proposed_source_type() -> str:
    """Provenance assigned only by the AI proposal service path."""
    return SERVER_AI_PROPOSED_SOURCE


async def unavailable(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    operation: str,
    request: BaseModel,
    requested_by: uuid.UUID | None = None,
) -> None:
    db.add(
        AiExecutionRecord(
            tenant_id=tenant_id,
            operation=operation,
            provider="none",
            status="UNAVAILABLE",
            request_summary=build_ai_request_summary(
                operation=operation, request=request, requested_by=requested_by
            ),
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
