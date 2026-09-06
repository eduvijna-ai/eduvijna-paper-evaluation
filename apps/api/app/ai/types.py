"""B5 typed AI structure contracts."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _conf(v: Decimal) -> Decimal:
    if v < 0 or v > 1:
        raise ValueError("confidence must be between 0 and 1")
    return v


class NormalizedBBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _bounds(self) -> NormalizedBBox:
        if self.x + self.width > 1 + 1e-9 or self.y + self.height > 1 + 1e-9:
            raise ValueError("bbox must stay within the normalized page")
        return self


class IdentityExtractionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: uuid.UUID
    page_id: uuid.UUID
    roster_hints: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    assessment_code: str | None = Field(default=None, max_length=100)


class IdentityExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extracted_name: str | None = Field(default=None, max_length=255)
    extracted_roll: str | None = Field(default=None, max_length=64)
    extracted_class: str | None = Field(default=None, max_length=64)
    candidate_student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    identity_confidence: Decimal
    raw_fields: dict[str, str] = Field(default_factory=dict, max_length=20)

    @field_validator("identity_confidence")
    @classmethod
    def _c(cls, v: Decimal) -> Decimal:
        return _conf(v)


class ProposedZone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(max_length=255)
    region_type: Literal["ANSWER", "SCRATCH", "DIAGRAM", "IDENTITY"]
    bbox: NormalizedBBox
    confidence: Decimal
    is_continuation: bool = False

    @field_validator("confidence")
    @classmethod
    def _c(cls, v: Decimal) -> Decimal:
        return _conf(v)


class PageAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: uuid.UUID
    page_id: uuid.UUID
    page_index: int = Field(ge=0)
    question_labels: list[str] = Field(default_factory=list, max_length=100)


class PageAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_zones: list[ProposedZone] = Field(default_factory=list, max_length=50)
    printed_labels: list[str] = Field(default_factory=list, max_length=50)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=20)


class ProposedMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version_id: uuid.UUID
    region_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    mapping_confidence: Decimal

    @field_validator("mapping_confidence")
    @classmethod
    def _c(cls, v: Decimal) -> Decimal:
        return _conf(v)


class RegionMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: uuid.UUID
    assessment_version_id: uuid.UUID
    question_version_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    region_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class RegionMappingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mappings: list[ProposedMapping] = Field(default_factory=list, max_length=200)
    mapping_confidence: Decimal
    unmapped_region_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)

    @field_validator("mapping_confidence")
    @classmethod
    def _c(cls, v: Decimal) -> Decimal:
        return _conf(v)


class TranscriptionSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=2000)
    start: float | None = None
    end: float | None = None


class TranscriptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: uuid.UUID
    answer_region_id: uuid.UUID
    question_label: str | None = Field(default=None, max_length=100)
    question_type: str | None = Field(default=None, max_length=64)
    crop_content_sha256: str = Field(min_length=64, max_length=64)


class TranscriptionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(default="", max_length=20_000)
    latex: str | None = Field(default=None, max_length=20_000)
    segments: list[TranscriptionSegment] = Field(default_factory=list, max_length=50)
    transcription_confidence: Decimal
    unreadable: bool = False

    @field_validator("transcription_confidence")
    @classmethod
    def _c(cls, v: Decimal) -> Decimal:
        return _conf(v)


class ProviderUnavailable(RuntimeError):
    """Configured provider cannot serve the operation."""


# --- B6 evaluation contracts -------------------------------------------------

ACADEMIC_ERROR_CODES: frozenset[str] = frozenset(
    {
        "CONCEPT",
        "FORMULA",
        "METHOD",
        "CALCULATION",
        "ALGEBRA",
        "SIGN",
        "SUBSTITUTION",
        "NOTATION",
        "UNIT",
        "DIAGRAM",
        "INTERPRETATION",
        "INCOMPLETE",
        "LOGIC_REASONING",
        "PRESENTATION",
        "FINAL_ANSWER",
    }
)

SYSTEM_ERROR_CODES: frozenset[str] = frozenset(
    {
        "UNREADABLE",
        "OCR_TRANSCRIPTION",
        "QUESTION_MAPPING",
        "IDENTITY_MAPPING",
        "VALID_ALTERNATIVE",
        "RUBRIC_AMBIGUITY",
        "OTHER_REVIEW_REQUIRED",
    }
)

ALL_ERROR_CODES: frozenset[str] = ACADEMIC_ERROR_CODES | SYSTEM_ERROR_CODES

REVIEW_BLOCKING_ERROR_CODES: frozenset[str] = frozenset(
    {
        "UNREADABLE",
        "OCR_TRANSCRIPTION",
        "QUESTION_MAPPING",
        "IDENTITY_MAPPING",
        "RUBRIC_AMBIGUITY",
        "OTHER_REVIEW_REQUIRED",
    }
)

CriterionDecision = Literal[
    "AWARDED", "PARTIAL", "DEDUCTED", "NOT_APPLICABLE", "UNREADABLE"
]


class RubricCriterionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    code: str = Field(max_length=100)
    label: str = Field(max_length=255)
    max_marks: Decimal
    sequence: int = Field(ge=0)
    scoring_mode: Literal["ADDITIVE", "DEDUCTIVE", "ALL_OR_NOTHING"] = "ADDITIVE"
    partial_credit_allowed: bool = False
    ecf_policy: Literal["NONE", "ALLOW_METHOD_CREDIT", "CUSTOM_REVIEW"] = "NONE"
    unit_requirement: str | None = Field(default=None, max_length=2000)
    precision_requirement: str | None = Field(default=None, max_length=2000)
    accepted_equivalents: list[str] = Field(default_factory=list, max_length=50)


class RubricEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version_id: uuid.UUID
    assessment_version_id: uuid.UUID
    rubric_criteria: list[RubricCriterionSnapshot] = Field(min_length=1, max_length=100)
    answer_key_text: str = Field(default="", max_length=50_000)
    structured_answer: dict[str, Any] | None = None
    transcription_text: str = Field(default="", max_length=50_000)
    blank_flag: bool = False
    unreadable_flag: bool = False
    math_verification_summary: dict[str, Any] | None = None
    max_mark: Decimal = Field(ge=0)


class CriterionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_criterion_id: uuid.UUID
    decision: CriterionDecision
    proposed_marks: Decimal | None = None
    error_code: str | None = Field(default=None, max_length=64)
    deduction_reason: str | None = Field(default=None, max_length=1000)
    step_index: int | None = Field(default=None, ge=0)
    ecf_source_criterion_id: uuid.UUID | None = None

    @field_validator("error_code")
    @classmethod
    def _error_code(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ALL_ERROR_CODES:
            raise ValueError(f"unknown error_code: {v}")
        return v


class RubricEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_proposals: list[CriterionProposal] = Field(min_length=1, max_length=100)
    proposed_total: Decimal | None = None
    evaluation_confidence: Decimal | None = None
    first_divergence_step: int | None = Field(default=None, ge=0)
    alternative_method_id: str | None = Field(default=None, max_length=100)
    alternative_method_label: str | None = Field(default=None, max_length=255)
    ecf_applied: bool = False
    error_codes: list[str] = Field(default_factory=list, max_length=50)
    deduction_reasons: list[dict[str, Any]] = Field(default_factory=list, max_length=50)

    @field_validator("evaluation_confidence")
    @classmethod
    def _c(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return v
        return _conf(v)

    @field_validator("error_codes")
    @classmethod
    def _codes(cls, v: list[str]) -> list[str]:
        for code in v:
            if code not in ALL_ERROR_CODES:
                raise ValueError(f"unknown error_code: {code}")
        return v


class ErrorClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version_id: uuid.UUID
    transcription_text: str = Field(default="", max_length=50_000)
    criterion_code: str | None = Field(default=None, max_length=100)
    criterion_label: str | None = Field(default=None, max_length=255)
    first_divergence_step: int | None = Field(default=None, ge=0)
    math_verification_summary: dict[str, Any] | None = None


class ErrorClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_codes: list[str] = Field(default_factory=list, max_length=20)
    evidence_spans: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    classification_confidence: Decimal | None = None

    @field_validator("error_codes")
    @classmethod
    def _codes(cls, v: list[str]) -> list[str]:
        for code in v:
            if code not in ALL_ERROR_CODES:
                raise ValueError(f"unknown error_code: {code}")
        return v

    @field_validator("classification_confidence")
    @classmethod
    def _c(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return v
        return _conf(v)


class MathVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equivalent: bool | None = None
    normalized_student: str | None = Field(default=None, max_length=2000)
    normalized_expected: str | None = Field(default=None, max_length=2000)
    math_verification_confidence: Decimal | None = None
    failure_reason: str | None = Field(default=None, max_length=500)

    @field_validator("math_verification_confidence")
    @classmethod
    def _c(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return v
        return _conf(v)


def dump_bounded(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
