"""Deterministic Maths-IIB UAT fixture (75 effective marks, ANY_N sections)."""

from __future__ import annotations

from decimal import Decimal

from app.ai.types import ProposedQuestionNode, QuestionPaperParseResult

FIXTURE_MARKER = "MATHS_IIB_UAT_FIXTURE"


def build_maths_iib_proposal() -> QuestionPaperParseResult:
    def leaves(
        prefix: str,
        start: int,
        count: int,
        marks: Decimal,
        sequence_offset: int,
    ) -> list[ProposedQuestionNode]:
        return [
            ProposedQuestionNode(
                stable_code=f"{prefix}{num}",
                display_label=str(num),
                sequence=sequence_offset + idx,
                prompt_text=f"Question {num}",
                max_marks=marks,
                question_type="STRUCTURED",
                scoring_mode="LEAF_SCORABLE",
                children=[],
            )
            for idx, num in enumerate(range(start, start + count))
        ]

    section_a_children = leaves("Q", 1, 10, Decimal("2.00"), 1)
    section_b_children = leaves("Q", 11, 7, Decimal("4.00"), 1)
    section_c_children = leaves("Q", 18, 7, Decimal("7.00"), 1)

    roots = [
        ProposedQuestionNode(
            stable_code="SEC_A",
            display_label="Section A",
            sequence=1,
            prompt_text="Answer all questions in Section A",
            max_marks=Decimal("20.00"),
            question_type="SECTION",
            scoring_mode="CONTAINER_DERIVED",
            selection_mode="ALL",
            children=section_a_children,
        ),
        ProposedQuestionNode(
            stable_code="SEC_B",
            display_label="Section B",
            sequence=2,
            prompt_text="Answer any five questions in Section B",
            max_marks=Decimal("20.00"),
            question_type="SECTION",
            scoring_mode="CONTAINER_DERIVED",
            selection_mode="ANY_N",
            selection_count=5,
            children=section_b_children,
        ),
        ProposedQuestionNode(
            stable_code="SEC_C",
            display_label="Section C",
            sequence=3,
            prompt_text="Answer any five questions in Section C",
            max_marks=Decimal("35.00"),
            question_type="SECTION",
            scoring_mode="CONTAINER_DERIVED",
            selection_mode="ANY_N",
            selection_count=5,
            children=section_c_children,
        ),
    ]
    return QuestionPaperParseResult(
        roots=roots,
        notes="fixed Maths-IIB UAT fixture (deterministic ANY_N)",
    )
