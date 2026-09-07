"""B8_V1 deterministic mastery evidence derivation from published ledger facts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

EvidenceType = Literal["CONCEPT", "EXECUTION", "PROCEDURE"]
Strength = Literal["STRONG", "WEAK", "INCONCLUSIVE"]

ALGORITHM_VERSION = "B8_V1"

# Review/system conditions that force INCONCLUSIVE across all evidence types.
REVIEW_INCONCLUSIVE_CODES: frozenset[str] = frozenset(
    {
        "UNREADABLE",
        "OCR_TRANSCRIPTION",
        "QUESTION_MAPPING",
        "IDENTITY_MAPPING",
        "RUBRIC_AMBIGUITY",
        "OTHER_REVIEW_REQUIRED",
    }
)

CONCEPT_WEAK_CODES: frozenset[str] = frozenset(
    {"CONCEPT", "FORMULA", "INTERPRETATION", "LOGIC_REASONING"}
)
EXECUTION_WEAK_CODES: frozenset[str] = frozenset(
    {"CALCULATION", "ALGEBRA", "SIGN", "SUBSTITUTION", "UNIT", "FINAL_ANSWER"}
)
PROCEDURE_WEAK_CODES: frozenset[str] = frozenset({"METHOD", "INCOMPLETE"})

# Must not auto-convert to concept weakness.
NON_CONCEPT_WEAKNESS_CODES: frozenset[str] = frozenset(
    {"NOTATION", "PRESENTATION", "DIAGRAM", "VALID_ALTERNATIVE"}
)


@dataclass(frozen=True)
class DerivedSignals:
    concept: Strength
    execution: Strength
    procedure: Strength
    academic_error_codes: tuple[str, ...]
    review_condition_codes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    score_ratio: Decimal


def _sorted_unique(codes: list[str] | set[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({c for c in codes if c}))


def derive_b8_v1_signals(
    *,
    final_score: Decimal,
    max_mark: Decimal,
    error_codes: list[str] | None,
    is_blank: bool,
) -> DerivedSignals:
    """Derive CONCEPT/EXECUTION/PROCEDURE strengths from final ledger facts only.

    Never uses proposed_ai_score. BLANK and review/system conditions are INCONCLUSIVE,
    not academic weakness. score_ratio is factual and separate from mastery strength.
    """
    if max_mark <= 0:
        raise ValueError("max_mark must be > 0")
    if final_score < 0 or final_score > max_mark:
        raise ValueError("final_score out of range")

    score_ratio = (final_score / max_mark).quantize(Decimal("0.000001"))
    codes = list(error_codes or [])
    review = _sorted_unique([c for c in codes if c in REVIEW_INCONCLUSIVE_CODES])
    academic = _sorted_unique(
        [
            c
            for c in codes
            if c not in REVIEW_INCONCLUSIVE_CODES and c != "BLANK"
        ]
    )
    reasons: list[str] = []

    if is_blank:
        reasons.append("BLANK")
        return DerivedSignals(
            concept="INCONCLUSIVE",
            execution="INCONCLUSIVE",
            procedure="INCONCLUSIVE",
            academic_error_codes=academic,
            review_condition_codes=review,
            reason_codes=_sorted_unique(reasons),
            score_ratio=score_ratio,
        )

    if review:
        reasons.extend(review)
        return DerivedSignals(
            concept="INCONCLUSIVE",
            execution="INCONCLUSIVE",
            procedure="INCONCLUSIVE",
            academic_error_codes=academic,
            review_condition_codes=review,
            reason_codes=_sorted_unique(reasons),
            score_ratio=score_ratio,
        )

    concept_weak = bool(set(academic) & CONCEPT_WEAK_CODES)
    execution_weak = bool(set(academic) & EXECUTION_WEAK_CODES)
    procedure_weak = bool(set(academic) & PROCEDURE_WEAK_CODES)

    full_credit = final_score == max_mark
    zero_score = final_score == 0

    # Full credit with no review-blocking condition → STRONG across types.
    if full_credit and not concept_weak and not execution_weak and not procedure_weak:
        return DerivedSignals(
            concept="STRONG",
            execution="STRONG",
            procedure="STRONG",
            academic_error_codes=academic,
            review_condition_codes=review,
            reason_codes=_sorted_unique(reasons),
            score_ratio=score_ratio,
        )

    # Concept
    if concept_weak:
        concept: Strength = "WEAK"
        reasons.extend(sorted(set(academic) & CONCEPT_WEAK_CODES))
    elif execution_weak and not concept_weak and final_score > 0:
        # PEV-033: calculation/execution slip with otherwise valid reasoning.
        concept = "STRONG"
        reasons.append("EXECUTION_SLIP_CONCEPT_INTACT")
    elif full_credit:
        concept = "STRONG"
    elif zero_score and not academic:
        # Low/zero without supporting taxonomy → do not invent WEAK.
        concept = "INCONCLUSIVE"
        reasons.append("INSUFFICIENT_TAXONOMY")
    elif zero_score and procedure_weak and not concept_weak and not execution_weak:
        concept = "INCONCLUSIVE"
    else:
        concept = "INCONCLUSIVE" if not academic else ("WEAK" if concept_weak else "INCONCLUSIVE")

    # Execution
    if execution_weak:
        execution: Strength = "WEAK"
        reasons.extend(sorted(set(academic) & EXECUTION_WEAK_CODES))
    elif full_credit:
        execution = "STRONG"
    elif concept_weak and not execution_weak and final_score > 0:
        execution = "INCONCLUSIVE"
    else:
        execution = "INCONCLUSIVE"

    # Procedure
    if procedure_weak:
        # INCOMPLETE alone on a non-blank scored question may be procedure WEAK,
        # but BLANK already returned above. Avoid treating pure zero+INCOMPLETE
        # from blank-like paths here — is_blank handles BLANK.
        procedure: Strength = "WEAK"
        reasons.extend(sorted(set(academic) & PROCEDURE_WEAK_CODES))
    elif full_credit:
        procedure = "STRONG"
    else:
        procedure = "INCONCLUSIVE"

    # Non-concept codes must not flip concept to WEAK.
    if concept == "WEAK" and not concept_weak:
        concept = "INCONCLUSIVE"

    # VALID_ALTERNATIVE / presentation / notation / diagram: never concept WEAK alone.
    only_non_concept = bool(academic) and set(academic).issubset(NON_CONCEPT_WEAKNESS_CODES)
    if only_non_concept:
        if concept == "WEAK":
            concept = "INCONCLUSIVE"
        if full_credit:
            concept, execution, procedure = "STRONG", "STRONG", "STRONG"

    return DerivedSignals(
        concept=concept,
        execution=execution,
        procedure=procedure,
        academic_error_codes=academic,
        review_condition_codes=review,
        reason_codes=_sorted_unique(reasons),
        score_ratio=score_ratio,
    )


def aggregate_signal(strong: int, weak: int, inconclusive: int) -> Strength:
    """Current evidence profile projection — not persisted MasteryState."""
    del inconclusive  # counts available to caller; aggregate uses strong vs weak
    if strong > weak:
        return "STRONG"
    if weak > strong:
        return "WEAK"
    return "INCONCLUSIVE"
