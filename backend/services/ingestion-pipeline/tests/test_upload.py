"""Upload endpoint tests (FR-008, FR-009, FR-010, FR-011)."""

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


@pytest.mark.xfail(reason="S3 not available in test environment")
async def test_upload_pdf_success() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/v1/courses/{uuid.uuid4()}/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")},
        )
    assert response.status_code == 202
    data = response.json()
    assert "paper_id" in data
    assert data["status"] == "pending"
    assert data["duplicate"] is False


async def test_upload_unsupported_type() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/v1/courses/{uuid.uuid4()}/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 415


async def test_upload_unauthorized() -> None:
    app.dependency_overrides.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/v1/courses/{uuid.uuid4()}/upload",
            files={"file": ("test.pdf", b"%PDF", "application/pdf")},
        )
    assert response.status_code == 401
