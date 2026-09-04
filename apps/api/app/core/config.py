from functools import lru_cache

from pydantic import AliasChoices, Field
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
