"""Structure-, evaluation-, narrative-, learning-, and authoring-stage AI protocols."""

from __future__ import annotations

from typing import Protocol

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


class StructureAIProvider(Protocol):
    provider_name: str

    async def extract_student_identity(
        self, request: IdentityExtractionInput
    ) -> IdentityExtractionResult: ...

    async def analyze_page(self, request: PageAnalysisInput) -> PageAnalysisResult: ...

    async def map_answer_regions(
        self, request: RegionMappingInput
    ) -> RegionMappingResult: ...

    async def transcribe_answer(
        self, request: TranscriptionInput
    ) -> TranscriptionResult: ...


class EvaluationAIProvider(Protocol):
    """Rubric evaluation + error taxonomy. Math verification is NOT on the provider."""

    provider_name: str

    async def evaluate_rubric(
        self, request: RubricEvaluationInput
    ) -> RubricEvaluationResult: ...

    async def classify_error(
        self, request: ErrorClassificationInput
    ) -> ErrorClassificationResult: ...


class NarrativeAIProvider(Protocol):
    """Post-approval prose narratives. Must never emit or alter numeric marks."""

    provider_name: str

    async def generate_student_explanation(
        self, request: StudentNarrativeInput
    ) -> StudentNarrativeResult: ...

    async def generate_parent_summary(
        self, request: ParentNarrativeInput
    ) -> ParentNarrativeResult: ...


class LearningAIProvider(Protocol):
    """B9 learning plan / improvement blueprint prose. Structure is server-owned."""

    provider_name: str

    async def generate_learning_plan(
        self, request: LearningPlanAIInput
    ) -> LearningPlanAIResult: ...

    async def generate_improvement_blueprint(
        self, request: ImprovementBlueprintAIInput
    ) -> ImprovementBlueprintAIResult: ...


class AuthoringAIProvider(Protocol):
    """B10 authoring proposals. Server validates / applies; provider never mutates DB."""

    provider_name: str

    async def parse_question_paper(
        self, request: QuestionPaperParseInput
    ) -> QuestionPaperParseResult: ...

    async def propose_answer_key(
        self, request: AnswerKeyProposalInput
    ) -> AnswerKeyProposalResult: ...

    async def propose_rubric(
        self, request: RubricProposalInput
    ) -> RubricProposalResult: ...

    async def suggest_curriculum_mapping(
        self, request: CurriculumMappingProposalInput
    ) -> CurriculumMappingProposalResult: ...
