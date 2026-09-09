"""B12_V1 pure algorithm unit tests (no DB)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.services.b12_algorithm import (
    aggregate_dimension,
    compute_node_state,
    is_academic_error,
    is_review_condition,
    practice_kind_for_error,
    source_evidence_hash,
)


def test_aggregate_dimension_ratio_and_counts() -> None:
    ratio, decisive, inconclusive = aggregate_dimension(
        ["STRONG", "STRONG", "WEAK", "INCONCLUSIVE"]
    )
    assert decisive == 3
    assert inconclusive == 1
    assert ratio == Decimal("0.666667")


def test_aggregate_dimension_insufficient_when_only_inconclusive() -> None:
    ratio, decisive, inconclusive = aggregate_dimension(
        ["INCONCLUSIVE", "INCONCLUSIVE"]
    )
    assert ratio is None
    assert decisive == 0
    assert inconclusive == 2


def test_inconclusive_never_becomes_weakness() -> None:
    ratio, decisive, inconclusive = aggregate_dimension(["INCONCLUSIVE"])
    assert ratio is None
    assert decisive == 0
    assert inconclusive == 1
    # Pure STRONG stays 1.0 — inconclusive siblings do not dilute or weaken
    ratio2, decisive2, _ = aggregate_dimension(["STRONG", "INCONCLUSIVE"])
    assert ratio2 == Decimal("1.000000")
    assert decisive2 == 1


def test_compute_node_state_independent_dimensions() -> None:
    state = compute_node_state(
        concept_strengths=["STRONG", "WEAK"],
        execution_strengths=["INCONCLUSIVE"],
    )
    assert state["concept_mastery"] == Decimal("0.500000")
    assert state["concept_decisive_count"] == 2
    assert state["execution_accuracy"] is None
    assert state["execution_decisive_count"] == 0
    assert state["execution_inconclusive_count"] == 1
    assert state["evidence_count"] == 3


def test_practice_kind_mapping() -> None:
    assert practice_kind_for_error("CONCEPT") == "CONCEPT_CHECK"
    assert practice_kind_for_error("FORMULA") == "CONCEPT_CHECK"
    assert practice_kind_for_error("CALCULATION") == "EXECUTION_PRACTICE"
    assert practice_kind_for_error("METHOD") == "PROCEDURE_PRACTICE"
    assert practice_kind_for_error("NOTATION") == "CONCEPT_CHECK"
    assert practice_kind_for_error("PRESENTATION") == "CONCEPT_CHECK"


def test_source_evidence_hash_stable_and_order_independent() -> None:
    a = uuid.UUID("11111111-1111-1111-1111-111111111111")
    b = uuid.UUID("22222222-2222-2222-2222-222222222222")
    assert source_evidence_hash([a, b]) == source_evidence_hash([b, a])
    assert len(source_evidence_hash([a])) == 64
    assert source_evidence_hash([a]) != source_evidence_hash([b])


def test_academic_vs_review_helpers() -> None:
    assert is_academic_error("CALCULATION")
    assert is_academic_error("VALID_ALTERNATIVE")
    assert not is_academic_error("UNREADABLE")
    assert is_review_condition("UNREADABLE")
    assert is_review_condition("OCR_TRANSCRIPTION")
    assert not is_review_condition("CONCEPT")
