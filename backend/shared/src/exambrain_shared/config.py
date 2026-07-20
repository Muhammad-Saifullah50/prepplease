"""Application settings via pydantic-settings.

All infrastructure/credential fields are optional so that importing or
instantiating :class:`Settings` never raises when configuration is absent
(FR-016). Stubs that need these values raise ``NotConfiguredError`` at call
time instead (FR-017).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings shared by all ExamBrain services."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Logging
    log_level: str = "INFO"

    # Infrastructure (optional at scaffold stage)
    database_url: str | None = None
    redis_url: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    # AWS (unused until IAM/S3 features land — stubs defer errors)
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
    s3_bucket: str | None = None

    # LLM (unused until LLM features land — stub defers errors)
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
