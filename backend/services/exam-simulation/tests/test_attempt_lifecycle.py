"""Unit tests for attempt lifecycle (start, save, submit, time limits)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from exambrain_shared.config import get_settings
from exambrain_shared.models.exam_sim import ExamSession, GeneratedExamRow
from exambrain_shared.redis import AttemptStateCache
from exam_simulation.services.attempt_lifecycle import AttemptLifecycle


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_cache() -> AsyncMock:
    return AsyncMock(spec=AttemptStateCache)


@pytest.fixture
def lifecycle(mock_db: AsyncMock, mock_cache: AsyncMock) -> AttemptLifecycle:
    return AttemptLifecycle(mock_db, mock_cache)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def course_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def exam_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_generated_exam_row(**kwargs: object) -> GeneratedExamRow:
    row = MagicMock(spec=GeneratedExamRow)
    row.id = kwargs.get("id", uuid.uuid4())
    row.course_id = kwargs.get("course_id", uuid.uuid4())
    row.content = kwargs.get("content", {"sections": []})
    row.status = kwargs.get("status", "ready")
    row.time_limit_minutes = kwargs.get("time_limit_minutes", 180)
    return row


def _make_exam_session(**kwargs: object) -> ExamSession:
    session = MagicMock(spec=ExamSession)
    session.id = kwargs.get("id", uuid.uuid4())
    session.user_id = kwargs.get("user_id", uuid.uuid4())
    session.course_id = kwargs.get("course_id", uuid.uuid4())
    session.status = kwargs.get("status", "active")
    session.started_at = kwargs.get("started_at", datetime.now(timezone.utc))
    session.deadline = kwargs.get("deadline")
    session.ended_at = kwargs.get("ended_at")
    session.finished_by = kwargs.get("finished_by")
    session.time_limit_minutes = kwargs.get("time_limit_minutes", 180)
    session.answers = kwargs.get("answers", {})
    session.focus_violations = kwargs.get("focus_violations", 0)
    session.exam_content = kwargs.get("exam_content", {"sections": []})
    return session


async def test_start_attempt_success(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
) -> None:
    exam_row = _make_generated_exam_row(id=exam_id, course_id=course_id, time_limit_minutes=120)
    # first execute (_find_active) → no active attempt
    no_active = MagicMock()
    no_active.scalar_one_or_none.return_value = None
    # second execute (exam lookup) → found
    found_exam = MagicMock()
    found_exam.scalar_one_or_none.return_value = exam_row
    mock_db.execute.side_effect = [no_active, found_exam]
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    session = await lifecycle.start(user_id, exam_id, course_id)

    assert session is not None
    assert session.time_limit_minutes == 120


async def test_start_attempt_duplicate_active_rejected(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
) -> None:
    existing = _make_exam_session(user_id=user_id, course_id=course_id, status="active")
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = existing
    mock_db.execute.return_value = scalar_result

    result = await lifecycle.start(user_id, exam_id, course_id)

    assert result is existing


async def test_start_attempt_exam_not_found(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
) -> None:
    no_active = MagicMock()
    no_active.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = no_active

    no_exam = MagicMock()
    no_exam.scalar_one_or_none.return_value = None

    def side_effect(*args: object, **kwargs: object) -> MagicMock:
        return no_exam

    mock_db.execute.side_effect = [no_active, no_exam]

    with pytest.raises(ValueError, match="Generated exam not found or not available"):
        await lifecycle.start(user_id, exam_id, course_id)


async def test_save_answers_partial_upsert(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    mock_cache: AsyncMock,
    user_id: uuid.UUID,
) -> None:
    attempt_id = uuid.uuid4()
    session = _make_exam_session(
        id=attempt_id, user_id=user_id, status="active", answers={"1": "old answer"}
    )

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = session
    mock_db.execute.return_value = scalar_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    mock_cache.set_state = AsyncMock()

    result = await lifecycle.save_answers(attempt_id, user_id, {"1": "updated", "2": "new"})

    assert result.answers == {"1": "updated", "2": "new"}
    mock_db.commit.assert_awaited_once()
    mock_cache.set_state.assert_awaited_once()


async def test_save_answers_non_active_rejected(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
) -> None:
    attempt_id = uuid.uuid4()
    session = _make_exam_session(id=attempt_id, user_id=user_id, status="submitted")
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = session
    mock_db.execute.return_value = scalar_result

    with pytest.raises(ValueError, match="Attempt is not active"):
        await lifecycle.save_answers(attempt_id, user_id, {"1": "answer"})


async def test_manual_submit_active_attempt(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    mock_cache: AsyncMock,
    user_id: uuid.UUID,
) -> None:
    attempt_id = uuid.uuid4()
    session = _make_exam_session(id=attempt_id, user_id=user_id, status="active", ended_at=None)

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = session
    mock_db.execute.return_value = scalar_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_cache.invalidate = AsyncMock()

    result = await lifecycle.finish(attempt_id, user_id, finished_by="manual")

    assert result.status == "submitted"
    assert result.finished_by == "manual"
    assert result.ended_at is not None
    mock_cache.invalidate.assert_awaited_once()


async def test_manual_submit_already_finished_idempotent(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
) -> None:
    attempt_id = uuid.uuid4()
    ended = datetime.now(timezone.utc)
    session = _make_exam_session(
        id=attempt_id, user_id=user_id, status="submitted", finished_by="deadline", ended_at=ended
    )

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = session
    mock_db.execute.return_value = scalar_result

    result = await lifecycle.finish(attempt_id, user_id, finished_by="manual")

    assert result.ended_at == ended  # unchanged


async def test_attempt_start_time_limit_from_exam(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
) -> None:
    exam_row = _make_generated_exam_row(id=exam_id, course_id=course_id, time_limit_minutes=180)
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = None  # no active
    mock_db.execute.side_effect = [MagicMock(scalar_one_or_none=lambda: None), MagicMock(scalar_one_or_none=lambda: exam_row)]
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    session = await lifecycle.start(user_id, exam_id, course_id)

    assert session.time_limit_minutes == 180


async def test_attempt_start_default_fallback(
    lifecycle: AttemptLifecycle,
    mock_db: AsyncMock,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    exam_id: uuid.UUID,
) -> None:
    exam_row = _make_generated_exam_row(id=exam_id, course_id=course_id, time_limit_minutes=None)
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = None  # no active
    mock_db.execute.side_effect = [MagicMock(scalar_one_or_none=lambda: None), MagicMock(scalar_one_or_none=lambda: exam_row)]
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    session = await lifecycle.start(user_id, exam_id, course_id)

    default = get_settings().exam_attempt_default_timeout_minutes
    assert session.time_limit_minutes == default
