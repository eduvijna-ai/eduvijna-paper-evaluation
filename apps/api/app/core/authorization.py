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
        }
    ),
    "EVALUATOR": frozenset(
        {"institution:read", "academic_year:read", "class_section:read", "student:read"}
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
