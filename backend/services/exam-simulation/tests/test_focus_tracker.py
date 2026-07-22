"""Unit tests for focus violation tracking and lockout."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from exambrain_shared.models.exam_sim import ExamSession
from exambrain_shared.redis import AttemptStateCache
from exam_simulation.services.focus_tracker import FocusTracker


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_cache() -> AsyncMock:
    cache = AsyncMock(spec=AttemptStateCache)
    cache.invalidate = AsyncMock()
    return cache


@pytest.fixture
def tracker(mock_db: AsyncMock, mock_cache: AsyncMock) -> FocusTracker:
    return FocusTracker(mock_db, mock_cache)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_session(**kwargs: object) -> MagicMock:
    session = MagicMock(spec=ExamSession)
    session.id = kwargs.get("id", uuid.uuid4())
    session.user_id = kwargs.get("user_id", uuid.uuid4())
    session.status = kwargs.get("status", "active")
    session.focus_violations = kwargs.get("focus_violations", 0)
    session.ended_at = kwargs.get("ended_at")
    session.finished_by = kwargs.get("finished_by")
    return session


async def test_focus_violation_under_limit(
    tracker: FocusTracker,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
) -> None:
    attempt_id = uuid.uuid4()
    session = _make_session(id=attempt_id, user_id=user_id, status="active", focus_violations=0)

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = session
    mock_db.execute.return_value = scalar_result
    mock_db.commit = AsyncMock()

    response = await tracker.report_violation(attempt_id, user_id)

    assert response.focus_violations == 1
    assert response.status == "active"
    assert response.violations_remaining >= 1
    mock_db.commit.assert_awaited_once()


async def test_focus_violation_cross_limit_lockout(
    tracker: FocusTracker,
    mock_db: AsyncMock,
    mock_cache: AsyncMock,
    user_id: uuid.UUID,
) -> None:
    attempt_id = uuid.uuid4()
    session = _make_session(
        id=attempt_id, user_id=user_id, status="active", focus_violations=2
    )

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = session
    mock_db.execute.return_value = scalar_result
    mock_db.commit = AsyncMock()

    response = await tracker.report_violation(attempt_id, user_id)

    assert response.focus_violations == 3
    assert response.status == "locked_out"
    assert response.finished_by == "lockout"
    assert response.violations_remaining == 0
    assert response.ended_at is not None
    mock_cache.invalidate.assert_awaited_once_with(str(attempt_id))


async def test_focus_violation_non_active_rejected(
    tracker: FocusTracker,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
) -> None:
    attempt_id = uuid.uuid4()
    session = _make_session(id=attempt_id, user_id=user_id, status="submitted")

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = session
    mock_db.execute.return_value = scalar_result

    with pytest.raises(ValueError, match="Attempt is not active"):
        await tracker.report_violation(attempt_id, user_id)
