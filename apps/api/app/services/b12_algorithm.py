"""B12_V1 pure deterministic longitudinal mastery / mistake intelligence logic."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from app.services.mastery_derivation import (
    CONCEPT_WEAK_CODES,
    EXECUTION_WEAK_CODES,
    PROCEDURE_WEAK_CODES,
    REVIEW_INCONCLUSIVE_CODES,
)

ALGORITHM_VERSION_B12_V1 = "B12_V1"
RECURRENCE_THRESHOLD = 2
RECOVERABLE_DISCLAIMER = (
    "Potentially recoverable marks are an analytical estimate from final "
    "criterion deductions, not guaranteed recovery."
)

ACADEMIC_ERROR_CODES: frozenset[str] = frozenset(
    {
        "CONCEPT",
        "FORMULA",
        "METHOD",
        "CALCULATION",
        "ALGEBRA",
        "SIGN",
        "SUBSTITUTION",
        "NOTATION",
        "UNIT",
        "DIAGRAM",
        "INTERPRETATION",
        "INCOMPLETE",
        "LOGIC_REASONING",
        "PRESENTATION",
        "FINAL_ANSWER",
        "VALID_ALTERNATIVE",
    }
)

_QUANT = Decimal("0.000001")


def is_academic_error(code: str) -> bool:
    return code in ACADEMIC_ERROR_CODES


def is_review_condition(code: str) -> bool:
    return code in REVIEW_INCONCLUSIVE_CODES


def aggregate_dimension(
    strengths: list[str],
) -> tuple[Decimal | None, int, int]:
    """Aggregate STRONG/WEAK/INCONCLUSIVE into mastery ratio + counts.

    Decisive = STRONG/WEAK only. Ratio = strong/(strong+weak) quantized to 1e-6.
    INCONCLUSIVE is counted separately and never treated as weakness.
    Returns (ratio_or_none, decisive_count, inconclusive_count).
    """
    strong = 0
    weak = 0
    inconclusive = 0
    for s in strengths:
        if s == "STRONG":
            strong += 1
        elif s == "WEAK":
            weak += 1
        elif s == "INCONCLUSIVE":
            inconclusive += 1
    decisive = strong + weak
    if decisive == 0:
        return None, 0, inconclusive
    ratio = (Decimal(strong) / Decimal(decisive)).quantize(_QUANT)
    return ratio, decisive, inconclusive


def compute_node_state(
    concept_strengths: list[str],
    execution_strengths: list[str],
) -> dict[str, Any]:
    concept_mastery, concept_decisive, concept_inc = aggregate_dimension(
        concept_strengths
    )
    execution_accuracy, execution_decisive, execution_inc = aggregate_dimension(
        execution_strengths
    )
    return {
        "concept_mastery": concept_mastery,
        "execution_accuracy": execution_accuracy,
        "concept_decisive_count": concept_decisive,
        "execution_decisive_count": execution_decisive,
        "concept_inconclusive_count": concept_inc,
        "execution_inconclusive_count": execution_inc,
        "evidence_count": len(concept_strengths) + len(execution_strengths),
    }


def source_evidence_hash(evidence_ids: Iterable[uuid.UUID]) -> str:
    sorted_ids = sorted(str(i) for i in evidence_ids)
    payload = "\n".join(sorted_ids).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def practice_kind_for_error(code: str) -> str:
    if code in CONCEPT_WEAK_CODES:
        return "CONCEPT_CHECK"
    if code in EXECUTION_WEAK_CODES:
        return "EXECUTION_PRACTICE"
    if code in PROCEDURE_WEAK_CODES:
        return "PROCEDURE_PRACTICE"
    return "CONCEPT_CHECK"
