"""Deterministic learning AI provider for B9 (no network)."""

from __future__ import annotations

from app.ai.types import (
    ImprovementBlueprintAIInput,
    ImprovementBlueprintAIResult,
    ImprovementBlueprintItemProse,
    LearningPlanAIInput,
    LearningPlanAIResult,
    LearningPlanPathStepProse,
    LearningPlanRecommendationProse,
)


class FixedLearningProvider:
    """Deterministic bounded prose over server-authorized structure."""

    provider_name = "fixed"

    def __init__(self, *, allow_non_test: bool = False) -> None:
        self._allow_non_test = allow_non_test

    async def generate_learning_plan(
        self, request: LearningPlanAIInput
    ) -> LearningPlanAIResult:
        return LearningPlanAIResult(
            recommendation_prose=[
                LearningPlanRecommendationProse(
                    recommendation_key=r.recommendation_key,
                    rationale=r.default_rationale,
                )
                for r in request.recommendations
            ],
            path_step_prose=[
                LearningPlanPathStepProse(
                    step_key=s.step_key,
                    description=s.default_description,
                )
                for s in request.path_steps
            ],
        )

    async def generate_improvement_blueprint(
        self, request: ImprovementBlueprintAIInput
    ) -> ImprovementBlueprintAIResult:
        return ImprovementBlueprintAIResult(
            title=request.title,
            item_prose=[
                ImprovementBlueprintItemProse(
                    item_key=i.item_key,
                    focus=i.default_focus,
                )
                for i in request.items
            ],
        )
