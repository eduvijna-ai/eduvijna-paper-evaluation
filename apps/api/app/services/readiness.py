import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AnswerKeyVersion,
    AssessmentVersion,
    QuestionVersion,
    RubricCriterion,
    RubricVersion,
)
from app.services.mark_reconciliation import reconcile_marks
from app.services.rubric_reconciliation import reconcile_rubric


async def ensure_assessment_ready(
    db: AsyncSession, *, tenant_id: uuid.UUID, assessment_version: AssessmentVersion
) -> None:
    questions = list(
        (
            await db.scalars(
                select(QuestionVersion).where(
                    QuestionVersion.tenant_id == tenant_id,
                    QuestionVersion.assessment_version_id == assessment_version.id,
                )
            )
        ).all()
    )
    parent_ids = {
        question.parent_question_version_id
        for question in questions
        if question.parent_question_version_id is not None
    }
    leaves = [
        question
        for question in questions
        if question.id not in parent_ids and question.scoring_mode == "LEAF_SCORABLE"
    ]
    if not leaves:
        raise HTTPException(
            409,
            {
                "code": "ASSESSMENT_NO_SCORABLE_QUESTIONS",
                "message": (
                    "Assessment must include at least one LEAF_SCORABLE question before READY"
                ),
            },
        )
    marks_ok, total = reconcile_marks(questions, assessment_version.max_marks)
    if not marks_ok:
        raise HTTPException(
            409,
            "Assessment marks do not reconcile: "
            f"leaf total {total} != {assessment_version.max_marks}",
        )
    for question in leaves:
        answer = await db.scalar(
            select(AnswerKeyVersion).where(
                AnswerKeyVersion.tenant_id == tenant_id,
                AnswerKeyVersion.question_version_id == question.id,
                AnswerKeyVersion.status == "APPROVED",
            )
        )
        if answer is None:
            raise HTTPException(
                409, f"Question {question.display_label} lacks an approved answer key"
            )
        rubric = await db.scalar(
            select(RubricVersion).where(
                RubricVersion.tenant_id == tenant_id,
                RubricVersion.question_version_id == question.id,
                RubricVersion.status == "APPROVED",
            )
        )
        if rubric is None:
            raise HTTPException(409, f"Question {question.display_label} lacks an approved rubric")
        criteria = list(
            (
                await db.scalars(
                    select(RubricCriterion).where(
                        RubricCriterion.tenant_id == tenant_id,
                        RubricCriterion.rubric_version_id == rubric.id,
                    )
                )
            ).all()
        )
        rubric_ok, _ = reconcile_rubric(criteria, question.max_marks)
        if not rubric_ok:
            raise HTTPException(409, f"Rubric for {question.display_label} does not reconcile")
