# ruff: noqa: B008
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from fastapi import Depends, HTTPException

ROLE_CODES: Final = (
    "PLATFORM_ADMIN",
    "INSTITUTION_ADMIN",
    "TEACHER",
    "EVALUATOR",
    "STUDENT",
    "PARENT",
    "EXAM_CONTROLLER",
    "ACADEMIC_COORDINATOR",
    "HOD",
    "MODERATOR",
    "AUDITOR",
)

PERMISSION_CODES: Final = (
    "institution:read",
    "academic_year:read",
    "academic_year:write",
    "class_section:read",
    "class_section:write",
    "student:read",
    "student:write",
    "student:import",
    "guardian:read",
    "guardian:write",
    "curriculum:read",
    "curriculum:manage",
    "assessment:read",
    "assessment:manage",
    "assessment:approve",
    "rubric:read",
    "rubric:manage",
    "rubric:approve",
    "submission:read",
    "submission:upload",
    "submission:review",
    "mapping:read",
    "mapping:review",
    "transcription:read",
    "transcription:review",
    "evaluation:read",
    "evaluation:run",
    "evaluation:review",
    "evaluation:approve",
    "publication:read",
    "publication:generate",
    "publication:publish",
    "analytics:read",
    "analytics:materialize",
    "learning:read",
    "learning:generate",
    "learning:review",
    "learning:approve",
    "learning:assign",
    "quality:read",
    "quality:manage",
    "grading:read",
    "grading:manage",
    "grading:work",
    "moderation:read",
    "moderation:manage",
    "moderation:review",
    "grievance:read",
    "grievance:create",
    "grievance:manage",
)

ROLE_PERMISSION_MAP: Final = {
    "INSTITUTION_ADMIN": frozenset(PERMISSION_CODES),
    "TEACHER": frozenset(
        {
            "institution:read",
            "academic_year:read",
            "class_section:read",
            "student:read",
            "student:write",
            "guardian:read",
            "curriculum:read",
            "curriculum:manage",
            "assessment:read",
            "assessment:manage",
            "assessment:approve",
            "rubric:read",
            "rubric:manage",
            "rubric:approve",
            "submission:read",
            "submission:upload",
            "submission:review",
            "mapping:read",
            "mapping:review",
            "transcription:read",
            "transcription:review",
            "evaluation:read",
            "evaluation:run",
            "evaluation:review",
            "evaluation:approve",
            "publication:read",
            "publication:generate",
            "publication:publish",
            "analytics:read",
            "analytics:materialize",
            "learning:read",
            "learning:generate",
            "learning:review",
            "learning:approve",
            "learning:assign",
            "quality:read",
            "quality:manage",
            "grading:read",
            "grading:manage",
            "grading:work",
            "moderation:read",
            "moderation:manage",
            "moderation:review",
            "grievance:read",
            "grievance:create",
            "grievance:manage",
        }
    ),
    "EVALUATOR": frozenset(
        {
            "institution:read",
            "academic_year:read",
            "class_section:read",
            "student:read",
            "curriculum:read",
            "assessment:read",
            "rubric:read",
            "submission:read",
            "submission:review",
            "mapping:read",
            "mapping:review",
            "transcription:read",
            "transcription:review",
            "evaluation:read",
            "evaluation:review",
            "publication:read",
            "analytics:read",
            "learning:read",
            "quality:read",
            "grading:read",
            "grading:work",
        }
    ),
    "MODERATOR": frozenset(
        {
            "institution:read",
            "academic_year:read",
            "class_section:read",
            "student:read",
            "assessment:read",
            "rubric:read",
            "submission:read",
            "evaluation:read",
            "publication:read",
            "moderation:read",
            "moderation:review",
            "grading:read",
            "grievance:read",
        }
    ),
    "HOD": frozenset(
        {
            "institution:read",
            "academic_year:read",
            "class_section:read",
            "student:read",
            "assessment:read",
            "rubric:read",
            "submission:read",
            "evaluation:read",
            "publication:read",
            "grading:read",
            "moderation:read",
            "moderation:manage",
            "moderation:review",
            "grievance:read",
            "grievance:manage",
        }
    ),
    "ACADEMIC_COORDINATOR": frozenset(
        {
            "institution:read",
            "academic_year:read",
            "class_section:read",
            "student:read",
            "assessment:read",
            "rubric:read",
            "submission:read",
            "evaluation:read",
            "publication:read",
            "grading:read",
            "moderation:read",
            "moderation:manage",
            "moderation:review",
            "grievance:read",
            "grievance:manage",
        }
    ),
    "EXAM_CONTROLLER": frozenset(
        {
            "institution:read",
            "academic_year:read",
            "class_section:read",
            "student:read",
            "assessment:read",
            "rubric:read",
            "submission:read",
            "evaluation:read",
            "publication:read",
            "grading:read",
            "moderation:read",
            "moderation:manage",
            "moderation:review",
            "grievance:read",
            "grievance:create",
            "grievance:manage",
        }
    ),
    "AUDITOR": frozenset(
        {
            "institution:read",
            "assessment:read",
            "submission:read",
            "evaluation:read",
            "publication:read",
            "grading:read",
            "moderation:read",
            "grievance:read",
            "analytics:read",
            "quality:read",
        }
    ),
    "STUDENT": frozenset(),
    "PARENT": frozenset(),
}


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    tenant_id: UUID
    roles: frozenset[str]
    permissions: frozenset[str]


def require_permissions(*codes: str) -> Callable[..., Awaitable[AuthContext]]:
    from app.core.security import get_current_user

    async def dependency(context: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not set(codes).issubset(context.permissions):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return context

    return dependency
