"""Provider registry for B5 structure operations."""

from __future__ import annotations

from app.ai.protocols import StructureAIProvider
from app.ai.providers.fixed import FixedStructureProvider, NoneStructureProvider
from app.ai.providers.openai import OpenAIStructureProvider
from app.core.config import Settings, get_settings


def get_structure_provider(settings: Settings | None = None) -> StructureAIProvider:
    settings = settings or get_settings()
    mode = (settings.ai_provider_vision or "none").strip().lower()
    env = settings.environment.lower()

    if mode == "none":
        return NoneStructureProvider()
    if mode == "fixed":
        if env in {"production", "prod"}:
            raise RuntimeError("fixed AI provider is not allowed in production")
        return FixedStructureProvider(allow_non_test=True)
    if mode == "openai":
        return OpenAIStructureProvider(
            api_key=settings.openai_api_key,
            model_identity=settings.ai_model_identity,
            model_page_analysis=settings.ai_model_page_analysis,
            model_mapping=settings.ai_model_mapping,
            model_transcription=settings.ai_model_transcription,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )
    raise RuntimeError(f"Unsupported AI_PROVIDER_VISION={mode!r}")


def structure_provider_active(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return (settings.ai_provider_vision or "none").strip().lower() not in {"", "none"}
