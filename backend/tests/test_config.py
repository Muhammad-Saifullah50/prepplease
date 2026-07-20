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


def test_agent_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Per-agent overrides default to None; behavior knobs to spec defaults."""
    for var in (
        "AGENT_PARSING_MODEL",
        "AGENT_ALIGNMENT_MODEL",
        "AGENT_BLUEPRINT_MODEL",
        "AGENT_GENERATOR_MODEL",
        "AGENT_EVALUATION_MODEL",
        "AGENT_MAX_TURNS",
        "ALIGNMENT_AUTO_MATCH_THRESHOLD",
        "ALIGNMENT_REVIEW_THRESHOLD",
        "PARSING_REVIEW_CONFIDENCE_THRESHOLD",
    ):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.agent_parsing_model is None
    assert settings.agent_alignment_model is None
    assert settings.agent_blueprint_model is None
    assert settings.agent_generator_model is None
    assert settings.agent_evaluation_model is None
    assert settings.agent_max_turns == 10
    assert settings.alignment_auto_match_threshold == 0.90
    assert settings.alignment_review_threshold == 0.70
    assert settings.parsing_review_confidence_threshold == 0.60


def test_agent_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PARSING_MODEL", "bedrock/some-parsing-model")
    monkeypatch.setenv("AGENT_MAX_TURNS", "5")
    monkeypatch.setenv("ALIGNMENT_AUTO_MATCH_THRESHOLD", "0.95")
    settings = Settings(_env_file=None)
    assert settings.agent_parsing_model == "bedrock/some-parsing-model"
    assert settings.agent_max_turns == 5
    assert settings.alignment_auto_match_threshold == 0.95
