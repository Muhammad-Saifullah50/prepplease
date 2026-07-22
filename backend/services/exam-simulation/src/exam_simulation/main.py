"""exam-simulation FastAPI application: attempt lifecycle + /health + /metrics."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from exambrain_shared.db import get_session_factory
from exambrain_shared.logging import configure_logging

from exam_simulation.routers import attempts, focus
from exam_simulation.services.deadline_checker import DeadlineChecker

SERVICE_NAME = "exam-simulation"
SERVICE_VERSION = "0.1.0"

configure_logging()

deadline_checker: DeadlineChecker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global deadline_checker
    session_factory = get_session_factory()
    deadline_checker = DeadlineChecker(session_factory)
    await deadline_checker.start()
    yield
    if deadline_checker is not None:
        await deadline_checker.stop()


app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION, lifespan=lifespan)

app.include_router(attempts.router)
app.include_router(focus.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check (FR-003)."""
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Prometheus metrics exposition (FR-004)."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
