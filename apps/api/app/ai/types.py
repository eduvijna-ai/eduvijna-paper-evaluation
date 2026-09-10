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


TranscriptionSegmentKind = Literal["TEXT", "MATH", "TABLE", "DIAGRAM"]

MAX_TABLE_ROWS = 40
MAX_TABLE_COLS = 20
MAX_TABLE_CELL_LENGTH = 500


class TranscriptionTable(BaseModel):
    """Rectangular table payload for TABLE transcription segments (PEV-013)."""

    model_config = ConfigDict(extra="forbid")

    rows: list[list[str]] = Field(min_length=1, max_length=MAX_TABLE_ROWS)

    @model_validator(mode="after")
    def _rectangular_and_bounds(self) -> TranscriptionTable:
        ncols = len(self.rows[0])
        if ncols < 1 or ncols > MAX_TABLE_COLS:
            raise ValueError(
                f"table must have between 1 and {MAX_TABLE_COLS} columns"
            )
        for row in self.rows:
            if len(row) != ncols:
                raise ValueError("table must be rectangular")
            for cell in row:
                if len(cell) > MAX_TABLE_CELL_LENGTH:
                    raise ValueError(
                        f"table cell exceeds max length {MAX_TABLE_CELL_LENGTH}"
                    )
        return self


