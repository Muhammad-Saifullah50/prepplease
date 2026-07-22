"""Status polling endpoint tests (FR-012, FR-023)."""

import uuid

import httpx
import pytest

from ingestion_pipeline.main import app

TEST_USER = {"id": uuid.uuid4(), "clerk_id": "user_test123"}


@pytest.fixture(autouse=True)
def override_auth():
    from ingestion_pipeline.auth import require_auth

    app.dependency_overrides[require_auth] = lambda: TEST_USER
    yield
    app.dependency_overrides.clear()


async def test_status_unknown_paper() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/v1/papers/{uuid.uuid4()}/status"
        )
    assert response.status_code == 404


async def test_status_unauthorized() -> None:
    app.dependency_overrides.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/v1/papers/{uuid.uuid4()}/status"
        )
    assert response.status_code == 401
