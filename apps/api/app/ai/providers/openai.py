"""Optional OpenAI structure provider (no network in CI)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.ai.types import (
    IdentityExtractionInput,
    IdentityExtractionResult,
    PageAnalysisInput,
    PageAnalysisResult,
    ProviderUnavailable,
    RegionMappingInput,
    RegionMappingResult,
    TranscriptionInput,
    TranscriptionResult,
)

JsonCaller = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class OpenAIStructureProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None,
        model_identity: str,
        model_page_analysis: str,
        model_mapping: str,
        model_transcription: str,
        timeout_seconds: int = 60,
        caller: JsonCaller | None = None,
    ) -> None:
        self._api_key = api_key
        self._models = {
            "identity": model_identity,
            "page_analysis": model_page_analysis,
            "mapping": model_mapping,
            "transcription": model_transcription,
        }
        self._timeout = timeout_seconds
        self._caller = caller

    def _require(self) -> None:
        if not self._api_key and self._caller is None:
            raise ProviderUnavailable("OPENAI_API_KEY is not configured")

    async def _complete(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require()
        if self._caller is not None:
            return await self._caller(operation, payload)
        # Production path uses official SDK only when key is present.
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise ProviderUnavailable("openai SDK is not installed") from exc
        client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout)
        model = self._models[operation]
        response = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": f"Return JSON only for EduVijna {operation}.",
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("OpenAI response must be a JSON object")
        return data

    async def extract_student_identity(
        self, request: IdentityExtractionInput
    ) -> IdentityExtractionResult:
        raw = await self._complete("identity", request.model_dump(mode="json"))
        return IdentityExtractionResult.model_validate(raw)

    async def analyze_page(self, request: PageAnalysisInput) -> PageAnalysisResult:
        raw = await self._complete("page_analysis", request.model_dump(mode="json"))
        return PageAnalysisResult.model_validate(raw)

    async def map_answer_regions(
        self, request: RegionMappingInput
    ) -> RegionMappingResult:
        raw = await self._complete("mapping", request.model_dump(mode="json"))
        return RegionMappingResult.model_validate(raw)

    async def transcribe_answer(
        self, request: TranscriptionInput
    ) -> TranscriptionResult:
        # Crop bytes are never included — only sha256 ref in the typed input.
        raw = await self._complete("transcription", request.model_dump(mode="json"))
        return TranscriptionResult.model_validate(raw)