class TranscriptionSegment(BaseModel):
    """Structured work segment. Legacy `{text: ...}` remains valid (kind defaults TEXT)."""

    model_config = ConfigDict(extra="forbid")

    kind: TranscriptionSegmentKind = "TEXT"
    step_index: int | None = Field(default=None, ge=0)
    text: str | None = Field(default=None, max_length=2000)
    latex: str | None = Field(default=None, max_length=5000)
    table: TranscriptionTable | None = None
    diagram_description: str | None = Field(default=None, max_length=5000)
    confidence: Decimal | None = None
    start: float | None = None
    end: float | None = None

    @field_validator("confidence")
    @classmethod
    def _segment_confidence(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return v
        return _conf(v)

    @model_validator(mode="after")
    def _kind_payload(self) -> TranscriptionSegment:
        if self.kind == "TEXT":
            if self.text is None:
                raise ValueError("TEXT segment requires text")
        elif self.kind == "MATH":
            if self.latex is None and (self.text is None or self.text == ""):
                raise ValueError("MATH segment requires latex or text")
        elif self.kind == "TABLE":
            if self.table is None:
                raise ValueError("TABLE segment requires table")
        elif self.kind == "DIAGRAM":
            if not self.diagram_description:
                raise ValueError("DIAGRAM segment requires diagram_description")
        return self


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


# --- B7 narrative contracts (prose only — no numeric marks in provider output) ---


class StudentNarrativeQuestionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_code: str = Field(max_length=100)
    feedback: str | None = Field(default=None, max_length=5000)
    error_explanations: list[str] = Field(default_factory=list, max_length=20)
    performance_band: Literal["full", "partial", "none"] = "partial"


class StudentNarrativeInput(BaseModel):
    """Approved ledger context for student narrative. Scores are NOT included."""

    model_config = ConfigDict(extra="forbid")

    assessment_title: str = Field(max_length=255)
    student_display_name: str = Field(max_length=255)
    questions: list[StudentNarrativeQuestionContext] = Field(
        default_factory=list, max_length=100
    )


class StudentNarrativeQuestionProse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_code: str = Field(max_length=100)
    explanation: str | None = Field(default=None, max_length=5000)
    corrected_approach: str | None = Field(default=None, max_length=5000)


class StudentNarrativeResult(BaseModel):
    """Prose-only student narrative. Must not contain numeric marks."""

    model_config = ConfigDict(extra="forbid")

    strengths: list[str] = Field(default_factory=list, max_length=20)
    areas_for_improvement: list[str] = Field(default_factory=list, max_length=20)
    next_steps: list[str] = Field(default_factory=list, max_length=20)
    question_narratives: list[StudentNarrativeQuestionProse] = Field(
        default_factory=list, max_length=100
    )


class ParentNarrativeInput(BaseModel):
    """Approved ledger context for parent narrative. Scores are NOT included."""

    model_config = ConfigDict(extra="forbid")

    assessment_title: str = Field(max_length=255)
    student_display_name: str = Field(max_length=255)
    question_summaries: list[str] = Field(default_factory=list, max_length=50)
    performance_overview: Literal["strong", "mixed", "needs_practice"] = "mixed"


class ParentNarrativeResult(BaseModel):
    """Prose-only parent narrative. Must not contain numeric marks."""

    model_config = ConfigDict(extra="forbid")

    what_went_well: list[str] = Field(default_factory=list, max_length=20)
    what_to_practice: list[str] = Field(default_factory=list, max_length=20)
    how_family_can_help: list[str] = Field(default_factory=list, max_length=20)
    next_step: str = Field(default="", max_length=2000)
    score_summary: str | None = Field(default=None, max_length=2000)


# --- B9 learning / improvement blueprint (bounded prose; server owns structure) ---


class LearningPlanRecommendationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_key: str = Field(max_length=200)
    target_node_id: uuid.UUID
    target_node_code: str = Field(max_length=100)
    target_node_title: str = Field(max_length=255)
    recommendation_kind: Literal[
        "PREREQUISITE_REPAIR",
        "TARGET_CONCEPT",
        "PROCEDURE_PRACTICE",
        "EXECUTION_PRACTICE",
    ]
    priority: Literal[1, 2, 3]
    concept_signal: Literal["STRONG", "WEAK", "INCONCLUSIVE"]
    execution_signal: Literal["STRONG", "WEAK", "INCONCLUSIVE"]
    procedure_signal: Literal["STRONG", "WEAK", "INCONCLUSIVE"]
    default_rationale: str = Field(max_length=2000)


class LearningPlanPathStepContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_key: str = Field(max_length=200)
    curriculum_node_id: uuid.UUID
    kind: Literal[
        "PREREQUISITE", "LEARN", "GUIDED", "INDEPENDENT", "MASTERY_CHECK"
    ]
    title: str = Field(max_length=255)
    default_description: str = Field(max_length=2000)


class LearningPlanAIInput(BaseModel):
    """Server-authorized recommendation/path facts for bounded wording only."""

    model_config = ConfigDict(extra="forbid")

    student_display_name: str = Field(max_length=255)
    curriculum_name: str = Field(max_length=255)
    recommendations: list[LearningPlanRecommendationContext] = Field(
        default_factory=list, max_length=50
    )
    path_steps: list[LearningPlanPathStepContext] = Field(
        default_factory=list, max_length=100
    )


class LearningPlanRecommendationProse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_key: str = Field(max_length=200)
    rationale: str = Field(max_length=2000)


class LearningPlanPathStepProse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_key: str = Field(max_length=200)
    description: str = Field(max_length=2000)


class LearningPlanAIResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_prose: list[LearningPlanRecommendationProse] = Field(
        default_factory=list, max_length=50
    )
    path_step_prose: list[LearningPlanPathStepProse] = Field(
        default_factory=list, max_length=100
    )


class ImprovementBlueprintItemContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_key: str = Field(max_length=200)
    learning_recommendation_id: uuid.UUID
    curriculum_node_id: uuid.UUID
    node_code: str = Field(max_length=100)
    node_title: str = Field(max_length=255)
    recommendation_kind: Literal[
        "PREREQUISITE_REPAIR",
        "TARGET_CONCEPT",
        "PROCEDURE_PRACTICE",
        "EXECUTION_PRACTICE",
    ]
    priority: Literal[1, 2, 3]
    template_kind: Literal[
        "CONCEPT_CHECK",
        "PREREQUISITE_CHECK",
        "PROCEDURE_PRACTICE",
        "EXECUTION_PRACTICE",
        "TRANSFER_CHECK",
    ]
    question_template_ref: str = Field(max_length=255)
    default_focus: str = Field(max_length=2000)
    difficulty: Literal["EASY", "MEDIUM", "HARD"] = "MEDIUM"


class ImprovementBlueprintAIInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_display_name: str = Field(max_length=255)
    curriculum_name: str = Field(max_length=255)
    title: str = Field(max_length=255)
    items: list[ImprovementBlueprintItemContext] = Field(
        default_factory=list, max_length=40
    )


class ImprovementBlueprintItemProse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_key: str = Field(max_length=200)
    focus: str = Field(max_length=2000)


class ImprovementBlueprintAIResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    item_prose: list[ImprovementBlueprintItemProse] = Field(
        default_factory=list, max_length=40
    )


# --- B10 authoring AI contracts (bounded trees / proposals) ---

MAX_AUTHORING_TREE_DEPTH = 6
MAX_AUTHORING_TREE_NODES = 200
MAX_AUTHORING_PROMPT_LEN = 10_000
MAX_AUTHORING_ANSWER_LEN = 20_000
MAX_AUTHORING_CRITERIA = 40
MAX_AUTHORING_MAPPINGS = 20


class ProposedQuestionNode(BaseModel):
    """Nested question proposal node. Children encode hierarchy (no parent id cycles)."""

    model_config = ConfigDict(extra="forbid")

    stable_code: str = Field(min_length=1, max_length=100)
    display_label: str = Field(min_length=1, max_length=100)
    sequence: int = Field(ge=0, le=10_000)
    prompt_text: str = Field(min_length=1, max_length=MAX_AUTHORING_PROMPT_LEN)
    max_marks: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    question_type: str = Field(min_length=1, max_length=64)
    scoring_mode: Literal["LEAF_SCORABLE", "CONTAINER_DERIVED"]
    instructions: str | None = Field(default=None, max_length=5000)
    children: list[ProposedQuestionNode] = Field(
        default_factory=list, max_length=MAX_AUTHORING_TREE_NODES
    )


class QuestionPaperEvidencePage(BaseModel):
    """One page of immutable paper evidence for authoring parse (B11).

    ``rendered_image_png`` is ephemeral provider input only — excluded from
    default JSON dumps used in traces / proposals.
    """

    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=0, le=500)
    extracted_text: str | None = Field(default=None, max_length=50_000)
    rendered_image_png: bytes | None = Field(default=None, repr=False)
    width: int | None = Field(default=None, ge=1, le=20_000)
    height: int | None = Field(default=None, ge=1, le=20_000)
    has_visual_evidence: bool = False


class QuestionPaperParseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: uuid.UUID
    assessment_version_id: uuid.UUID
    assessment_title: str = Field(max_length=255)
    max_marks: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    assessment_artifact_id: uuid.UUID
    content_sha256: str = Field(min_length=64, max_length=64)
    mime_type: str = Field(min_length=1, max_length=128)
    original_filename: str = Field(min_length=1, max_length=512)
    evidence_pages: list[QuestionPaperEvidencePage] = Field(min_length=1, max_length=100)

    def provider_payload(self) -> dict[str, Any]:
        """JSON-safe payload for providers (no raw image bytes)."""
        return {
            "assessment_id": str(self.assessment_id),
            "assessment_version_id": str(self.assessment_version_id),
            "assessment_title": self.assessment_title,
            "max_marks": str(self.max_marks),
            "assessment_artifact_id": str(self.assessment_artifact_id),
            "content_sha256": self.content_sha256,
            "mime_type": self.mime_type,
            "original_filename": self.original_filename,
            "pages": [
                {
                    "page_index": page.page_index,
                    "extracted_text": page.extracted_text,
                    "has_visual_evidence": page.has_visual_evidence,
                    "width": page.width,
                    "height": page.height,
                    "image_byte_size": (
                        len(page.rendered_image_png) if page.rendered_image_png else 0
                    ),
                }
                for page in self.evidence_pages
            ],
        }


class QuestionPaperParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roots: list[ProposedQuestionNode] = Field(
        min_length=1, max_length=MAX_AUTHORING_TREE_NODES
    )
    notes: str | None = Field(default=None, max_length=2000)


class AnswerKeyProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: uuid.UUID
    question_version_id: uuid.UUID
    stable_code: str = Field(max_length=100)
    display_label: str = Field(max_length=100)
    prompt_text: str = Field(max_length=MAX_AUTHORING_PROMPT_LEN)
    max_marks: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    question_type: str = Field(max_length=64)
    instructions: str | None = Field(default=None, max_length=500)


class AnswerKeyProposalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_text: str = Field(min_length=1, max_length=MAX_AUTHORING_ANSWER_LEN)
    structured_answer: dict[str, Any] | None = None


class ProposedRubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    max_marks: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    sequence: int = Field(ge=0, le=10_000)
    scoring_mode: Literal["ADDITIVE", "DEDUCTIVE", "ALL_OR_NOTHING"] = "ADDITIVE"
    partial_credit_allowed: bool = False
    ecf_policy: Literal["NONE", "ALLOW_METHOD_CREDIT", "CUSTOM_REVIEW"] = "NONE"
    accepted_equivalents: list[str] = Field(default_factory=list, max_length=50)


class RubricProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_version_id: uuid.UUID
    question_version_id: uuid.UUID
    stable_code: str = Field(max_length=100)
    display_label: str = Field(max_length=100)
    prompt_text: str = Field(max_length=MAX_AUTHORING_PROMPT_LEN)
    max_marks: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    question_type: str = Field(max_length=64)
    answer_text: str | None = Field(default=None, max_length=MAX_AUTHORING_ANSWER_LEN)
    instructions: str | None = Field(default=None, max_length=500)


class RubricProposalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    criteria: list[ProposedRubricCriterion] = Field(
        min_length=1, max_length=MAX_AUTHORING_CRITERIA
    )


class CurriculumNodeHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_node_id: uuid.UUID
    code: str = Field(max_length=100)
    name: str = Field(max_length=255)
    node_type: str = Field(max_length=64)


class CurriculumMappingProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_version_id: uuid.UUID
    curriculum_id: uuid.UUID
    prompt_text: str = Field(max_length=MAX_AUTHORING_PROMPT_LEN)
    stable_code: str = Field(max_length=100)
    candidate_nodes: list[CurriculumNodeHint] = Field(
        default_factory=list, max_length=100
    )
    instructions: str | None = Field(default=None, max_length=500)


class ProposedCurriculumMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_node_id: uuid.UUID
    mapping_type: Literal["PRIMARY", "SECONDARY", "LEARNING_OUTCOME", "SKILL"]
    weight: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    rationale: str | None = Field(default=None, max_length=2000)


class CurriculumMappingProposalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mappings: list[ProposedCurriculumMapping] = Field(
        default_factory=list, max_length=MAX_AUTHORING_MAPPINGS
    )


# --- B18 embedding contracts -------------------------------------------------


class EmbeddingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texts: list[str] = Field(min_length=1, max_length=500)


class EmbeddingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vectors: list[list[float]] = Field(min_length=1, max_length=500)
    provider: str = Field(max_length=64)
    model: str = Field(max_length=128)
    model_version: str = Field(max_length=64)
    embedding_dim: int = Field(ge=1, le=4096)


def dump_bounded(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
