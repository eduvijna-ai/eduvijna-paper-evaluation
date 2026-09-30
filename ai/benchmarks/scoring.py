"""Metric scoring helpers for the PREPROD-003 AI quality harness."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


METRIC_KEYS: tuple[str, ...] = (
    "student_identity_accuracy",
    "answer_region_accuracy",
    "question_mapping_accuracy",
    "transcription_accuracy",
    "evaluation_marking_accuracy",
    "teacher_vs_ai_score_agreement",
)

SUPPORTED_CATEGORIES: frozenset[str] = frozenset(
    {
        "clean_handwriting",
        "poor_handwriting",
        "crossed_out",
        "continuation",
        "faint",
        "rotated",
        "pen_colors",
        "math",
        "equations",
        "fractions",
        "tables",
        "diagrams",
        "incomplete",
        "alternate_methods",
        "multi_subject",
        "multilingual",
    }
)


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _exact(a: Any, b: Any) -> float:
    return 1.0 if a == b else 0.0


def _set_f1(expected: list[Any] | None, actual: list[Any] | None) -> float:
    exp = set(expected or [])
    act = set(actual or [])
    if not exp and not act:
        return 1.0
    if not exp or not act:
        return 0.0
    overlap = len(exp & act)
    precision = overlap / len(act)
    recall = overlap / len(exp)
    if precision + recall == 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _mapping_accuracy(expected: list[dict[str, Any]] | None, actual: list[dict[str, Any]] | None) -> float:
    exp = {
        (str(item.get("region_id")), str(item.get("question_version_id")))
        for item in (expected or [])
    }
    act = {
        (str(item.get("region_id")), str(item.get("question_version_id")))
        for item in (actual or [])
    }
    if not exp and not act:
        return 1.0
    if not exp or not act:
        return 0.0
    overlap = len(exp & act)
    return overlap / max(len(exp), len(act))


def _marks_agreement(expected: Any, actual: Any) -> float:
    e = _as_decimal(expected)
    a = _as_decimal(actual)
    if e is None and a is None:
        return 1.0
    if e is None or a is None:
        return 0.0
    return 1.0 if e == a else 0.0


def score_case(*, gold: dict[str, Any], prediction: dict[str, Any]) -> dict[str, float]:
    """Score one case across independent metrics (0.0–1.0 each)."""
    return {
        "student_identity_accuracy": _exact(
            gold.get("student_id"), prediction.get("student_id")
        ),
        "answer_region_accuracy": _set_f1(
            gold.get("answer_region_ids"), prediction.get("answer_region_ids")
        ),
        "question_mapping_accuracy": _mapping_accuracy(
            gold.get("question_mappings"), prediction.get("question_mappings")
        ),
        "transcription_accuracy": _exact(
            gold.get("transcription_text"), prediction.get("transcription_text")
        ),
        "evaluation_marking_accuracy": _marks_agreement(
            gold.get("final_marks"), prediction.get("proposed_marks")
        ),
        "teacher_vs_ai_score_agreement": _marks_agreement(
            gold.get("teacher_final_marks", gold.get("final_marks")),
            prediction.get("proposed_marks"),
        ),
    }


def aggregate_metrics(case_scores: list[dict[str, float]]) -> dict[str, float | None]:
    if not case_scores:
        return {key: None for key in METRIC_KEYS}
    out: dict[str, float | None] = {}
    for key in METRIC_KEYS:
        values = [row[key] for row in case_scores if key in row]
        out[key] = sum(values) / len(values) if values else None
    return out
