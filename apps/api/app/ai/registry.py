"""Provider registry for B5–B10 structure, evaluation, narrative, learning, authoring."""

from __future__ import annotations

from typing import Any

from app.ai.protocols import (
    AuthoringAIProvider,
    EvaluationAIProvider,
    LearningAIProvider,
    NarrativeAIProvider,
    StructureAIProvider,
)
from app.ai.providers.authoring import FixedAuthoringProvider
from app.ai.providers.fixed import FixedStructureProvider, NoneStructureProvider
from app.ai.providers.learning import FixedLearningProvider
from app.ai.providers.narrative import FixedNarrativeProvider, NoneNarrativeProvider
from app.ai.providers.openai import OpenAIStructureProvider
from app.core.config import Settings, get_settings


def _vision_mode(settings: Settings) -> str:
    return (settings.ai_provider_vision or "none").strip().lower()


def _text_mode(settings: Settings) -> str:
    return (settings.ai_provider_text or "none").strip().lower()


def _authoring_mode(settings: Settings) -> str:
    return (settings.ai_provider_authoring or "none").strip().lower()


def _openai_provider(settings: Settings) -> OpenAIStructureProvider:
    return OpenAIStructureProvider(
        api_key=settings.openai_api_key,
        model_identity=settings.ai_model_identity,
        model_page_analysis=settings.ai_model_page_analysis,
        model_mapping=settings.ai_model_mapping,
        model_transcription=settings.ai_model_transcription,
        model_evaluation=settings.ai_model_evaluation,
        model_student_report=settings.ai_model_student_report,
        model_parent_report=settings.ai_model_parent_report,
        model_learning_plan=settings.ai_model_learning_plan,
        model_improvement_blueprint=settings.ai_model_improvement_blueprint,
        model_question_paper_parse=settings.ai_model_question_paper_parse,
        model_answer_key_proposal=settings.ai_model_answer_key_proposal,
        model_rubric_proposal=settings.ai_model_rubric_proposal,
        model_curriculum_mapping_proposal=settings.ai_model_curriculum_mapping_proposal,
        timeout_seconds=settings.ai_request_timeout_seconds,
    )


def get_structure_provider(settings: Settings | None = None) -> StructureAIProvider:
    settings = settings or get_settings()
    mode = _vision_mode(settings)
    env = settings.environment.lower()

    if mode == "none":
        return NoneStructureProvider()
    if mode == "fixed":
        if env in {"production", "prod"}:
            raise RuntimeError("fixed AI provider is not allowed in production")
        return FixedStructureProvider(allow_non_test=True)
    if mode == "openai":
        return _openai_provider(settings)
    raise RuntimeError(f"Unsupported AI_PROVIDER_VISION={mode!r}")


def get_evaluation_provider(settings: Settings | None = None) -> EvaluationAIProvider:
    """Reuse AI_PROVIDER_VISION so fixed/openai/none work for evaluation in CI."""
    # Same concrete classes implement EvaluationAIProvider.
    return get_structure_provider(settings)  # type: ignore[return-value]


def get_narrative_provider(
    settings: Settings | None = None,
) -> NarrativeAIProvider | None:
    """Return narrative provider, or None when AI_PROVIDER_TEXT=none (rules fallback)."""
    settings = settings or get_settings()
    mode = _text_mode(settings)
    env = settings.environment.lower()

    if mode in {"", "none"}:
        return None
    if mode == "fixed":
        if env in {"production", "prod"}:
            raise RuntimeError("fixed AI provider is not allowed in production")
        return FixedNarrativeProvider(allow_non_test=True)
    if mode == "openai":
        return _openai_provider(settings)
    raise RuntimeError(f"Unsupported AI_PROVIDER_TEXT={mode!r}")


def get_learning_provider(
    settings: Settings | None = None,
) -> LearningAIProvider | None:
    """Return learning provider, or None when AI_PROVIDER_TEXT=none (rules fallback)."""
    settings = settings or get_settings()
    mode = _text_mode(settings)
    env = settings.environment.lower()

    if mode in {"", "none"}:
        return None
    if mode == "fixed":
        if env in {"production", "prod"}:
            raise RuntimeError("fixed AI provider is not allowed in production")
        return FixedLearningProvider(allow_non_test=True)
    if mode == "openai":
        return _openai_provider(settings)
    raise RuntimeError(f"Unsupported AI_PROVIDER_TEXT={mode!r}")


def get_authoring_provider(
    settings: Settings | None = None,
) -> AuthoringAIProvider | None:
    """Return authoring provider, or None when AI_PROVIDER_AUTHORING=none (503)."""
    settings = settings or get_settings()
    mode = _authoring_mode(settings)
    env = settings.environment.lower()

    if mode in {"", "none"}:
        return None
    if mode == "fixed":
        if env in {"production", "prod"}:
            raise RuntimeError("fixed AI provider is not allowed in production")
        return FixedAuthoringProvider(allow_non_test=True)
    if mode == "openai":
        return _openai_provider(settings)
    raise RuntimeError(f"Unsupported AI_PROVIDER_AUTHORING={mode!r}")


def structure_provider_active(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return _vision_mode(settings) not in {"", "none"}


def evaluation_provider_active(settings: Settings | None = None) -> bool:
    return structure_provider_active(settings)


def narrative_provider_active(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return _text_mode(settings) not in {"", "none"}


def learning_provider_active(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return _text_mode(settings) not in {"", "none"}


def authoring_provider_active(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return _authoring_mode(settings) not in {"", "none"}


def get_benchmark_candidate_executor(
    *,
    candidate_provider: str,
    candidate_model: str,
    settings: Settings | None = None,
) -> Any:
    """Resolve a B15 gold-regression candidate through the provider registry.

    CI fixtures (``fixed`` + ``fixed-benchmark-*``) stay credential-free.
    Configured candidates use :func:`get_evaluation_provider` and never
    invoke vendor SDKs from the benchmark domain layer.
    """
    from app.ai.providers.benchmark import resolve_benchmark_candidate

    return resolve_benchmark_candidate(
        candidate_provider=candidate_provider,
        candidate_model=candidate_model,
        settings=settings,
    )


__all__ = [
    "NoneNarrativeProvider",
    "authoring_provider_active",
    "evaluation_provider_active",
    "get_authoring_provider",
    "get_benchmark_candidate_executor",
    "get_evaluation_provider",
    "get_learning_provider",
    "get_narrative_provider",
    "get_structure_provider",
    "learning_provider_active",
    "narrative_provider_active",
    "structure_provider_active",
]
