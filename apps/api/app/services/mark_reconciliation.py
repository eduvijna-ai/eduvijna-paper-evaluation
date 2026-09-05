from decimal import Decimal

from app.db.models import QuestionVersion


def reconcile_marks(
    questions: list[QuestionVersion], assessment_max_marks: Decimal
) -> tuple[bool, Decimal]:
    """Only LEAF_SCORABLE questions count; CONTAINER_DERIVED marks are display aggregates."""
    parent_ids = {
        question.parent_question_version_id
        for question in questions
        if question.parent_question_version_id is not None
    }
    leaf_total = sum(
        (
            question.max_marks
            for question in questions
            if question.id not in parent_ids and question.scoring_mode == "LEAF_SCORABLE"
        ),
        Decimal("0.00"),
    )
    return leaf_total == assessment_max_marks, leaf_total
