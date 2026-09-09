"""Isolated fixed benchmark providers for B15 gold regression (no ledger writes)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.ai.execution_metadata import AIExecutionMetadata

FIXED_BENCHMARK_PROVIDER = "fixed"
FIXED_BENCHMARK_PROMPT_TEMPLATE = "fixed-benchmark-v1"
FIXED_BENCHMARK_MODEL_VERSION = "B15_V1"

MODEL_PASS = "fixed-benchmark-pass"
MODEL_REGRESS = "fixed-benchmark-regress"
MODEL_INVALID = "fixed-benchmark-invalid"

SUPPORTED_MODELS = frozenset({MODEL_PASS, MODEL_REGRESS, MODEL_INVALID})


@dataclass(frozen=True)
class BenchmarkCandidateOutput:
    """Isolated candidate output for one gold case — never written to evaluation ledger."""

    marks: Decimal | None
    error_codes: list[str]
    missing_output: bool
    execution_metadata: AIExecutionMetadata


def _dec(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_error_codes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(code) for code in raw]


class FixedBenchmarkProvider:
    """Deterministic isolated evaluator for locked gold cases.

    Models:
    - ``fixed-benchmark-pass`` — returns expected marks/error_codes from the fixture
    - ``fixed-benchmark-regress`` — returns marks off by +1 (or half max) and wrong codes
    - ``fixed-benchmark-invalid`` — returns marks > max (safety invariant fail)

    Does not call production evaluation ledger writers.
    """

    provider_name = FIXED_BENCHMARK_PROVIDER

    def __init__(self, *, model: str) -> None:
        if model not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported fixed benchmark model: {model}")
        self.model = model

    def execution_metadata(self) -> AIExecutionMetadata:
        return AIExecutionMetadata(
            provider=FIXED_BENCHMARK_PROVIDER,
            model=self.model,
            model_version=FIXED_BENCHMARK_MODEL_VERSION,
            prompt_template_version=FIXED_BENCHMARK_PROMPT_TEMPLATE,
        )

    def evaluate_gold_case(
        self,
        replay_fixture: dict[str, Any],
        *,
        expected_final_marks: Decimal,
        expected_max_marks: Decimal,
        expected_error_codes: list[str],
    ) -> BenchmarkCandidateOutput:
        meta = self.execution_metadata()
        expected_codes = _normalize_error_codes(expected_error_codes)
        fixture_expected = replay_fixture.get("expected_final_marks")
        gold_marks = (
            _dec(fixture_expected)
            if fixture_expected is not None
            else _dec(expected_final_marks)
        )
        max_marks = _dec(
            replay_fixture.get("expected_max_marks", expected_max_marks)
        )

        if self.model == MODEL_PASS:
            return BenchmarkCandidateOutput(
                marks=gold_marks,
                error_codes=list(expected_codes),
                missing_output=False,
                execution_metadata=meta,
            )

        if self.model == MODEL_REGRESS:
            delta = Decimal("1")
            if gold_marks + delta > max_marks and max_marks > 0:
                delta = (max_marks / Decimal("2")).quantize(Decimal("0.0001"))
            regress_marks = gold_marks + delta
            if expected_codes:
                flipped = [f"REGRESS_{code}" for code in expected_codes]
            else:
                flipped = ["REGRESS_TAXONOMY_MISMATCH"]
            return BenchmarkCandidateOutput(
                marks=regress_marks,
                error_codes=flipped,
                missing_output=False,
                execution_metadata=meta,
            )

        # MODEL_INVALID — marks exceed max (safety invariant failure)
        invalid_marks = max_marks + Decimal("1")
        return BenchmarkCandidateOutput(
            marks=invalid_marks,
            error_codes=list(expected_codes),
            missing_output=False,
            execution_metadata=meta,
        )


def resolve_fixed_benchmark_provider(*, candidate_model: str) -> FixedBenchmarkProvider:
    if candidate_model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported candidate model: {candidate_model}")
    return FixedBenchmarkProvider(model=candidate_model)
