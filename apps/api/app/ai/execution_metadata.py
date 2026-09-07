"""PEV-060 execution metadata for actual AI / fixed provider invocations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AIExecutionMetadata:
    provider: str
    model: str
    model_version: str
    prompt_template_version: str

    def as_record_kwargs(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "prompt_template_version": self.prompt_template_version,
        }


class SupportsExecutionMetadata(Protocol):
    provider_name: str

    def execution_metadata(self, operation: str) -> AIExecutionMetadata: ...


FIXED_STRUCTURE_META = AIExecutionMetadata(
    provider="fixed",
    model="fixed-structure",
    model_version="B11_V1",
    prompt_template_version="fixed-structure-v1",
)

FIXED_AUTHORING_META = AIExecutionMetadata(
    provider="fixed",
    model="fixed-authoring",
    model_version="B11_V1",
    prompt_template_version="fixed-authoring-v1",
)

FIXED_NARRATIVE_META = AIExecutionMetadata(
    provider="fixed",
    model="fixed-narrative",
    model_version="B11_V1",
    prompt_template_version="fixed-narrative-v1",
)

FIXED_LEARNING_META = AIExecutionMetadata(
    provider="fixed",
    model="fixed-learning",
    model_version="B11_V1",
    prompt_template_version="fixed-learning-v1",
)

OPENAI_ADAPTER_VERSION = "openai-adapter-B11_V1"


def openai_execution_metadata(*, operation: str, model: str) -> AIExecutionMetadata:
    return AIExecutionMetadata(
        provider="openai",
        model=model,
        model_version=OPENAI_ADAPTER_VERSION,
        prompt_template_version=f"openai-{operation}-v1",
    )


def metadata_from_provider(provider: Any, operation: str) -> AIExecutionMetadata:
    """Resolve PEV-060 metadata from a provider; never invent OpenAI for fixed."""
    if hasattr(provider, "execution_metadata"):
        meta = provider.execution_metadata(operation)
        if isinstance(meta, AIExecutionMetadata):
            return meta
    name = str(getattr(provider, "provider_name", "unknown") or "unknown")
    return AIExecutionMetadata(
        provider=name,
        model=f"{name}-default",
        model_version="B11_V1",
        prompt_template_version=f"{name}-{operation}-v1",
    )
