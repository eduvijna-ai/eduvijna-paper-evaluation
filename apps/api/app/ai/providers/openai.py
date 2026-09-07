"""Optional OpenAI structure + evaluation provider (no network in CI)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

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

    def _require(self) -> None:
        if not self._api_key and self._caller is None:
            raise ProviderUnavailable("OPENAI_API_KEY is not configured")

    async def _complete(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require()
        if self._caller is not None:
            return await self._caller(operation, payload)
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
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("OpenAI response must be a JSON object")
        return data

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

    async def parse_question_paper(
        self, request: QuestionPaperParseInput
    ) -> QuestionPaperParseResult:
        raw = await self._complete(
            "parse_question_paper", request.model_dump(mode="json")
        )
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
