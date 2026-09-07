"""Deterministic and null narrative providers for B7 reports."""

from __future__ import annotations

from app.ai.execution_metadata import FIXED_NARRATIVE_META, AIExecutionMetadata
from app.ai.types import (
    ParentNarrativeInput,
    ParentNarrativeResult,
    ProviderUnavailable,
    StudentNarrativeInput,
    StudentNarrativeQuestionProse,
    StudentNarrativeResult,
)


class FixedNarrativeProvider:
    """Deterministic prose narratives for CI — no network, no numeric marks."""

    provider_name = "fixed"

    def __init__(self, *, allow_non_test: bool = False) -> None:
        self._allow_non_test = allow_non_test

    def execution_metadata(self, operation: str) -> AIExecutionMetadata:
        return AIExecutionMetadata(
            provider=FIXED_NARRATIVE_META.provider,
            model=FIXED_NARRATIVE_META.model,
            model_version=FIXED_NARRATIVE_META.model_version,
            prompt_template_version=f"fixed-narrative-{operation}-v1",
        )

    async def generate_student_explanation(
        self, request: StudentNarrativeInput
    ) -> StudentNarrativeResult:
        strengths: list[str] = []
        improvements: list[str] = []
        narratives: list[StudentNarrativeQuestionProse] = []
        for q in request.questions:
            if q.performance_band == "full":
                strengths.append(f"Solid work on question {q.question_code}.")
                narratives.append(
                    StudentNarrativeQuestionProse(
                        question_code=q.question_code,
                        explanation=(
                            f"You demonstrated a complete approach on "
                            f"question {q.question_code}."
                        ),
                        corrected_approach=None,
                    )
                )
            elif q.performance_band == "none":
                improvements.append(f"Revisit question {q.question_code}.")
                narratives.append(
                    StudentNarrativeQuestionProse(
                        question_code=q.question_code,
                        explanation=(
                            f"Question {q.question_code} needs another attempt "
                            "with the key method steps."
                        ),
                        corrected_approach=(
                            "Review the model solution and retry the first "
                            "working step carefully."
                        ),
                    )
                )
            else:
                improvements.append(f"Strengthen partial credit on {q.question_code}.")
                narratives.append(
                    StudentNarrativeQuestionProse(
                        question_code=q.question_code,
                        explanation=(
                            f"Question {q.question_code} shows partial understanding; "
                            "tighten the remaining steps."
                        ),
                        corrected_approach=(
                            "Check units, signs, and the final simplification."
                        ),
                    )
                )
        if not strengths:
            strengths = ["Keep practicing structured solution steps."]
        if not improvements:
            improvements = ["Maintain accuracy under timed conditions."]
        return StudentNarrativeResult(
            strengths=strengths[:10],
            areas_for_improvement=improvements[:10],
            next_steps=[
                f"Review feedback for {request.assessment_title}.",
                "Practice similar problems from your textbook.",
            ],
            question_narratives=narratives,
        )

    async def generate_parent_summary(
        self, request: ParentNarrativeInput
    ) -> ParentNarrativeResult:
        if request.performance_overview == "strong":
            well = [f"{request.student_display_name} showed strong understanding."]
            practice = ["Continue timed practice to keep skills sharp."]
            next_step = "Encourage explaining solutions out loud once a week."
        elif request.performance_overview == "needs_practice":
            well = ["Effort and attempt structure are visible."]
            practice = [
                f"Focus on foundational steps in {request.assessment_title}.",
                "Revisit worked examples together.",
            ]
            next_step = "Schedule short daily practice on weaker topics."
        else:
            well = ["Some questions were handled well."]
            practice = ["Review questions that were only partially completed."]
            next_step = "Ask your child to rework one missed problem each evening."
        return ParentNarrativeResult(
            what_went_well=well,
            what_to_practice=practice,
            how_family_can_help=[
                "Ask them to teach you one solved example.",
                "Provide a quiet study window without phones.",
            ],
            next_step=next_step,
            score_summary=(
                f"A plain-language summary for {request.student_display_name} "
                f"on {request.assessment_title}."
            ),
        )


class NoneNarrativeProvider:
    provider_name = "none"

    async def generate_student_explanation(
        self, request: StudentNarrativeInput
    ) -> StudentNarrativeResult:
        raise ProviderUnavailable("AI_PROVIDER_TEXT=none")

    async def generate_parent_summary(
        self, request: ParentNarrativeInput
    ) -> ParentNarrativeResult:
        raise ProviderUnavailable("AI_PROVIDER_TEXT=none")
