"""B8_V1 mastery derivation unit tests (no DB)."""

from __future__ import annotations

from decimal import Decimal

from app.services.mastery_derivation import aggregate_signal, derive_b8_v1_signals


def test_concept_error_yields_concept_weak() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("2"),
        max_mark=Decimal("5"),
        error_codes=["CONCEPT"],
        is_blank=False,
    )
    assert s.concept == "WEAK"
    assert "CONCEPT" in s.academic_error_codes
    assert s.execution == "INCONCLUSIVE"
    assert s.procedure == "INCONCLUSIVE"


def test_calculation_only_partial_concept_strong_execution_weak() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("3"),
        max_mark=Decimal("5"),
        error_codes=["CALCULATION"],
        is_blank=False,
    )
    assert s.concept == "STRONG"
    assert s.execution == "WEAK"
    assert "EXECUTION_SLIP_CONCEPT_INTACT" in s.reason_codes
    assert s.procedure == "INCONCLUSIVE"


def test_method_yields_procedure_weak() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("1"),
        max_mark=Decimal("5"),
        error_codes=["METHOD"],
        is_blank=False,
    )
    assert s.procedure == "WEAK"
    assert "METHOD" in s.academic_error_codes


def test_full_credit_clean_all_strong() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("5"),
        max_mark=Decimal("5"),
        error_codes=[],
        is_blank=False,
    )
    assert s.concept == "STRONG"
    assert s.execution == "STRONG"
    assert s.procedure == "STRONG"
    assert s.score_ratio == Decimal("1.000000")


def test_unreadable_all_inconclusive() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("0"),
        max_mark=Decimal("5"),
        error_codes=["UNREADABLE"],
        is_blank=False,
    )
    assert s.concept == "INCONCLUSIVE"
    assert s.execution == "INCONCLUSIVE"
    assert s.procedure == "INCONCLUSIVE"
    assert "UNREADABLE" in s.review_condition_codes


def test_ocr_transcription_inconclusive() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("0"),
        max_mark=Decimal("5"),
        error_codes=["OCR_TRANSCRIPTION"],
        is_blank=False,
    )
    assert s.concept == "INCONCLUSIVE"
    assert s.execution == "INCONCLUSIVE"
    assert s.procedure == "INCONCLUSIVE"
    assert "OCR_TRANSCRIPTION" in s.review_condition_codes


def test_blank_inconclusive_not_concept_weak() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("0"),
        max_mark=Decimal("5"),
        error_codes=["INCOMPLETE", "BLANK"],
        is_blank=True,
    )
    assert s.concept == "INCONCLUSIVE"
    assert s.execution == "INCONCLUSIVE"
    assert s.procedure == "INCONCLUSIVE"
    assert "BLANK" in s.reason_codes
    assert s.concept != "WEAK"


def test_valid_alternative_alone_not_concept_weak() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("4"),
        max_mark=Decimal("5"),
        error_codes=["VALID_ALTERNATIVE"],
        is_blank=False,
    )
    assert s.concept != "WEAK"
    assert "VALID_ALTERNATIVE" in s.academic_error_codes


def test_score_ratio_correct() -> None:
    s = derive_b8_v1_signals(
        final_score=Decimal("2.5"),
        max_mark=Decimal("5"),
        error_codes=[],
        is_blank=False,
    )
    assert s.score_ratio == Decimal("0.500000")

    s2 = derive_b8_v1_signals(
        final_score=Decimal("1"),
        max_mark=Decimal("3"),
        error_codes=["CONCEPT"],
        is_blank=False,
    )
    assert s2.score_ratio == (Decimal("1") / Decimal("3")).quantize(Decimal("0.000001"))


def test_aggregate_signal_strong_gt_weak() -> None:
    assert aggregate_signal(3, 1, 0) == "STRONG"


def test_aggregate_signal_weak_gt_strong() -> None:
    assert aggregate_signal(1, 4, 2) == "WEAK"


def test_aggregate_signal_tie_inconclusive() -> None:
    assert aggregate_signal(2, 2, 5) == "INCONCLUSIVE"
    assert aggregate_signal(0, 0, 10) == "INCONCLUSIVE"
