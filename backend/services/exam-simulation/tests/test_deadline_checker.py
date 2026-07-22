"""Unit tests for deadline checker background task."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from exambrain_shared.models.exam_sim import ExamSession
from exam_simulation.services.deadline_checker import DeadlineChecker


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> async_sessionmaker[AsyncSession]:
    factory = MagicMock(spec=async_sessionmaker)
    factory.return_value.__aenter__.return_value = mock_session
    factory.return_value.__aexit__ = AsyncMock()
    return factory


@pytest.fixture
def checker(mock_session_factory: async_sessionmaker[AsyncSession]) -> DeadlineChecker:
    return DeadlineChecker(mock_session_factory)


def _make_expired_session(**kwargs: object) -> MagicMock:
    session = MagicMock(spec=ExamSession)
    session.id = kwargs.get("id", 1)
    session.status = kwargs.get("status", "active")
    session.deadline = kwargs.get(
        "deadline", datetime.now(timezone.utc) - timedelta(minutes=10)
    )
    session.finished_by = None
    session.ended_at = None
    return session


async def test_catch_up_missed_deadlines(
    checker: DeadlineChecker,
    mock_session: AsyncMock,
    mock_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    expired = [_make_expired_session(), _make_expired_session()]
    scalar_result = MagicMock()
    scalar_result.scalars.return_value.all.return_value = expired
    mock_session.execute.return_value = scalar_result
    mock_session.commit = AsyncMock()

    await checker._catch_up_missed_deadlines()

    for session in expired:
        assert session.status == "expired"
        assert session.finished_by == "deadline"
        assert session.ended_at is not None
    mock_session.commit.assert_awaited_once()


async def test_check_and_finish_expired(
    checker: DeadlineChecker,
    mock_session: AsyncMock,
    mock_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    expired = [_make_expired_session()]
    scalar_result = MagicMock()
    scalar_result.scalars.return_value.all.return_value = expired
    mock_session.execute.return_value = scalar_result
    mock_session.commit = AsyncMock()

    await checker._check_and_finish_expired()

    assert expired[0].status == "expired"
    assert expired[0].finished_by == "deadline"
    mock_session.commit.assert_awaited_once()


async def test_no_expired_attempts_skips_commit(
    checker: DeadlineChecker,
    mock_session: AsyncMock,
) -> None:
    scalar_result = MagicMock()
    scalar_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = scalar_result
    mock_session.commit = AsyncMock()

    await checker._check_and_finish_expired()

    mock_session.commit.assert_not_called()
