"""B15 gold benchmark candidates: CI fixtures + configured EvaluationAIProvider path.

Credential-free CI uses ``FixedBenchmarkProvider`` models
(``fixed-benchmark-pass|regress|invalid``).

Production / configured candidates resolve exclusively through
``get_evaluation_provider()`` (registry) and ``evaluate_rubric`` — never vendor
SDKs from the benchmark service. Outputs are isolated and never written to the
evaluation ledger or published/mastery tables.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.ai.execution_metadata import (
    AIExecutionMetadata,
    metadata_from_provider,
)
from app.ai.protocols import EvaluationAIProvider
from app.ai.registry import (
    evaluation_provider_active,
    get_evaluation_provider,
)
from app.ai.types import (
    ProviderUnavailable,
    RubricCriterionSnapshot,
    RubricEvaluationInput,
    RubricEvaluationResult,
)
from app.core.config import Settings, get_settings

FIXED_BENCHMARK_PROVIDER = "fixed"
FIXED_BENCHMARK_PROMPT_TEMPLATE = "fixed-benchmark-v1"
FIXED_BENCHMARK_MODEL_VERSION = "B15_V1"

MODEL_PASS = "fixed-benchmark-pass"
MODEL_REGRESS = "fixed-benchmark-regress"
MODEL_INVALID = "fixed-benchmark-invalid"

CI_FIXTURE_MODELS = frozenset({MODEL_PASS, MODEL_REGRESS, MODEL_INVALID})
# Back-compat alias
SUPPORTED_MODELS = CI_FIXTURE_MODELS


@dataclass(frozen=True)
class BenchmarkCandidateOutput:
    """Isolated candidate output for one gold case — never written to evaluation ledger."""

    marks: Decimal | None
    error_codes: list[str]
    missing_output: bool
    execution_metadata: AIExecutionMetadata


class BenchmarkCandidateError(RuntimeError):
    """Raised when a candidate cannot be resolved or is unconfigured."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _dec(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_error_codes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(code) for code in raw]


def is_ci_fixture_candidate(*, candidate_provider: str, candidate_model: str) -> bool:
    return (
        candidate_provider == FIXED_BENCHMARK_PROVIDER
        and candidate_model in CI_FIXTURE_MODELS
    )


class FixedBenchmarkProvider:
    """Deterministic isolated evaluator for locked gold cases (CI / credential-free).

    Models:
    - ``fixed-benchmark-pass`` — returns expected marks/error_codes from the fixture
    - ``fixed-benchmark-regress`` — returns marks off by +1 (or half max) and wrong codes
    - ``fixed-benchmark-invalid`` — returns marks > max (safety invariant fail)

    Does not call production evaluation ledger writers.
    """

    provider_name = FIXED_BENCHMARK_PROVIDER

    def __init__(self, *, model: str) -> None:
        if model not in CI_FIXTURE_MODELS:
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
    if candidate_model not in CI_FIXTURE_MODELS:
        raise ValueError(f"Unsupported candidate model: {candidate_model}")
    return FixedBenchmarkProvider(model=candidate_model)


def replay_fixture_to_rubric_input(
    replay_fixture: dict[str, Any],
) -> RubricEvaluationInput:
    """Build typed ``RubricEvaluationInput`` from a PII-minimized frozen fixture."""
    criteria_raw = replay_fixture.get("criterion_snapshot") or []
    if not isinstance(criteria_raw, list) or len(criteria_raw) < 1:
        raise BenchmarkCandidateError(
            "BENCHMARK_REPLAY_INVALID",
            "Replay fixture lacks rubric criterion_snapshot required for evaluation",
        )
    criteria = [RubricCriterionSnapshot.model_validate(item) for item in criteria_raw]
    qv = replay_fixture.get("question_version_id")
    av = replay_fixture.get("assessment_version_id")
    if not qv or not av:
        raise BenchmarkCandidateError(
            "BENCHMARK_REPLAY_INVALID",
            "Replay fixture missing question_version_id or assessment_version_id",
        )
    max_mark = _dec(
        replay_fixture.get("max_mark")
        or replay_fixture.get("expected_max_marks")
        or "0"
    )
    return RubricEvaluationInput(
        question_version_id=uuid.UUID(str(qv)),
        assessment_version_id=uuid.UUID(str(av)),
        rubric_criteria=criteria,
        answer_key_text=str(replay_fixture.get("answer_key_text") or ""),
        structured_answer=replay_fixture.get("structured_answer"),
        transcription_text=str(replay_fixture.get("transcription_text") or ""),
        blank_flag=bool(replay_fixture.get("blank_flag")),
        unreadable_flag=bool(replay_fixture.get("unreadable_flag")),
        math_verification_summary=replay_fixture.get("math_verification_summary"),
        max_mark=max_mark,
    )


