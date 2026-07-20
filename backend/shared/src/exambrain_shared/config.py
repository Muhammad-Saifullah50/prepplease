"""Application settings via pydantic-settings.

All infrastructure/credential fields are optional so that importing or
instantiating :class:`Settings` never raises when configuration is absent
(FR-016). Stubs that need these values raise ``NotConfiguredError`` at call
time instead (FR-017).
"""

from collections.abc import Iterable
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
    llm_embedding_model: str | None = None
    llm_max_retries: int = 3
    llm_retry_deadline_seconds: int = 60

    # Rate limiting defaults (optional)
    rate_limit_default_threshold: int | None = None
    rate_limit_default_window_seconds: int | None = None

    # S3 endpoint override (future MinIO swap)
    s3_endpoint_url: str | None = None

    # Per-agent model overrides (Phase 2 agents; default to llm_model — FR-021)
    agent_parsing_model: str | None = None
    agent_alignment_model: str | None = None
    agent_blueprint_model: str | None = None
    agent_generator_model: str | None = None
    agent_evaluation_model: str | None = None

    # Agent behavior (Phase 2 agents — research R10)
    agent_max_turns: int = 10
    alignment_auto_match_threshold: float = 0.90
    alignment_review_threshold: float = 0.70
    parsing_review_confidence_threshold: float = 0.60

    _SECRET_FIELDS = frozenset({"aws_secret_access_key", "llm_api_key"})

    def __repr_args__(self) -> "Iterable[tuple[str | None, object]]":
        """Redact secret values in repr/str so they never reach logs."""
        for name, value in super().__repr_args__():
            if name in self._SECRET_FIELDS and value is not None:
                yield name, "***"
            else:
                yield name, value


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
