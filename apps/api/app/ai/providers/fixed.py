"""Deterministic fixed structure provider for local/CI (non-production)."""

from __future__ import annotations

from decimal import Decimal

from app.ai.types import (
    IdentityExtractionInput,
    IdentityExtractionResult,
    NormalizedBBox,
    PageAnalysisInput,
    PageAnalysisResult,
    ProposedMapping,
    ProposedZone,
    ProviderUnavailable,
    RegionMappingInput,
    RegionMappingResult,
    TranscriptionInput,
    TranscriptionResult,
    TranscriptionSegment,
)


class FixedStructureProvider:
    provider_name = "fixed"

    def __init__(self, *, allow_non_test: bool = False) -> None:
        self._allow_non_test = allow_non_test

    def _guard(self) -> None:
        if not self._allow_non_test:
            # Registry sets allow_non_test=True only for local/test/ci.
            pass

    async def extract_student_identity(
        self, request: IdentityExtractionInput
    ) -> IdentityExtractionResult:
        self._guard()
        candidates = []
        for hint in request.roster_hints[:5]:
            sid = hint.get("student_id")
            if sid:
                try:
                    import uuid

                    candidates.append(uuid.UUID(sid))
                except ValueError:
                    continue
        return IdentityExtractionResult(
            extracted_name="Fixed Student",
            extracted_roll="FIX-001",
            extracted_class=None,
            candidate_student_ids=candidates[:5],
            identity_confidence=Decimal("0.8200"),
            raw_fields={"provider": "fixed", "page_id": str(request.page_id)},
        )

    async def analyze_page(self, request: PageAnalysisInput) -> PageAnalysisResult:
        self._guard()
        zones = [
            ProposedZone(
                label="Q1 zone" if request.page_index == 0 else f"P{request.page_index + 1} zone",
                region_type="ANSWER",
                bbox=NormalizedBBox(x=0.1, y=0.15, width=0.7, height=0.25),
                confidence=Decimal("0.7500"),
                is_continuation=request.page_index > 0,
            )
        ]
        if request.page_index > 0:
            zones.append(
                ProposedZone(
                    label="Continuation zone",
                    region_type="ANSWER",
                    bbox=NormalizedBBox(x=0.12, y=0.45, width=0.6, height=0.2),
                    confidence=Decimal("0.7000"),
                    is_continuation=True,
                )
            )
        return PageAnalysisResult(
            proposed_zones=zones,
            printed_labels=request.question_labels[:10],
            metadata={"provider": "fixed", "page_index": str(request.page_index)},
        )

    async def map_answer_regions(
        self, request: RegionMappingInput
    ) -> RegionMappingResult:
        self._guard()
        if not request.question_version_ids or not request.region_ids:
            return RegionMappingResult(
                mappings=[],
                mapping_confidence=Decimal("0.0000"),
                unmapped_region_ids=list(request.region_ids),
            )
        primary = request.region_ids[0]
        mappings = [
            ProposedMapping(
                question_version_id=request.question_version_ids[0],
                region_ids=[primary],
                mapping_confidence=Decimal("0.7000"),
            )
        ]
        unmapped = [rid for rid in request.region_ids if rid != primary]
        return RegionMappingResult(
            mappings=mappings,
            mapping_confidence=Decimal("0.7000"),
            unmapped_region_ids=unmapped,
        )

    async def transcribe_answer(
        self, request: TranscriptionInput
    ) -> TranscriptionResult:
        self._guard()
        short = str(request.answer_region_id).replace("-", "")[:8]
        text = f"Fixed transcription for {short}"
        return TranscriptionResult(
            text=text,
            latex=None,
            segments=[TranscriptionSegment(text=text)],
            transcription_confidence=Decimal("0.7700"),
            unreadable=False,
        )


class NoneStructureProvider:
    provider_name = "none"

    async def extract_student_identity(
        self, request: IdentityExtractionInput
    ) -> IdentityExtractionResult:
        raise ProviderUnavailable("AI_PROVIDER_VISION=none")

    async def analyze_page(self, request: PageAnalysisInput) -> PageAnalysisResult:
        raise ProviderUnavailable("AI_PROVIDER_VISION=none")

    async def map_answer_regions(
        self, request: RegionMappingInput
    ) -> RegionMappingResult:
        raise ProviderUnavailable("AI_PROVIDER_VISION=none")

    async def transcribe_answer(
        self, request: TranscriptionInput
    ) -> TranscriptionResult:
        raise ProviderUnavailable("AI_PROVIDER_VISION=none")
