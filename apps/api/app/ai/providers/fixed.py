"""Deterministic fixed structure + evaluation provider for local/CI (non-production)."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from app.ai.execution_metadata import FIXED_STRUCTURE_META, AIExecutionMetadata
from app.ai.types import (
    CriterionProposal,
    ErrorClassificationInput,
    ErrorClassificationResult,
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
    RubricCriterionSnapshot,
    RubricEvaluationInput,
    RubricEvaluationResult,
    TranscriptionInput,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionTable,
)


def _exercise_tag(request: RubricEvaluationInput) -> str:
    text = (request.transcription_text or "").upper()
    for tag in (
        "UNREADABLE",
        "PARTIAL",
        "DEDUCT",
        "ECF",
        "ALT",
        "FULL",
        "REVIEW",
    ):
        if f"EXERCISE:{tag}" in text:
            return tag
    digest = hashlib.sha256(
        f"{request.question_version_id}:{request.transcription_text}".encode()
    ).hexdigest()
    return ["FULL", "PARTIAL", "DEDUCT", "ECF", "ALT", "REVIEW"][int(digest[:8], 16) % 6]


def _award_all(criteria: list[RubricCriterionSnapshot]) -> list[CriterionProposal]:
    return [
        CriterionProposal(
            rubric_criterion_id=c.id,
            decision="AWARDED",
            proposed_marks=c.max_marks,
            error_code=None,
            deduction_reason=None,
            step_index=c.sequence,
            ecf_source_criterion_id=None,
        )
        for c in criteria
    ]


class FixedStructureProvider:
    """Implements StructureAIProvider and EvaluationAIProvider."""

    provider_name = "fixed"

    def __init__(self, *, allow_non_test: bool = False) -> None:
        self._allow_non_test = allow_non_test

    def execution_metadata(self, operation: str) -> AIExecutionMetadata:
        return AIExecutionMetadata(
            provider=FIXED_STRUCTURE_META.provider,
            model=FIXED_STRUCTURE_META.model,
            model_version=FIXED_STRUCTURE_META.model_version,
            prompt_template_version=f"fixed-structure-{operation}-v1",
        )

    def _guard(self) -> None:
        if not self._allow_non_test:
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
        # Deterministic mixed structure for PEV-013 (TEXT + MATH + TABLE).
        segments = [
            TranscriptionSegment(kind="TEXT", text=text, step_index=0),
            TranscriptionSegment(
                kind="MATH",
                latex=rf"x_{{{short[:2]}}}^2 + 1",
                text=None,
                step_index=1,
                confidence=Decimal("0.8000"),
            ),
            TranscriptionSegment(
                kind="TABLE",
                table=TranscriptionTable(
                    rows=[
                        ["step", "value"],
                        ["1", short[:4]],
                        ["2", short[4:8]],
                    ]
                ),
                step_index=2,
                confidence=Decimal("0.7500"),
            ),
        ]
        return TranscriptionResult(
            text=text,
            latex=rf"x_{{{short[:2]}}}^2 + 1",
            segments=segments,
            transcription_confidence=Decimal("0.7700"),
            unreadable=False,
        )

    async def evaluate_rubric(
        self, request: RubricEvaluationInput
    ) -> RubricEvaluationResult:
        self._guard()
        criteria = sorted(request.rubric_criteria, key=lambda c: c.sequence)
        tag = _exercise_tag(request)

        if request.unreadable_flag or tag == "UNREADABLE":
            proposals = [
                CriterionProposal(
                    rubric_criterion_id=c.id,
                    decision="UNREADABLE",
                    proposed_marks=None,
                    error_code="UNREADABLE",
                    deduction_reason=None,
                    step_index=c.sequence,
                )
                for c in criteria
            ]
            return RubricEvaluationResult(
                criterion_proposals=proposals,
                proposed_total=None,
                evaluation_confidence=None,
                first_divergence_step=None,
                ecf_applied=False,
                error_codes=["UNREADABLE"],
                deduction_reasons=[],
            )

        if tag == "REVIEW":
            proposals = [
                CriterionProposal(
                    rubric_criterion_id=c.id,
                    decision="PARTIAL",
                    proposed_marks=None,
                    error_code="RUBRIC_AMBIGUITY",
                    deduction_reason="Fixed provider review exercise",
                    step_index=c.sequence,
                )
                for c in criteria
            ]
            return RubricEvaluationResult(
                criterion_proposals=proposals,
                proposed_total=None,
                evaluation_confidence=Decimal("0.3000"),
                first_divergence_step=0,
                ecf_applied=False,
                error_codes=["RUBRIC_AMBIGUITY", "OTHER_REVIEW_REQUIRED"],
                deduction_reasons=[],
            )

        if tag == "PARTIAL" and criteria:
            half = (criteria[0].max_marks / 2).quantize(Decimal("0.0001"))
            proposals = [
                CriterionProposal(
                    rubric_criterion_id=criteria[0].id,
                    decision="PARTIAL",
                    proposed_marks=half,
                    error_code="INCOMPLETE",
                    deduction_reason="Fixed partial credit exercise",
                    step_index=criteria[0].sequence,
                )
            ]
            for c in criteria[1:]:
                proposals.append(
                    CriterionProposal(
                        rubric_criterion_id=c.id,
                        decision="AWARDED",
                        proposed_marks=c.max_marks,
                        step_index=c.sequence,
                    )
                )
            total = sum((p.proposed_marks or Decimal("0") for p in proposals), Decimal("0"))
            return RubricEvaluationResult(
                criterion_proposals=proposals,
                proposed_total=total,
                evaluation_confidence=Decimal("0.8000"),
                first_divergence_step=criteria[0].sequence,
                ecf_applied=False,
                error_codes=["INCOMPLETE"],
                deduction_reasons=[
                    {
                        "criterion_id": str(criteria[0].id),
                        "error_code": "INCOMPLETE",
                        "reason": "Fixed partial credit exercise",
                        "marks_deducted": float(criteria[0].max_marks - half),
                    }
                ],
            )

        if tag == "DEDUCT" and criteria:
            proposals = [
                CriterionProposal(
                    rubric_criterion_id=criteria[0].id,
                    decision="DEDUCTED",
                    proposed_marks=Decimal("0"),
                    error_code="CALCULATION",
                    deduction_reason="Fixed deduction exercise",
                    step_index=criteria[0].sequence,
                )
            ]
            for c in criteria[1:]:
                proposals.append(
                    CriterionProposal(
                        rubric_criterion_id=c.id,
                        decision="AWARDED",
                        proposed_marks=c.max_marks,
                        step_index=c.sequence,
                    )
                )
            total = sum((p.proposed_marks or Decimal("0") for p in proposals), Decimal("0"))
            return RubricEvaluationResult(
                criterion_proposals=proposals,
                proposed_total=total,
                evaluation_confidence=Decimal("0.8500"),
                first_divergence_step=criteria[0].sequence,
                ecf_applied=False,
                error_codes=["CALCULATION"],
                deduction_reasons=[
                    {
                        "criterion_id": str(criteria[0].id),
                        "error_code": "CALCULATION",
                        "reason": "Fixed deduction exercise",
                        "marks_deducted": float(criteria[0].max_marks),
                    }
                ],
            )

        if tag == "ECF" and len(criteria) >= 2:
            origin = criteria[0]
            affected = criteria[1]
            if affected.ecf_policy == "NONE":
                # Still deterministic: fall back to partial without claiming ECF.
                return await self.evaluate_rubric(
                    request.model_copy(
                        update={
                            "transcription_text": (request.transcription_text or "")
                            + " EXERCISE:PARTIAL"
                        }
                    )
                )
            half = (origin.max_marks / 2).quantize(Decimal("0.0001"))
            proposals = [
                CriterionProposal(
                    rubric_criterion_id=origin.id,
                    decision="PARTIAL",
                    proposed_marks=half,
                    error_code="SUBSTITUTION",
                    deduction_reason="Fixed ECF origin",
                    step_index=origin.sequence,
                ),
                CriterionProposal(
                    rubric_criterion_id=affected.id,
                    decision="AWARDED",
                    proposed_marks=affected.max_marks,
                    error_code=None,
                    deduction_reason="ECF method credit retained",
                    step_index=affected.sequence,
                    ecf_source_criterion_id=origin.id,
                ),
            ]
            for c in criteria[2:]:
                proposals.append(
                    CriterionProposal(
                        rubric_criterion_id=c.id,
                        decision="AWARDED",
                        proposed_marks=c.max_marks,
                        step_index=c.sequence,
                    )
                )
            total = sum((p.proposed_marks or Decimal("0") for p in proposals), Decimal("0"))
            return RubricEvaluationResult(
                criterion_proposals=proposals,
                proposed_total=total,
                evaluation_confidence=Decimal("0.7800"),
                first_divergence_step=origin.sequence,
                ecf_applied=True,
                error_codes=["SUBSTITUTION"],
                deduction_reasons=[
                    {
                        "criterion_id": str(origin.id),
                        "error_code": "SUBSTITUTION",
                        "reason": "Fixed ECF origin",
                        "marks_deducted": float(origin.max_marks - half),
                    }
                ],
            )

        if tag == "ALT":
            proposals = _award_all(criteria)
            total = sum((p.proposed_marks or Decimal("0") for p in proposals), Decimal("0"))
            return RubricEvaluationResult(
                criterion_proposals=proposals,
                proposed_total=total,
                evaluation_confidence=Decimal("0.8800"),
                first_divergence_step=None,
                alternative_method_id="fixed-alt-1",
                alternative_method_label="Fixed alternative method",
                ecf_applied=False,
                error_codes=["VALID_ALTERNATIVE"],
                deduction_reasons=[],
            )

        # FULL (default)
        proposals = _award_all(criteria)
        total = sum((p.proposed_marks or Decimal("0") for p in proposals), Decimal("0"))
        # Cap at max_mark
        if total > request.max_mark:
            total = request.max_mark
        return RubricEvaluationResult(
            criterion_proposals=proposals,
            proposed_total=total,
            evaluation_confidence=Decimal("0.9100"),
            first_divergence_step=None,
            ecf_applied=False,
            error_codes=[],
            deduction_reasons=[],
        )

    async def classify_error(
        self, request: ErrorClassificationInput
    ) -> ErrorClassificationResult:
        self._guard()
        text = (request.transcription_text or "").upper()
        if "CALCULATION" in text:
            codes = ["CALCULATION"]
        elif "CONCEPT" in text:
            codes = ["CONCEPT"]
        elif "UNREADABLE" in text:
            codes = ["UNREADABLE"]
        else:
            digest = hashlib.sha256(text.encode()).hexdigest()
            codes = [["CALCULATION", "METHOD", "INCOMPLETE"][int(digest[:2], 16) % 3]]
        return ErrorClassificationResult(
            error_codes=codes,
            evidence_spans=[{"start": 0, "end": min(12, len(request.transcription_text or ""))}],
            classification_confidence=Decimal("0.7500"),
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

    async def evaluate_rubric(
        self, request: RubricEvaluationInput
    ) -> RubricEvaluationResult:
        raise ProviderUnavailable("AI_PROVIDER_VISION=none")

    async def classify_error(
        self, request: ErrorClassificationInput
    ) -> ErrorClassificationResult:
        raise ProviderUnavailable("AI_PROVIDER_VISION=none")


# Alias for evaluation-focused call sites / tests.
FixedEvaluationProvider = FixedStructureProvider
