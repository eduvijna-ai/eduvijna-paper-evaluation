"""Bounded B20 language/script semantics for the submission understanding flow."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

LANGUAGE_STATE_UNKNOWN = "UNKNOWN"
LANGUAGE_STATE_CONFIRMED = "CONFIRMED"
LANGUAGE_STATE_REVIEW_REQUIRED = "REVIEW_REQUIRED"
LANGUAGE_STATE_UNSUPPORTED = "UNSUPPORTED"

LANGUAGE_SOURCE_UNKNOWN = "UNKNOWN"
LANGUAGE_SOURCE_PROVIDED = "PROVIDED"
LANGUAGE_SOURCE_DETECTED = "DETECTED"

LANGUAGE_STATES: frozenset[str] = frozenset(
    {
        LANGUAGE_STATE_UNKNOWN,
        LANGUAGE_STATE_CONFIRMED,
        LANGUAGE_STATE_REVIEW_REQUIRED,
        LANGUAGE_STATE_UNSUPPORTED,
    }
)
LANGUAGE_SOURCES: frozenset[str] = frozenset(
    {
        LANGUAGE_SOURCE_UNKNOWN,
        LANGUAGE_SOURCE_PROVIDED,
        LANGUAGE_SOURCE_DETECTED,
    }
)

# Bounded BCP-47 / ISO-15924 subset used by B20 fixtures and routing.
SUPPORTED_LANGUAGE_SCRIPTS: dict[str, frozenset[str]] = {
    "en": frozenset({"Latn"}),
    "hi": frozenset({"Deva"}),
}

DEFAULT_SCRIPT_FOR_LANGUAGE: dict[str, str] = {
    "en": "Latn",
    "hi": "Deva",
}

LANGUAGE_DETECTION_REVIEW_THRESHOLD = Decimal("0.8500")

ERROR_LANGUAGE_UNSUPPORTED = "LANGUAGE_UNSUPPORTED"
ERROR_SCRIPT_UNSUPPORTED = "SCRIPT_UNSUPPORTED"
ERROR_LANGUAGE_REVIEW_REQUIRED = "LANGUAGE_REVIEW_REQUIRED"
ERROR_LANGUAGE_CONTEXT_REQUIRED = "LANGUAGE_CONTEXT_REQUIRED"
ERROR_SUBJECT_PROFILE_UNSUPPORTED = "SUBJECT_PROFILE_UNSUPPORTED"


class LanguageContextError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def canonicalize_language_code(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip()
    if not token:
        return None
    primary = token.replace("_", "-").split("-", 1)[0].lower()
    if not primary or len(primary) > 8:
        raise LanguageContextError(
            ERROR_LANGUAGE_UNSUPPORTED,
            f"Unsupported language code: {value}",
        )
    return primary


def canonicalize_script_code(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip()
    if not token:
        return None
    if len(token) != 4 or not token.isalpha():
        raise LanguageContextError(
            ERROR_SCRIPT_UNSUPPORTED,
            f"Unsupported script code: {value}",
        )
    return token[0].upper() + token[1:].lower()


def default_script_for_language(language_code: str | None) -> str | None:
    if not language_code:
        return None
    return DEFAULT_SCRIPT_FOR_LANGUAGE.get(language_code)


def language_script_supported(language_code: str | None, script_code: str | None) -> bool:
    if language_code is None:
        return True
    allowed = SUPPORTED_LANGUAGE_SCRIPTS.get(language_code)
    if allowed is None:
        return False
    if script_code is None:
        return True
    return script_code in allowed


@dataclass(frozen=True, slots=True)
class LanguageDecision:
    language_code: str | None
    script_code: str | None
    language_source: str
    language_confidence: Decimal | None
    language_state: str
    routing_language_code: str
    routing_script_code: str
    gate_code: str | None

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "language_code": self.language_code,
            "script_code": self.script_code,
            "language_source": self.language_source,
            "language_confidence": (
                float(self.language_confidence)
                if self.language_confidence is not None
                else None
            ),
            "language_state": self.language_state,
        }

    def routing_dict(self) -> dict[str, str | None]:
        return {
            "language_code": self.language_code,
            "script_code": self.script_code,
            "routing_language_code": self.routing_language_code,
            "routing_script_code": self.routing_script_code,
            "language_source": self.language_source,
            "language_state": self.language_state,
        }


def _routing_pair(
    language_code: str | None, script_code: str | None
) -> tuple[str, str]:
    lang = language_code or "en"
    script = script_code or default_script_for_language(lang) or "Latn"
    return lang, script


def decide_provided_language(
    *,
    language_code: str | None,
    script_code: str | None,
) -> LanguageDecision:
    """Explicit upload/confirm path. Omitted values stay UNKNOWN (legacy)."""
    lang = canonicalize_language_code(language_code)
    script = canonicalize_script_code(script_code)
    if lang is None and script is None:
        routing_lang, routing_script = _routing_pair(None, None)
        return LanguageDecision(
            language_code=None,
            script_code=None,
            language_source=LANGUAGE_SOURCE_UNKNOWN,
            language_confidence=None,
            language_state=LANGUAGE_STATE_UNKNOWN,
            routing_language_code=routing_lang,
            routing_script_code=routing_script,
            gate_code=None,
        )
    if lang is None:
        raise LanguageContextError(
            ERROR_LANGUAGE_CONTEXT_REQUIRED,
            "script_code requires language_code",
        )
    if script is None:
        script = default_script_for_language(lang)
    if not language_script_supported(lang, script):
        if lang not in SUPPORTED_LANGUAGE_SCRIPTS:
            gate = ERROR_LANGUAGE_UNSUPPORTED
            state = LANGUAGE_STATE_UNSUPPORTED
        else:
            gate = ERROR_SCRIPT_UNSUPPORTED
            state = LANGUAGE_STATE_UNSUPPORTED
        routing_lang, routing_script = _routing_pair(lang, script)
        return LanguageDecision(
            language_code=lang,
            script_code=script,
            language_source=LANGUAGE_SOURCE_PROVIDED,
            language_confidence=None,
            language_state=state,
            routing_language_code=routing_lang,
            routing_script_code=routing_script,
            gate_code=gate,
        )
    routing_lang, routing_script = _routing_pair(lang, script)
    return LanguageDecision(
        language_code=lang,
        script_code=script,
        language_source=LANGUAGE_SOURCE_PROVIDED,
        language_confidence=None,
        language_state=LANGUAGE_STATE_CONFIRMED,
        routing_language_code=routing_lang,
        routing_script_code=routing_script,
        gate_code=None,
    )


def decide_detected_language(
    *,
    language_code: str | None,
    script_code: str | None,
    confidence: Decimal | None,
    ambiguous: bool = False,
) -> LanguageDecision:
    """AI/fixture detection. Never auto-confirms, even at high confidence."""
    try:
        lang = canonicalize_language_code(language_code)
        script = canonicalize_script_code(script_code)
    except LanguageContextError:
        routing_lang, routing_script = _routing_pair("und", None)
        return LanguageDecision(
            language_code=language_code.strip().lower() if language_code else None,
            script_code=script_code,
            language_source=LANGUAGE_SOURCE_DETECTED,
            language_confidence=confidence,
            language_state=LANGUAGE_STATE_UNSUPPORTED,
            routing_language_code=routing_lang,
            routing_script_code=routing_script,
            gate_code=ERROR_LANGUAGE_UNSUPPORTED,
        )
    if lang is None:
        routing_lang, routing_script = _routing_pair(None, None)
        return LanguageDecision(
            language_code=None,
            script_code=None,
            language_source=LANGUAGE_SOURCE_DETECTED,
            language_confidence=confidence,
            language_state=LANGUAGE_STATE_REVIEW_REQUIRED,
            routing_language_code=routing_lang,
            routing_script_code=routing_script,
            gate_code=ERROR_LANGUAGE_REVIEW_REQUIRED,
        )
    if script is None:
        script = default_script_for_language(lang)
    if lang == "und" or not language_script_supported(lang, script):
        if lang not in SUPPORTED_LANGUAGE_SCRIPTS or lang == "und":
            gate = ERROR_LANGUAGE_UNSUPPORTED
            state = LANGUAGE_STATE_UNSUPPORTED
        else:
            gate = ERROR_SCRIPT_UNSUPPORTED
            state = LANGUAGE_STATE_UNSUPPORTED
        routing_lang, routing_script = _routing_pair(lang, script)
        return LanguageDecision(
            language_code=lang,
            script_code=script,
            language_source=LANGUAGE_SOURCE_DETECTED,
            language_confidence=confidence,
            language_state=state,
            routing_language_code=routing_lang,
            routing_script_code=routing_script,
            gate_code=gate,
        )
    low_confidence = confidence is None or confidence < LANGUAGE_DETECTION_REVIEW_THRESHOLD
    routing_lang, routing_script = _routing_pair(lang, script)
    return LanguageDecision(
        language_code=lang,
        script_code=script,
        language_source=LANGUAGE_SOURCE_DETECTED,
        language_confidence=confidence,
        language_state=LANGUAGE_STATE_REVIEW_REQUIRED,
        routing_language_code=routing_lang,
        routing_script_code=routing_script,
        gate_code=ERROR_LANGUAGE_REVIEW_REQUIRED if (ambiguous or low_confidence or True) else None,
    )


def decision_from_submission(submission: Any) -> LanguageDecision:
    lang = getattr(submission, "language_code", None)
    script = getattr(submission, "script_code", None)
    source = getattr(submission, "language_source", None) or LANGUAGE_SOURCE_UNKNOWN
    state = getattr(submission, "language_state", None) or LANGUAGE_STATE_UNKNOWN
    confidence = getattr(submission, "language_confidence", None)
    routing_lang, routing_script = _routing_pair(lang, script)
    gate = None
    if state == LANGUAGE_STATE_UNSUPPORTED:
        if lang and lang not in SUPPORTED_LANGUAGE_SCRIPTS:
            gate = ERROR_LANGUAGE_UNSUPPORTED
        else:
            gate = ERROR_SCRIPT_UNSUPPORTED
    elif state == LANGUAGE_STATE_REVIEW_REQUIRED:
        gate = ERROR_LANGUAGE_REVIEW_REQUIRED
    return LanguageDecision(
        language_code=lang,
        script_code=script,
        language_source=source,
        language_confidence=confidence,
        language_state=state,
        routing_language_code=routing_lang,
        routing_script_code=routing_script,
        gate_code=gate,
    )


def apply_decision_to_submission(submission: Any, decision: LanguageDecision) -> None:
    submission.language_code = decision.language_code
    submission.script_code = decision.script_code
    submission.language_source = decision.language_source
    submission.language_confidence = decision.language_confidence
    submission.language_state = decision.language_state


LanguageState = Literal["UNKNOWN", "CONFIRMED", "REVIEW_REQUIRED", "UNSUPPORTED"]
