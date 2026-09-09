"""B16.1 grading ownership access policy for ledger-review mutations.

When a QuestionEvaluation is governed by an active B16 grading work item,
only the assigned evaluator — or an explicit grading-governance override
actor — may mutate the ledger via B6 accept/override/feedback/escalate.

Legacy path (no governing work item): unchanged B6 behavior.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GradingWorkItem

# Work items that still govern QE review authority.
# COMPLETED historical assignments do not block later workflows.
GOVERNING_WORK_ITEM_STATUSES = frozenset(
    {"QUEUED", "IN_PROGRESS", "SUBMITTED", "RETURNED"}
)

# Explicit enterprise grading-governance override allowlist.
# evaluation:review alone is never sufficient for cross-assignment override.
GRADING_GOVERNANCE_ROLES = frozenset(
    {
        "INSTITUTION_ADMIN",
        "EXAM_CONTROLLER",
        "HOD",
        "ACADEMIC_COORDINATOR",
    }
)

GRADING_GOVERNANCE_PERMISSION = "grading:manage"


class GradingAccessError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


async def get_governing_work_item(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    question_evaluation_id: uuid.UUID,
) -> GradingWorkItem | None:
    """Return the single active governing work item for a QE, if any."""
    item = await db.scalar(
        select(GradingWorkItem).where(
            GradingWorkItem.tenant_id == tenant_id,
            GradingWorkItem.question_evaluation_id == question_evaluation_id,
            GradingWorkItem.status.in_(list(GOVERNING_WORK_ITEM_STATUSES)),
        )
    )
    return item if isinstance(item, GradingWorkItem) else None


def is_grading_governance_override(
    *,
    actor_roles: Collection[str],
    actor_permissions: Collection[str],
) -> bool:
    roles = frozenset(actor_roles)
    perms = frozenset(actor_permissions)
    return bool(roles & GRADING_GOVERNANCE_ROLES) and (
        GRADING_GOVERNANCE_PERMISSION in perms
    )


async def assert_question_evaluation_review_allowed(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    question_evaluation_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_roles: Collection[str],
    actor_permissions: Collection[str],
) -> None:
    """Enforce B16 ownership at the authoritative ledger-review boundary.

    Raises GradingAccessError(GRADING_ASSIGNMENT_FORBIDDEN) when a governing
    work item exists and the actor is neither the assignee nor a governance
    override actor. Does not leak cross-tenant existence (caller must already
    have tenant-scoped the QuestionEvaluation).
    """
    item = await get_governing_work_item(
        db,
        tenant_id=tenant_id,
        question_evaluation_id=question_evaluation_id,
    )
    if item is None:
        return
    if item.assigned_evaluator_id == actor_user_id:
        return
    if is_grading_governance_override(
        actor_roles=actor_roles, actor_permissions=actor_permissions
    ):
        return
    raise GradingAccessError(
        "GRADING_ASSIGNMENT_FORBIDDEN",
        "Question evaluation is assigned to another grading work-item owner",
    )
