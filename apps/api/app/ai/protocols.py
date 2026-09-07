"""Structure-, evaluation-, and narrative-stage AI provider protocols."""

from __future__ import annotations

from typing import Protocol

from app.ai.types import (
    ErrorClassificationInput,
    ErrorClassificationResult,
    IdentityExtractionInput,
    IdentityExtractionResult,
    PageAnalysisInput,
    PageAnalysisResult,
    ParentNarrativeInput,
    ParentNarrativeResult,
    RegionMappingInput,
    RegionMappingResult,
    RubricEvaluationInput,
    RubricEvaluationResult,
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
