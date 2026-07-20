"""ingestion-pipeline FastAPI application: /health and /metrics."""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from exambrain_shared.logging import configure_logging

SERVICE_NAME = "ingestion-pipeline"
SERVICE_VERSION = "0.1.0"

configure_logging()

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check (FR-003)."""
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Prometheus metrics exposition (FR-004)."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
