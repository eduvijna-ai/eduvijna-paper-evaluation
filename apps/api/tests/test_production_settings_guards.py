"""Production fail-closed Settings guards (pre-production hardening)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _prod_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "environment": "production",
        "auth_token_secret": "prod-secret-not-for-git",
        "ai_provider_vision": "openai",
        "ai_provider_text": "openai",
        "ai_provider_authoring": "openai",
        "upload_scanner": "none",
        "b19_test_providers_enabled": False,
        "webhook_allow_insecure_destinations": False,
        "_env_file": None,
    }
    base.update(overrides)
    return base


def test_production_settings_accept_safe_values() -> None:
    settings = Settings(**_prod_kwargs())  # type: ignore[arg-type]
    assert settings.environment == "production"
    assert settings.auth_token_secret == "prod-secret-not-for-git"


@pytest.mark.parametrize(
    "overrides",
    [
        {"ai_provider_vision": "fixed"},
        {"ai_provider_text": "fixed"},
        {"ai_provider_authoring": "fixed"},
        {"upload_scanner": "fixed"},
        {"b19_test_providers_enabled": True},
        {"webhook_allow_insecure_destinations": True},
        {"auth_token_secret": None, "environment": "production"},
    ],
)
def test_production_settings_reject_unsafe_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(**_prod_kwargs(**overrides))  # type: ignore[arg-type]


def test_prod_alias_also_fail_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(**_prod_kwargs(environment="prod", ai_provider_vision="fixed"))  # type: ignore[arg-type]


def test_local_allows_fixed_providers() -> None:
    settings = Settings(
        **_prod_kwargs(  # type: ignore[arg-type]
            environment="local",
            auth_token_secret=None,
            ai_provider_vision="fixed",
            upload_scanner="fixed",
            b19_test_providers_enabled=True,
            webhook_allow_insecure_destinations=True,
        )
    )
    assert settings.ai_provider_vision == "fixed"
    assert settings.auth_token_secret  # local default injected
