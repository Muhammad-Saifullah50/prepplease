"""course-core FastAPI application: dashboard, courses, users, webhooks, health."""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from course_core import webhooks
from course_core.routers import courses, dashboard, users
from exambrain_shared.logging import configure_logging

SERVICE_NAME = "course-core"
SERVICE_VERSION = "0.1.0"

configure_logging()

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)

app.include_router(webhooks.router)
app.include_router(courses.router)
app.include_router(dashboard.router)
app.include_router(users.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Prometheus metrics exposition."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
