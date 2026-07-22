"""Dashboard endpoint tests (FR-014, FR-015, FR-016)."""

import uuid

import httpx
import pytest

from course_core.main import app

TEST_USER = {
    "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
    "clerk_id": "user_test123",
}


@pytest.fixture(autouse=True)
def override_auth():
    from course_core.auth import resolve_current_user

    app.dependency_overrides[resolve_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.clear()


async def test_dashboard_summary_returns_courses() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert "courses" in data


async def test_dashboard_unauthorized() -> None:
    app.dependency_overrides.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/dashboard/summary")
    assert response.status_code == 401


async def test_performance_unknown_course() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/v1/courses/{uuid.uuid4()}/performance")
    assert response.status_code == 404


async def test_blueprint_unknown_course() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/v1/courses/{uuid.uuid4()}/blueprint")
    assert response.status_code == 404
