"""Structure- and evaluation-stage AI provider protocols (B5/B6)."""

from __future__ import annotations

from typing import Protocol

from app.ai.types import (
    ErrorClassificationInput,
    ErrorClassificationResult,
    IdentityExtractionInput,
    IdentityExtractionResult,
    PageAnalysisInput,
    PageAnalysisResult,
    RegionMappingInput,
    RegionMappingResult,
    RubricEvaluationInput,
    RubricEvaluationResult,
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
