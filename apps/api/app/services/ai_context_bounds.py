"""Reusable AI proposal context bounds (Issue #7)."""

from __future__ import annotations

import json
from typing import Annotated

from pydantic import AfterValidator, Field

CONTEXT_MAX_KEYS = 20
CONTEXT_MAX_KEY_LENGTH = 100
CONTEXT_MAX_VALUE_LENGTH = 2000
CONTEXT_MAX_SERIALIZED_BYTES = 16_384


def validate_ai_proposal_context(context: dict[str, str]) -> dict[str, str]:
    """Enforce CVB bounds on A2 AI proposal context maps."""
    if len(context) > CONTEXT_MAX_KEYS:
        raise ValueError(f"context may contain at most {CONTEXT_MAX_KEYS} keys")
    for key, value in context.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("context keys and values must be strings")
        if len(key) > CONTEXT_MAX_KEY_LENGTH:
            raise ValueError(
                f"context key length must be <= {CONTEXT_MAX_KEY_LENGTH} characters"
            )
        if len(value) > CONTEXT_MAX_VALUE_LENGTH:
            raise ValueError(
                f"context value length must be <= {CONTEXT_MAX_VALUE_LENGTH} characters"
            )
    encoded = json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(encoded) > CONTEXT_MAX_SERIALIZED_BYTES:
        raise ValueError(
            f"context serialized size must be <= {CONTEXT_MAX_SERIALIZED_BYTES} UTF-8 bytes"
        )
    return context


BoundedAiContext = Annotated[
    dict[str, str],
    Field(default_factory=dict),
    AfterValidator(validate_ai_proposal_context),
]
