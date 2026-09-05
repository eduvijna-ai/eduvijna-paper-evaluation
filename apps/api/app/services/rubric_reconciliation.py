from decimal import Decimal

from app.db.models import RubricCriterion


def reconcile_rubric(
    criteria: list[RubricCriterion], question_max_marks: Decimal
) -> tuple[bool, Decimal]:
    """ADDITIVE criteria must total the question marks; DEDUCTIVE starts at question max."""
    additive_total = sum(
        (criterion.max_marks for criterion in criteria if criterion.scoring_mode == "ADDITIVE"),
        Decimal("0.00"),
    )
    has_additive = any(criterion.scoring_mode == "ADDITIVE" for criterion in criteria)
    valid = additive_total == question_max_marks if has_additive else bool(criteria)
    return valid, additive_total