def rubric_result_to_candidate_output(
    result: RubricEvaluationResult,
    *,
    execution_metadata: AIExecutionMetadata,
) -> BenchmarkCandidateOutput:
    """Map ``evaluate_rubric`` output to isolated benchmark comparison fields."""
    codes = _normalize_error_codes(list(result.error_codes or []))
    for prop in result.criterion_proposals:
        if prop.error_code:
            codes.append(str(prop.error_code))
    codes = sorted(set(codes))

    marks = result.proposed_total
    if marks is None:
        proposal_marks = [
            p.proposed_marks
            for p in result.criterion_proposals
            if p.proposed_marks is not None
        ]
        if not proposal_marks:
            return BenchmarkCandidateOutput(
                marks=None,
                error_codes=codes,
                missing_output=True,
                execution_metadata=execution_metadata,
            )
        marks = sum(proposal_marks, Decimal("0"))

    return BenchmarkCandidateOutput(
        marks=Decimal(str(marks)),
        error_codes=codes,
        missing_output=False,
        execution_metadata=execution_metadata,
    )


class EvaluationBenchmarkAdapter:
    """Isolated gold replay via ``EvaluationAIProvider.evaluate_rubric``.

    Never writes QuestionEvaluation / PublishedResult / mastery state.
    """

    def __init__(self, provider: EvaluationAIProvider) -> None:
        self._provider = provider
        self.provider_name = str(getattr(provider, "provider_name", "unknown"))

    async def evaluate_gold_case(
        self,
        replay_fixture: dict[str, Any],
        *,
        expected_final_marks: Decimal,
        expected_max_marks: Decimal,
        expected_error_codes: list[str],
    ) -> BenchmarkCandidateOutput:
        del expected_final_marks, expected_max_marks, expected_error_codes
        request = replay_fixture_to_rubric_input(replay_fixture)
        meta = metadata_from_provider(self._provider, "gold_benchmark_evaluate")
        try:
            result = await self._provider.evaluate_rubric(request)
        except ProviderUnavailable as exc:
            raise BenchmarkCandidateError(
                "BENCHMARK_CANDIDATE_UNCONFIGURED",
                str(exc),
            ) from exc
        return rubric_result_to_candidate_output(result, execution_metadata=meta)


def resolve_benchmark_candidate(
    *,
    candidate_provider: str,
    candidate_model: str,
    settings: Settings | None = None,
) -> FixedBenchmarkProvider | EvaluationBenchmarkAdapter:
    """Resolve a B15 candidate executor.

    * CI fixtures: ``fixed`` + ``fixed-benchmark-*`` → ``FixedBenchmarkProvider``
    * Configured path: ``candidate_provider`` must match the active registry
      evaluation provider's ``provider_name`` (``fixed`` / ``openai`` / …).
    """
    settings = settings or get_settings()
    provider_key = (candidate_provider or "").strip().lower()
    model_key = (candidate_model or "").strip()

    if is_ci_fixture_candidate(
        candidate_provider=provider_key, candidate_model=model_key
    ):
        return FixedBenchmarkProvider(model=model_key)

    if not evaluation_provider_active(settings):
        raise BenchmarkCandidateError(
            "BENCHMARK_CANDIDATE_UNCONFIGURED",
            "No evaluation AI provider is configured "
            "(set AI_PROVIDER_VISION to fixed or openai)",
        )

    eval_provider = get_evaluation_provider(settings)
    active_name = str(getattr(eval_provider, "provider_name", "") or "").lower()
    if provider_key != active_name:
        raise BenchmarkCandidateError(
            "BENCHMARK_CANDIDATE_UNSUPPORTED",
            f"Candidate provider {candidate_provider!r} does not match active "
            f"evaluation provider {active_name!r}",
        )

    # Reject CI fixture model names on the configured path to avoid ambiguity.
    if model_key in CI_FIXTURE_MODELS:
        raise BenchmarkCandidateError(
            "BENCHMARK_CANDIDATE_UNSUPPORTED",
            f"Model {candidate_model!r} is reserved for the deterministic CI fixture path",
        )

    return EvaluationBenchmarkAdapter(eval_provider)


async def evaluate_benchmark_candidate(
    *,
    candidate_provider: str,
    candidate_model: str,
    replay_fixture: dict[str, Any],
    expected_final_marks: Decimal,
    expected_max_marks: Decimal,
    expected_error_codes: list[str],
    settings: Settings | None = None,
) -> BenchmarkCandidateOutput:
    """Execute one isolated gold case against the resolved candidate."""
    executor = resolve_benchmark_candidate(
        candidate_provider=candidate_provider,
        candidate_model=candidate_model,
        settings=settings,
    )
    if isinstance(executor, FixedBenchmarkProvider):
        return executor.evaluate_gold_case(
            replay_fixture,
            expected_final_marks=expected_final_marks,
            expected_max_marks=expected_max_marks,
            expected_error_codes=expected_error_codes,
        )

    try:
        return await executor.evaluate_gold_case(
            replay_fixture,
            expected_final_marks=expected_final_marks,
            expected_max_marks=expected_max_marks,
            expected_error_codes=expected_error_codes,
        )
    except ProviderUnavailable as exc:
        raise BenchmarkCandidateError(
            "BENCHMARK_CANDIDATE_UNCONFIGURED",
            str(exc),
        ) from exc
