"""User profile endpoint tests (FR-004)."""

import uuid

import httpx
import pytest

from course_core.main import app

TEST_USER = {
    "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
    "clerk_id": "user_test123",
    "email": "test@example.com",
    "display_name": "Test User",
    "preferences": {},
}


@pytest.fixture(autouse=True)
def override_auth():
    from course_core.auth import resolve_current_user

    app.dependency_overrides[resolve_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.clear()


async def test_get_profile() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["clerk_id"] == "user_test123"
    assert "email" in data


async def test_update_profile() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/v1/users/me",
            json={"display_name": "Updated Name"},
        )
    assert response.status_code == 200


async def test_profile_unauthorized() -> None:
    app.dependency_overrides.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/users/me")
    assert response.status_code == 401
