"""Tests for shared Settings loading (FR-016)."""

import pytest

from exambrain_shared.config import Settings


def test_settings_load_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must load with no environment at all — optional fields None."""
    for var in (
        "LOG_LEVEL",
        "DATABASE_URL",
        "REDIS_URL",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "S3_BUCKET",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.redis_url is None
    assert settings.otel_exporter_otlp_endpoint is None
    assert settings.aws_access_key_id is None
    assert settings.llm_provider is None


def test_log_level_defaults_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.log_level == "INFO"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    settings = Settings(_env_file=None)
    assert settings.log_level == "DEBUG"
    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"
