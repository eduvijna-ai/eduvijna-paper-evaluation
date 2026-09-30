"""Optional OpenAI structure + evaluation provider (no network in CI)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.execution_metadata import AIExecutionMetadata, openai_execution_metadata
from app.ai.types import (
    AnswerKeyProposalInput,
    AnswerKeyProposalResult,
    CurriculumMappingProposalInput,
    CurriculumMappingProposalResult,
    ErrorClassificationInput,
    ErrorClassificationResult,
    IdentityExtractionInput,
    IdentityExtractionResult,
    ImprovementBlueprintAIInput,
    ImprovementBlueprintAIResult,
    LearningPlanAIInput,
    LearningPlanAIResult,
    PageAnalysisInput,
    PageAnalysisResult,
    ParentNarrativeInput,
    ParentNarrativeResult,
    ProviderUnavailable,
    QuestionPaperParseInput,
    QuestionPaperParseResult,
    RegionMappingInput,
    RegionMappingResult,
    RubricEvaluationInput,
    RubricEvaluationResult,
    RubricProposalInput,
    RubricProposalResult,
    StudentNarrativeInput,
    StudentNarrativeResult,
    TranscriptionInput,
    TranscriptionResult,
)

JsonCaller = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]

logger = logging.getLogger(__name__)

# Bounded retries for transient OpenAI/network failures only.
_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BACKOFF_SECONDS = (0.5, 1.0, 2.0)


def _exception_status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value
    return None


def is_transient_openai_failure(exc: BaseException) -> bool:
    """Return True for timeouts / rate limits / 5xx-style transient failures."""
    name = type(exc).__name__
    if name in {
        "APITimeoutError",
        "APIConnectionError",
        "RateLimitError",
        "InternalServerError",
        "TimeoutError",
        "asyncio.TimeoutError",
    }:
        return True
    status = _exception_status_code(exc)
    if status in {408, 409, 425, 429, 500, 502, 503, 504}:
        return True
    # httpx / generic transport hints (message only; no silent mark invention)
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "timed out",
            "timeout",
            "connection reset",
            "temporarily unavailable",
            "rate limit",
        )
    )


class OpenAIStructureProvider:
    """Implements StructureAIProvider and EvaluationAIProvider."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None,
        model_identity: str,
        model_page_analysis: str,
        model_mapping: str,
        model_transcription: str,
        model_evaluation: str | None = None,
        model_student_report: str | None = None,
        model_parent_report: str | None = None,
        model_learning_plan: str | None = None,
        model_improvement_blueprint: str | None = None,
        model_question_paper_parse: str | None = None,
        model_answer_key_proposal: str | None = None,
        model_rubric_proposal: str | None = None,
        model_curriculum_mapping_proposal: str | None = None,
        timeout_seconds: int = 60,
        caller: JsonCaller | None = None,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: tuple[float, ...] = _DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._models = {
            "identity": model_identity,
            "page_analysis": model_page_analysis,
            "mapping": model_mapping,
            "transcription": model_transcription,
            "evaluate_rubric": model_evaluation or model_transcription,
            "classify_error": model_evaluation or model_transcription,
            "generate_student_explanation": model_student_report or model_transcription,
            "generate_parent_summary": model_parent_report or model_transcription,
            "generate_learning_plan": model_learning_plan or model_transcription,
            "generate_improvement_blueprint": (
                model_improvement_blueprint or model_transcription
            ),
            "parse_question_paper": model_question_paper_parse or model_transcription,
            "propose_answer_key": model_answer_key_proposal or model_transcription,
            "propose_rubric": model_rubric_proposal or model_transcription,
            "suggest_curriculum_mapping": (
                model_curriculum_mapping_proposal or model_transcription
            ),
        }
        self._timeout = timeout_seconds
        self._caller = caller
        self._max_attempts = max(1, max_attempts)
        self._backoff_seconds = backoff_seconds or _DEFAULT_BACKOFF_SECONDS

    def execution_metadata(self, operation: str) -> AIExecutionMetadata:
        model = self._models.get(operation) or next(iter(self._models.values()))
        return openai_execution_metadata(operation=operation, model=model)

    def _require(self) -> None:
        if not self._api_key and self._caller is None:
            raise ProviderUnavailable("OPENAI_API_KEY is not configured")

    async def _call_with_retry(
        self, operation: str, invoke: Callable[[], Awaitable[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Retry transient failures; never invent marks on exhaustion.

        Terminal failures raise ``ProviderUnavailable`` (or the original non-
        transient error) so callers route to REVIEW_REQUIRED / unavailable
        states instead of fabricating scores.
        """
        last_exc: BaseException | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await invoke()
            except ProviderUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001 — classify then re-raise
                last_exc = exc
                if not is_transient_openai_failure(exc) or attempt >= self._max_attempts:
                    break
                delay = self._backoff_seconds[
                    min(attempt - 1, len(self._backoff_seconds) - 1)
                ]
                logger.warning(
                    "openai_transient_retry operation=%s attempt=%s/%s delay=%s error=%s",
                    operation,
                    attempt,
                    self._max_attempts,
                    delay,
                    type(exc).__name__,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        if is_transient_openai_failure(last_exc):
            raise ProviderUnavailable(
                f"OpenAI transient failure after {self._max_attempts} attempts "
                f"for {operation}: {type(last_exc).__name__}"
            ) from last_exc
        raise last_exc

    async def _complete(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require()
        if self._caller is not None:

            async def _via_caller() -> dict[str, Any]:
                assert self._caller is not None
                return await self._caller(operation, payload)

            return await self._call_with_retry(operation, _via_caller)

        async def _invoke() -> dict[str, Any]:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover
                raise ProviderUnavailable("openai SDK is not installed") from exc
            client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout)
            model = self._models[operation]
            response = await client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": f"Return JSON only for EduVijna {operation}.",
                    },
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )
            content = response.choices[0].message.content or "{}"
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError("OpenAI response was not valid JSON") from exc
            if not isinstance(data, dict):
                raise ValueError("OpenAI response must be a JSON object")
            return data

        return await self._call_with_retry(operation, _invoke)

    async def extract_student_identity(
        self, request: IdentityExtractionInput
    ) -> IdentityExtractionResult:
        raw = await self._complete("identity", request.model_dump(mode="json"))
        return IdentityExtractionResult.model_validate(raw)

    async def analyze_page(self, request: PageAnalysisInput) -> PageAnalysisResult:
        raw = await self._complete("page_analysis", request.model_dump(mode="json"))
        return PageAnalysisResult.model_validate(raw)

    async def map_answer_regions(
        self, request: RegionMappingInput
    ) -> RegionMappingResult:
        raw = await self._complete("mapping", request.model_dump(mode="json"))
        return RegionMappingResult.model_validate(raw)

    async def transcribe_answer(
        self, request: TranscriptionInput
    ) -> TranscriptionResult:
        raw = await self._complete("transcription", request.model_dump(mode="json"))
        segments = raw.get("segments")
        if isinstance(segments, list):
            normalized: list[Any] = []
            for seg in segments:
                if isinstance(seg, str):
                    normalized.append({"kind": "TEXT", "text": seg})
                elif isinstance(seg, dict):
                    normalized.append(seg)
            raw = {**raw, "segments": normalized}
        return TranscriptionResult.model_validate(raw)

    async def evaluate_rubric(
        self, request: RubricEvaluationInput
    ) -> RubricEvaluationResult:
        raw = await self._complete("evaluate_rubric", request.model_dump(mode="json"))
        return RubricEvaluationResult.model_validate(raw)

    async def classify_error(
        self, request: ErrorClassificationInput
    ) -> ErrorClassificationResult:
        raw = await self._complete("classify_error", request.model_dump(mode="json"))
        return ErrorClassificationResult.model_validate(raw)

    async def generate_student_explanation(
        self, request: StudentNarrativeInput
    ) -> StudentNarrativeResult:
        raw = await self._complete(
            "generate_student_explanation", request.model_dump(mode="json")
        )
        return StudentNarrativeResult.model_validate(raw)

    async def generate_parent_summary(
        self, request: ParentNarrativeInput
    ) -> ParentNarrativeResult:
        raw = await self._complete(
            "generate_parent_summary", request.model_dump(mode="json")
        )
        return ParentNarrativeResult.model_validate(raw)

    async def generate_learning_plan(
        self, request: LearningPlanAIInput
    ) -> LearningPlanAIResult:
        raw = await self._complete(
            "generate_learning_plan", request.model_dump(mode="json")
        )
        return LearningPlanAIResult.model_validate(raw)

    async def generate_improvement_blueprint(
        self, request: ImprovementBlueprintAIInput
    ) -> ImprovementBlueprintAIResult:
        raw = await self._complete(
            "generate_improvement_blueprint", request.model_dump(mode="json")
        )
        return ImprovementBlueprintAIResult.model_validate(raw)

    async def _complete_multimodal(
        self, operation: str, *, text_payload: dict[str, Any], image_pngs: list[bytes]
    ) -> dict[str, Any]:
        """Send text + optional transient image evidence (never logged as base64)."""
        self._require()
        if self._caller is not None:
            # Tests/mocks receive page text + image byte sizes, not raw base64.
            caller_payload = {
                **text_payload,
                "visual_page_count": len(image_pngs),
                "visual_image_bytes": [len(b) for b in image_pngs],
            }

            async def _via_caller() -> dict[str, Any]:
                assert self._caller is not None
                return await self._caller(operation, caller_payload)

            return await self._call_with_retry(operation, _via_caller)

        async def _invoke() -> dict[str, Any]:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover
                raise ProviderUnavailable("openai SDK is not installed") from exc
            import base64

            client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout)
            model = self._models[operation]
            user_content: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": (
                        "Parse this question paper into JSON matching "
                        "QuestionPaperParseResult. "
                        f"Evidence summary: {json.dumps(text_payload)}"
                    ),
                }
            ]
            for png in image_pngs[:20]:
                b64 = base64.standard_b64encode(png).decode("ascii")
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
            response = await client.chat.completions.create(  # type: ignore[call-overload]
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": f"Return JSON only for EduVijna {operation}.",
                    },
                    {"role": "user", "content": user_content},
                ],
            )
            content = response.choices[0].message.content or "{}"
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError("OpenAI response was not valid JSON") from exc
            if not isinstance(data, dict):
                raise ValueError("OpenAI response must be a JSON object")
            return data

        return await self._call_with_retry(operation, _invoke)

    async def parse_question_paper(
        self, request: QuestionPaperParseInput
    ) -> QuestionPaperParseResult:
        text_payload = request.provider_payload()
        images = [
            page.rendered_image_png
            for page in request.evidence_pages
            if page.rendered_image_png
        ]
        if images:
            raw = await self._complete_multimodal(
                "parse_question_paper", text_payload=text_payload, image_pngs=images
            )
        else:
            raw = await self._complete("parse_question_paper", text_payload)
        return QuestionPaperParseResult.model_validate(raw)

    async def propose_answer_key(
        self, request: AnswerKeyProposalInput
    ) -> AnswerKeyProposalResult:
        raw = await self._complete(
            "propose_answer_key", request.model_dump(mode="json")
        )
        return AnswerKeyProposalResult.model_validate(raw)

    async def propose_rubric(
        self, request: RubricProposalInput
    ) -> RubricProposalResult:
        raw = await self._complete("propose_rubric", request.model_dump(mode="json"))
        return RubricProposalResult.model_validate(raw)

    async def suggest_curriculum_mapping(
        self, request: CurriculumMappingProposalInput
    ) -> CurriculumMappingProposalResult:
        raw = await self._complete(
            "suggest_curriculum_mapping", request.model_dump(mode="json")
        )
        return CurriculumMappingProposalResult.model_validate(raw)


# Alias for clarity in evaluation-focused call sites / tests.
OpenAIEvaluationProvider = OpenAIStructureProvider
OpenAINarrativeProvider = OpenAIStructureProvider
OpenAILearningProvider = OpenAIStructureProvider
OpenAIAuthoringProvider = OpenAIStructureProvider
