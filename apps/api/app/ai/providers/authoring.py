"""Deterministic authoring AI provider for B10 (no network)."""

from __future__ import annotations

from decimal import Decimal

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


class FixedAuthoringProvider:
    """Deterministic nested Q1/Q1a tree, answer key, and reconciling rubric criteria."""

    provider_name = "fixed"

    def __init__(self, *, allow_non_test: bool = False) -> None:
        self._allow_non_test = allow_non_test

    async def parse_question_paper(
        self, request: QuestionPaperParseInput
    ) -> QuestionPaperParseResult:
        marks = Decimal(request.max_marks).quantize(Decimal("0.01"))
        leaf = ProposedQuestionNode(
            stable_code="Q1a",
            display_label="1(a)",
            sequence=1,
            prompt_text=f"Answer the question for {request.assessment_title}",
            max_marks=marks,
            question_type="STRUCTURED",
            scoring_mode="LEAF_SCORABLE",
            children=[],
        )
        root = ProposedQuestionNode(
            stable_code="Q1",
            display_label="1",
            sequence=1,
            prompt_text="Section 1",
            max_marks=marks,
            question_type="SECTION",
            scoring_mode="CONTAINER_DERIVED",
            children=[leaf],
        )
        return QuestionPaperParseResult(
            roots=[root],
            notes="fixed authoring parse",
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
