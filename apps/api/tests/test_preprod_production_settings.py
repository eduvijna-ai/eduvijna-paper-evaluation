"""Unit tests for production fail-closed settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base(**overrides: object) -> Settings:
    data = {
        "environment": "production",
        "auth_token_secret": "production-secret-not-for-git",
        "ai_provider_vision": "none",
        "ai_provider_text": "none",
        "ai_provider_authoring": "none",
        "upload_scanner": "none",
        "b19_test_providers_enabled": False,
        "webhook_allow_insecure_destinations": False,
    }
    data.update(overrides)
    return Settings(**data)  # type: ignore[arg-type]


def test_production_accepts_secure_defaults() -> None:
    settings = _base()
    assert settings.environment == "production"


@pytest.mark.parametrize(
    "field,value",
    [
        ("ai_provider_vision", "fixed"),
        ("ai_provider_text", "fixed"),
        ("ai_provider_authoring", "fixed"),
        ("upload_scanner", "fixed"),
    ],
)
def test_production_rejects_fixed_providers(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        _base(**{field: value})


def test_production_rejects_test_webhooks_and_providers() -> None:
    with pytest.raises(ValidationError):
        _base(b19_test_providers_enabled=True)
    with pytest.raises(ValidationError):
        _base(webhook_allow_insecure_destinations=True)


def test_local_still_allows_fixed() -> None:
    settings = Settings(
        environment="local",
        ai_provider_vision="fixed",
        upload_scanner="fixed",
    )
    assert settings.ai_provider_vision == "fixed"
