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
    s3_endpoint_url: str = Field(
        default="http://127.0.0.1:19000",
        validation_alias=AliasChoices("S3_ENDPOINT_URL", "s3_endpoint_url"),
    )
    s3_access_key: str = Field(
        default="eduvijna_minio",
        validation_alias=AliasChoices("S3_ACCESS_KEY", "s3_access_key"),
    )
    s3_secret_key: str = Field(
        default="eduvijna_minio_dev_only",
        validation_alias=AliasChoices("S3_SECRET_KEY", "s3_secret_key"),
    )
    s3_bucket: str = Field(
        default="eduvijna-papers",
        validation_alias=AliasChoices("S3_BUCKET", "s3_bucket"),
    )
    s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("S3_REGION", "s3_region"),
    )
    submission_upload_max_bytes: int = Field(
        default=52_428_800,
        validation_alias=AliasChoices(
            "SUBMISSION_UPLOAD_MAX_BYTES", "submission_upload_max_bytes"
        ),
    )
    submission_max_pages: int = Field(
        default=100,
        validation_alias=AliasChoices("SUBMISSION_MAX_PAGES", "submission_max_pages"),
    )
    celery_broker_url: str = Field(
        default="redis://127.0.0.1:16379/0",
        validation_alias=AliasChoices("CELERY_BROKER_URL", "celery_broker_url"),
    )
    celery_result_backend: str = Field(
        default="redis://127.0.0.1:16379/1",
        validation_alias=AliasChoices("CELERY_RESULT_BACKEND", "celery_result_backend"),
    )
    celery_task_always_eager: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "CELERY_TASK_ALWAYS_EAGER", "celery_task_always_eager"
        ),
    )
    ai_provider_vision: str = Field(
        default="none",
        validation_alias=AliasChoices("AI_PROVIDER_VISION", "ai_provider_vision"),
    )
    ai_model_identity: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("AI_MODEL_IDENTITY", "ai_model_identity"),
    )
    ai_model_page_analysis: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices(
            "AI_MODEL_PAGE_ANALYSIS", "ai_model_page_analysis"
        ),
    )
    ai_model_mapping: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("AI_MODEL_MAPPING", "ai_model_mapping"),
    )
    ai_model_transcription: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices(
            "AI_MODEL_TRANSCRIPTION", "ai_model_transcription"
        ),
    )
    ai_model_evaluation: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("AI_MODEL_EVALUATION", "ai_model_evaluation"),
        description=(
            "Model for evaluate_rubric/classify_error. Provider selection reuses "
            "AI_PROVIDER_VISION (fixed/openai/none) — no separate AI_PROVIDER_EVALUATION."
        ),
    )
    ai_request_timeout_seconds: int = Field(
        default=60,
        validation_alias=AliasChoices(
            "AI_REQUEST_TIMEOUT_SECONDS", "ai_request_timeout_seconds"
        ),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
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
