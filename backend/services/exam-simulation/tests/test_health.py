"""Health/metrics contract tests for exam-simulation (FR-003, FR-004)."""

import httpx

from exam_simulation.main import app


async def test_health_payload() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "exam-simulation",
        "version": "0.1.0",
    }


async def test_metrics_exposition() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert b"python_gc_objects_collected_total" in response.content
