from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, Protocol


class _QuestionLike(Protocol):
    id: Any
    parent_question_version_id: Any | None
    sequence: int
    scoring_mode: str
    max_marks: Decimal
    selection_mode: str
    selection_count: int | None


def _children_map(
    questions: Sequence[_QuestionLike],
) -> dict[Any | None, list[_QuestionLike]]:
    children: dict[Any | None, list[_QuestionLike]] = defaultdict(list)
    for question in questions:
        children[question.parent_question_version_id].append(question)
    for items in children.values():
        items.sort(key=lambda q: q.sequence)
    return children


def effective_max_marks(
    question: _QuestionLike,
    children: dict[Any | None, list[_QuestionLike]],
) -> Decimal:
    child_list = children.get(question.id, [])
    if question.scoring_mode == "LEAF_SCORABLE" and not child_list:
        return Decimal(question.max_marks).quantize(Decimal("0.01"))

    if not child_list:
        return Decimal("0.00")

    child_totals = [effective_max_marks(child, children) for child in child_list]
    mode = (getattr(question, "selection_mode", None) or "ALL").upper()
    if mode == "ANY_N":
        count = question.selection_count
        if count is None or count < 1:
            raise ValueError("ANY_N container requires selection_count >= 1")
        if count > len(child_list):
            raise ValueError("selection_count exceeds eligible children")
        per_child = child_totals[0]
        for other in child_totals[1:]:
            if other != per_child:
                raise ValueError("ANY_N children must have equal effective max marks")
        return (Decimal(count) * per_child).quantize(Decimal("0.01"))

    return sum(child_totals, start=Decimal("0.00")).quantize(Decimal("0.01"))


def reconcile_marks(
    questions: Sequence[_QuestionLike], assessment_max_marks: Decimal
) -> tuple[bool, Decimal]:
    """Effective assessment maximum from roots (supports ANY_N choice groups)."""
    if not questions:
        total = Decimal("0.00")
        return total == Decimal(assessment_max_marks).quantize(Decimal("0.01")), total

    children = _children_map(questions)
    roots = [q for q in questions if q.parent_question_version_id is None]
    try:
        total = sum(
            (effective_max_marks(root, children) for root in roots),
            start=Decimal("0.00"),
        ).quantize(Decimal("0.01"))
    except ValueError:
        return False, Decimal("0.00")
    expected = Decimal(assessment_max_marks).quantize(Decimal("0.01"))
    return total == expected, total
