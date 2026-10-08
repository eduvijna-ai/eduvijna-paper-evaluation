"""ANY_N choice-group validation for mapping and finalization."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from app.db.models import QuestionAnswerMapping, QuestionVersion


@dataclass(frozen=True)
class ChoiceGroupViolation:
    container_question_version_id: uuid.UUID
    container_label: str
    selection_count: int
    answered_count: int


def _children_map(
    questions: list[QuestionVersion],
) -> dict[uuid.UUID | None, list[QuestionVersion]]:
    children: dict[uuid.UUID | None, list[QuestionVersion]] = defaultdict(list)
    for question in questions:
        children[question.parent_question_version_id].append(question)
    for items in children.values():
        items.sort(key=lambda q: q.sequence)
    return children


def _leaf_descendants(
    node: QuestionVersion, children: dict[uuid.UUID | None, list[QuestionVersion]]
) -> list[QuestionVersion]:
    child_list = children.get(node.id, [])
    if not child_list:
        if node.scoring_mode == "LEAF_SCORABLE":
            return [node]
        return []
    leaves: list[QuestionVersion] = []
    for child in child_list:
        leaves.extend(_leaf_descendants(child, children))
    return leaves


def find_choice_group_over_attempts(
    questions: list[QuestionVersion],
    mappings: dict[uuid.UUID, QuestionAnswerMapping],
) -> list[ChoiceGroupViolation]:
    children = _children_map(questions)
    violations: list[ChoiceGroupViolation] = []
    for question in questions:
        mode = (question.selection_mode or "ALL").upper()
        if mode != "ANY_N":
            continue
        count = question.selection_count
        if count is None:
            continue
        direct_children = children.get(question.id, [])
        answered = 0
        for child in direct_children:
            for leaf in _leaf_descendants(child, children):
                mapping = mappings.get(leaf.id)
                if mapping is not None and mapping.disposition == "ANSWERED":
                    answered += 1
                    break
        if answered > count:
            violations.append(
                ChoiceGroupViolation(
                    container_question_version_id=question.id,
                    container_label=question.display_label,
                    selection_count=count,
                    answered_count=answered,
                )
            )
    return violations
