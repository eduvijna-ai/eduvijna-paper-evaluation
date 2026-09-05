from decimal import Decimal

from app.db.models import RubricCriterion


def reconcile_rubric(
    criteria: list[RubricCriterion], question_max_marks: Decimal
) -> tuple[bool, Decimal]:
    """Validate rubric mark envelope against the question.

    Semantics (CVB A2):
    - ADDITIVE: awardable criteria must sum exactly to ``question_max_marks``.
    - DEDUCTIVE: scoring starts at ``question_max_marks``; criterion ``max_marks``
      are maximum deductions. The deduction envelope must equal the question max
      (full failure can reach zero). DEDUCTIVE is **not** validated by treating
      criteria as additive awards.
    - ALL_OR_NOTHING: every criterion band must equal the full question max.
    - Mixed ADDITIVE + DEDUCTIVE: additive awards must equal question max; any
      DEDUCTIVE envelope must be ``<=`` question max.
    - Empty criteria are never valid.
    """
    if not criteria:
        return False, Decimal("0.00")

    additive_total = sum(
        (c.max_marks for c in criteria if c.scoring_mode == "ADDITIVE"),
        Decimal("0.00"),
    )
    deductive_total = sum(
        (c.max_marks for c in criteria if c.scoring_mode == "DEDUCTIVE"),
        Decimal("0.00"),
    )
    all_or_nothing = [c for c in criteria if c.scoring_mode == "ALL_OR_NOTHING"]
    modes = {c.scoring_mode for c in criteria}

    if modes == {"ADDITIVE"}:
        valid = additive_total == question_max_marks
        return valid, additive_total

    if modes == {"DEDUCTIVE"}:
        valid = deductive_total == question_max_marks
        return valid, deductive_total

    if modes == {"ALL_OR_NOTHING"}:
        valid = all(c.max_marks == question_max_marks for c in all_or_nothing)
        return valid, question_max_marks if valid else Decimal("0.00")

    if "ADDITIVE" in modes and modes <= {"ADDITIVE", "DEDUCTIVE"}:
        valid = additive_total == question_max_marks and deductive_total <= question_max_marks
        return valid, additive_total

    # Unsupported mixes (e.g. ADDITIVE + ALL_OR_NOTHING) are invalid for A2.
    return False, additive_total
