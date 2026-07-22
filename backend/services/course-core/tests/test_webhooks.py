"""Clerk webhook endpoint tests (FR-002, FR-021)."""

import httpx

from course_core.main import app


async def test_webhook_missing_headers() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/webhooks/clerk", json={})
    assert response.status_code == 401


async def test_webhook_unknown_event() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/webhooks/clerk",
            json={"type": "unknown.event", "data": {"id": "user_test"}},
            headers={
                "svix-id": "test",
                "svix-timestamp": "1234567890",
                "svix-signature": "v1,test",
            },
        )
    assert response.status_code == 422 or response.status_code == 401
