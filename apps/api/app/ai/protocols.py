"""Structure-stage AI provider protocol (B5)."""

from __future__ import annotations

from typing import Protocol

from app.ai.types import (
    IdentityExtractionInput,
    IdentityExtractionResult,
    PageAnalysisInput,
    PageAnalysisResult,
    RegionMappingInput,
    RegionMappingResult,
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
