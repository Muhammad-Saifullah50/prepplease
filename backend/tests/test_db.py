"""Tests for the lazy async DB foundation (FR-005)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

import exambrain_shared.db as db
from exambrain_shared.db import (
    Base,
    NotConfiguredError,
    get_engine,
    get_session_factory,
)


@pytest.fixture(autouse=True)
def reset_lazy_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate each test from module-level lazy singletons."""
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)


def test_import_creates_no_engine() -> None:
    """Importing the module must not create an engine or connect (FR-005)."""
    assert db._engine is None


def test_get_engine_without_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from exambrain_shared.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(NotConfiguredError, match="Database is not configured"):
            get_engine()
    finally:
        get_settings.cache_clear()


def test_get_engine_lazy_creation() -> None:
    engine = get_engine("postgresql+asyncpg://u:p@localhost:5432/testdb")
    assert isinstance(engine, AsyncEngine)
    # Second call returns the same cached engine.
    assert get_engine() is engine


def test_session_factory_binds_engine() -> None:
    factory = get_session_factory("postgresql+asyncpg://u:p@localhost:5432/testdb")
    assert factory.kw["bind"] is db._engine


def test_declarative_base_has_metadata() -> None:
    assert Base.metadata is not None
