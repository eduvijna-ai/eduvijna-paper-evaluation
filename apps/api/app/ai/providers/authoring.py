"""Deterministic authoring AI provider for B10/B11 (no network)."""

from __future__ import annotations

import re
from decimal import Decimal

from app.ai.execution_metadata import (
    FIXED_AUTHORING_META,
    AIExecutionMetadata,
)
from app.ai.types import (
    AnswerKeyProposalInput,
    AnswerKeyProposalResult,
    CurriculumMappingProposalInput,
    CurriculumMappingProposalResult,
    ProposedCurriculumMapping,
    ProposedQuestionNode,
    ProposedRubricCriterion,
    QuestionPaperParseInput,
    QuestionPaperParseResult,
    RubricProposalInput,
    RubricProposalResult,
)

# Synthetic CVB fixture pattern, e.g. "1(a) Solve 2x + 3 = 7. [10 marks]"
_LEAF_PATTERN = re.compile(
    r"(?P<label>(?:Q?\s*)?(?P<num>\d+)\s*\(\s*(?P<sub>[a-zA-Z])\s*\))\s*"
    r"(?P<prompt>.+?)\s*\[\s*(?P<marks>\d+(?:\.\d+)?)\s*marks?\s*\]",
    re.IGNORECASE | re.DOTALL,
)


class FixedAuthoringProvider:
    """Evidence-dependent parse + deterministic answer/rubric proposals."""

    provider_name = "fixed"

    def __init__(self, *, allow_non_test: bool = False) -> None:
        self._allow_non_test = allow_non_test

    def execution_metadata(self, operation: str) -> AIExecutionMetadata:
        return AIExecutionMetadata(
            provider=FIXED_AUTHORING_META.provider,
            model=FIXED_AUTHORING_META.model,
            model_version=FIXED_AUTHORING_META.model_version,
            prompt_template_version=f"fixed-authoring-{operation}-v1",
        )

    async def parse_question_paper(
        self, request: QuestionPaperParseInput
    ) -> QuestionPaperParseResult:
        text_parts = [
            (page.extracted_text or "").strip()
            for page in request.evidence_pages
            if (page.extracted_text or "").strip()
        ]
        combined = "\n".join(text_parts).strip()
        if not combined:
            raise ValueError(
                "fixed authoring parse requires extracted text evidence from the uploaded paper"
            )

        marks = Decimal(request.max_marks).quantize(Decimal("0.01"))
        match = _LEAF_PATTERN.search(combined)
        if match:
            prompt = " ".join(match.group("prompt").split()).strip()
            label_num = match.group("num")
            label_sub = match.group("sub").lower()
            display_label = f"{label_num}({label_sub})"
            stable_leaf = f"Q{label_num}{label_sub}"
            stable_root = f"Q{label_num}"
            parsed_marks = Decimal(match.group("marks")).quantize(Decimal("0.01"))
            # Prefer assessment max when fixture marks match; otherwise keep fixture marks
            # so evidence dependency is visible while still allowing reconciliation tests.
            leaf_marks = parsed_marks if parsed_marks == marks else marks
        else:
            # Still evidence-dependent: first non-empty line becomes the leaf prompt.
            first_line = next(
                (ln.strip() for ln in combined.splitlines() if ln.strip()),
                combined[:200],
            )
            prompt = first_line[:2000]
            display_label = "1(a)"
            stable_leaf = "Q1a"
            stable_root = "Q1"
            leaf_marks = marks

        leaf = ProposedQuestionNode(
            stable_code=stable_leaf,
            display_label=display_label,
            sequence=1,
            prompt_text=prompt,
            max_marks=leaf_marks,
            question_type="STRUCTURED",
            scoring_mode="LEAF_SCORABLE",
            children=[],
        )
        root = ProposedQuestionNode(
            stable_code=stable_root,
            display_label=stable_root.replace("Q", "", 1) or "1",
            sequence=1,
            prompt_text="Section 1",
            max_marks=leaf_marks,
            question_type="SECTION",
            scoring_mode="CONTAINER_DERIVED",
            children=[leaf],
        )
        return QuestionPaperParseResult(
            roots=[root],
            notes="fixed authoring parse (evidence-derived)",
        )

    async def propose_answer_key(
        self, request: AnswerKeyProposalInput
    ) -> AnswerKeyProposalResult:
        return AnswerKeyProposalResult(
            answer_text=f"Model answer for {request.stable_code}",
            structured_answer={"stable_code": request.stable_code},
        )

    async def propose_rubric(
        self, request: RubricProposalInput
    ) -> RubricProposalResult:
        marks = Decimal(request.max_marks).quantize(Decimal("0.01"))
        return RubricProposalResult(
            title=f"Rubric {request.stable_code}",
            criteria=[
                ProposedRubricCriterion(
                    criterion_code="C1",
                    description=f"Correct response for {request.display_label}",
                    max_marks=marks,
                    sequence=1,
                    scoring_mode="ADDITIVE",
                    partial_credit_allowed=True,
                    ecf_policy="ALLOW_METHOD_CREDIT",
                    accepted_equivalents=[],
                )
            ],
        )

    async def suggest_curriculum_mapping(
        self, request: CurriculumMappingProposalInput
    ) -> CurriculumMappingProposalResult:
        if not request.candidate_nodes:
            return CurriculumMappingProposalResult(mappings=[])
        node = request.candidate_nodes[0]
        return CurriculumMappingProposalResult(
            mappings=[
                ProposedCurriculumMapping(
                    curriculum_node_id=node.curriculum_node_id,
                    mapping_type="PRIMARY",
                    weight=Decimal("1.00"),
                    rationale=f"Primary topic match for {request.stable_code}",
                )
            ]
        )
