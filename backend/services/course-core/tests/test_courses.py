"""Course CRUD endpoint tests (FR-005, FR-006, FR-007)."""

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


async def test_create_course() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/courses",
            json={"title": "CS301 - Data Structures", "code": "CS301"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "CS301 - Data Structures"
    assert "id" in data


async def test_list_courses() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/courses")
    assert response.status_code == 200
    data = response.json()
    assert "courses" in data


async def test_unauthorized() -> None:
    app.dependency_overrides.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/courses")
    assert response.status_code == 401


async def test_get_unknown_course() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/v1/courses/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_blueprint_history_empty() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/v1/courses/{uuid.uuid4()}/blueprints")
    assert response.status_code == 200
    data = response.json()
    assert "blueprints" in data
