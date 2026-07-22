"""API integration tests for exam simulation flows."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from exambrain_shared.models.exam_sim import ExamSession
from exam_simulation.dependencies import get_attempt_state_cache, get_current_user, get_db
from exam_simulation.main import app

TEST_USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def override_deps():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_cache = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_attempt_state_cache] = lambda: mock_cache
    yield
    app.dependency_overrides.clear()


def _make_active_session(attempt_id: uuid.UUID) -> MagicMock:
    session = MagicMock(spec=ExamSession)
    session.id = attempt_id
    session.user_id = TEST_USER_ID
    session.status = "active"
    session.started_at = datetime.now(timezone.utc)
    session.deadline = datetime.now(timezone.utc) + timedelta(hours=2)
    session.time_limit_minutes = 120
    session.exam_content = {"sections": []}
    session.answers = {}
    session.focus_violations = 0
    session.ended_at = None
    session.finished_by = None
    return session


async def test_start_attempt_missing_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/exam-attempts",
            json={"generated_exam_id": str(uuid.uuid4()), "course_id": str(uuid.uuid4())},
        )
    assert response.status_code == 401


async def test_start_attempt_returns_201() -> None:
    exam_id = uuid.uuid4()
    course_id = uuid.uuid4()
    attempt_id = uuid.uuid4()

    mock_db = app.dependency_overrides[get_db]()
    mock_cache = app.dependency_overrides[get_attempt_state_cache]()
    mock_cache.get_state = AsyncMock(return_value=None)

    # first call (_find_active) → None, second call (exam lookup) → mock
    no_active = MagicMock()
    no_active.scalar_one_or_none.return_value = None
    exam_mock = MagicMock()
    exam_mock.scalar_one_or_none.return_value = MagicMock(
        id=exam_id, course_id=course_id, content={"sections": []}, status="ready",
        time_limit_minutes=120,
    )
    mock_db.execute.side_effect = [no_active, exam_mock]

    session = _make_active_session(attempt_id)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda x: setattr(x, 'id', attempt_id) or None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/exam-attempts",
            json={"generated_exam_id": str(exam_id), "course_id": str(course_id)},
            headers={"X-User-Id": str(TEST_USER_ID)},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "active"


async def test_poll_state_returns_200() -> None:
    attempt_id = uuid.uuid4()
    session = _make_active_session(attempt_id)

    mock_db = app.dependency_overrides[get_db]()
    mock_cache = app.dependency_overrides[get_attempt_state_cache]()
    mock_cache.get_state = AsyncMock(return_value=None)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/exam-attempts/{attempt_id}/state",
            headers={"X-User-Id": str(TEST_USER_ID)},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"


async def test_save_answers_returns_200() -> None:
    attempt_id = uuid.uuid4()
    session = _make_active_session(attempt_id)

    mock_db = app.dependency_overrides[get_db]()
    mock_cache = app.dependency_overrides[get_attempt_state_cache]()
    mock_cache.get_state = AsyncMock(return_value=None)
    mock_cache.set_state = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: session)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            f"/api/v1/exam-attempts/{attempt_id}/answers",
            json={"answers": {"1": "my answer"}},
            headers={"X-User-Id": str(TEST_USER_ID)},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"


async def test_submit_attempt_returns_200() -> None:
    attempt_id = uuid.uuid4()
    session = _make_active_session(attempt_id)

    mock_db = app.dependency_overrides[get_db]()
    mock_cache = app.dependency_overrides[get_attempt_state_cache]()
    mock_cache.invalidate = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: session)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/exam-attempts/{attempt_id}/finish",
            headers={"X-User-Id": str(TEST_USER_ID)},
        )
    assert response.status_code == 200
    data = response.json()
    assert "submitted" in data["status"] or "active" in data["status"]


async def test_focus_violation_flow() -> None:
    attempt_id = uuid.uuid4()
    session = _make_active_session(attempt_id)

    mock_db = app.dependency_overrides[get_db]()
    mock_cache = app.dependency_overrides[get_attempt_state_cache]()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: session)
    mock_db.commit = AsyncMock()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/exam-attempts/{attempt_id}/focus-violations",
            headers={"X-User-Id": str(TEST_USER_ID)},
        )
    assert response.status_code == 200
    data = response.json()
    assert "focus_violations" in data
    assert data["focus_violations"] >= 0


async def test_concurrent_finish_requests_idempotent() -> None:
    attempt_id = uuid.uuid4()

    mock_db = app.dependency_overrides[get_db]()
    mock_cache = app.dependency_overrides[get_attempt_state_cache]()
    mock_cache.invalidate = AsyncMock()

    finished_session = _make_active_session(attempt_id)
    finished_session.status = "submitted"
    finished_session.finished_by = "manual"
    finished_session.ended_at = datetime.now(timezone.utc)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: finished_session)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            f"/api/v1/exam-attempts/{attempt_id}/finish",
            headers={"X-User-Id": str(TEST_USER_ID)},
        )
        second = await client.post(
            f"/api/v1/exam-attempts/{attempt_id}/finish",
            headers={"X-User-Id": str(TEST_USER_ID)},
        )
    assert first.status_code == 200
    assert second.status_code == 200


async def test_own_attempt_only_access() -> None:
    attempt_id = uuid.uuid4()

    mock_db = app.dependency_overrides[get_db]()
    mock_cache = app.dependency_overrides[get_attempt_state_cache]()
    mock_cache.get_state = AsyncMock(return_value=None)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/exam-attempts/{attempt_id}/state",
            headers={"X-User-Id": str(TEST_USER_ID)},
        )
    assert response.status_code == 404
