"""Deterministic subject × language × script × operation capability checks."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.language_context import (
    ERROR_LANGUAGE_UNSUPPORTED,
    ERROR_SCRIPT_UNSUPPORTED,
    ERROR_SUBJECT_PROFILE_UNSUPPORTED,
    SUPPORTED_LANGUAGE_SCRIPTS,
)
from app.services.subject_profile import (
    KNOWN_SUBJECT_PROFILES,
    SUBJECT_PROFILE_UNSPECIFIED,
    SUBJECT_PROFILE_UNSUPPORTED,
)

CAPABLE_OPERATIONS: frozenset[str] = frozenset(
    {
        "transcribe_answer",
        "evaluate_rubric",
    }
)

# Fixed/OpenAI adapters share this bounded matrix. Unsupported combinations
# fail closed; they never silently fall through to a generic Math/English path.
_SUPPORTED: frozenset[tuple[str, str, str, str]] = frozenset(
    (profile, language, script, operation)
    for profile in (KNOWN_SUBJECT_PROFILES | {SUBJECT_PROFILE_UNSPECIFIED})
    for language, scripts in SUPPORTED_LANGUAGE_SCRIPTS.items()
    for script in scripts
    for operation in CAPABLE_OPERATIONS
)


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    supported: bool
    error_code: str | None
    subject_profile: str
    language_code: str
    script_code: str
    operation: str
    provider: str

    def as_routing_dict(self) -> dict[str, str | bool | None]:
        return {
            "supported": self.supported,
            "error_code": self.error_code,
            "subject_profile": self.subject_profile,
            "language_code": self.language_code,
            "script_code": self.script_code,
            "operation": self.operation,
            "provider": self.provider,
        }


class CapabilityUnsupported(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def check_provider_capability(
    *,
    provider: str,
    subject_profile: str,
    language_code: str,
    script_code: str,
    operation: str,
) -> CapabilityDecision:
    profile = (subject_profile or SUBJECT_PROFILE_UNSPECIFIED).strip().upper()
    language = (language_code or "en").strip().lower()
    script = (script_code or "Latn").strip()
    if script:
        script = script[0].upper() + script[1:].lower()
    op = (operation or "").strip()
    provider_name = (provider or "unknown").strip().lower()

    if profile == SUBJECT_PROFILE_UNSUPPORTED or profile not in (
        KNOWN_SUBJECT_PROFILES | {SUBJECT_PROFILE_UNSPECIFIED}
    ):
        return CapabilityDecision(
            supported=False,
            error_code=ERROR_SUBJECT_PROFILE_UNSUPPORTED,
            subject_profile=profile,
            language_code=language,
            script_code=script,
            operation=op,
            provider=provider_name,
        )
    if language not in SUPPORTED_LANGUAGE_SCRIPTS:
        return CapabilityDecision(
            supported=False,
            error_code=ERROR_LANGUAGE_UNSUPPORTED,
            subject_profile=profile,
            language_code=language,
            script_code=script,
            operation=op,
            provider=provider_name,
        )
    if script not in SUPPORTED_LANGUAGE_SCRIPTS[language]:
        return CapabilityDecision(
            supported=False,
            error_code=ERROR_SCRIPT_UNSUPPORTED,
            subject_profile=profile,
            language_code=language,
            script_code=script,
            operation=op,
            provider=provider_name,
        )
    key = (profile, language, script, op)
    if key not in _SUPPORTED:
        return CapabilityDecision(
            supported=False,
            error_code=ERROR_SUBJECT_PROFILE_UNSUPPORTED,
            subject_profile=profile,
            language_code=language,
            script_code=script,
            operation=op,
            provider=provider_name,
        )
    return CapabilityDecision(
        supported=True,
        error_code=None,
        subject_profile=profile,
        language_code=language,
        script_code=script,
        operation=op,
        provider=provider_name,
    )


def require_provider_capability(
    *,
    provider: str,
    subject_profile: str,
    language_code: str,
    script_code: str,
    operation: str,
) -> CapabilityDecision:
    decision = check_provider_capability(
        provider=provider,
        subject_profile=subject_profile,
        language_code=language_code,
        script_code=script_code,
        operation=operation,
    )
    if not decision.supported:
        raise CapabilityUnsupported(
            decision.error_code or ERROR_SUBJECT_PROFILE_UNSUPPORTED,
            "Provider does not support "
            f"{decision.subject_profile} × {decision.language_code} × "
            f"{decision.script_code} × {decision.operation}",
        )
    return decision
