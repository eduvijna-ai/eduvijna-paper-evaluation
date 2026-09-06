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


def dump_bounded(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
