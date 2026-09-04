from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    application: str = Field(
        default="eduvijna-paper-evaluation",
        validation_alias=AliasChoices("APP_NAME", "application"),
    )
    environment: str = Field(
        default="local",
        validation_alias=AliasChoices("APP_ENV", "environment"),
    )
    git_sha: str = Field(
        default="unknown",
        validation_alias=AliasChoices("GIT_SHA", "git_sha"),
    )
    api_version: str = Field(
        default="0.1.0",
        validation_alias=AliasChoices("API_VERSION", "api_version"),
    )
    database_url: str = Field(
        default="postgresql+asyncpg://eduvijna:eduvijna_local_dev_only@localhost:5432/eduvijna",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL", "log_level"),
    )
    auth_token_secret: str | None = Field(
        default=None, validation_alias=AliasChoices("AUTH_TOKEN_SECRET", "auth_token_secret")
    )
    auth_token_ttl_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("AUTH_TOKEN_TTL_MINUTES", "auth_token_ttl_minutes"),
    )
    auth_algorithm: str = Field(
        default="HS256", validation_alias=AliasChoices("AUTH_ALGORITHM", "auth_algorithm")
    )
    student_import_max_bytes: int = Field(
        default=2_000_000,
        validation_alias=AliasChoices("STUDENT_IMPORT_MAX_BYTES", "student_import_max_bytes"),
    )
    student_import_max_rows: int = Field(
        default=5_000,
        validation_alias=AliasChoices("STUDENT_IMPORT_MAX_ROWS", "student_import_max_rows"),
    )

    @model_validator(mode="after")
    def require_auth_secret(self) -> "Settings":
        if not self.auth_token_secret:
            if self.environment.lower() not in {"local", "test"}:
                raise ValueError("AUTH_TOKEN_SECRET is required outside local/test")
            self.auth_token_secret = "eduvijna_local_jwt_dev_only_change_me"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
