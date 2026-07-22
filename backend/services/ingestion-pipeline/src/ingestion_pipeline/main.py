"""ingestion-pipeline FastAPI application: upload, status, health, metrics."""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from exambrain_shared.logging import configure_logging
from ingestion_pipeline.routers import papers, status, upload

SERVICE_NAME = "ingestion-pipeline"
SERVICE_VERSION = "0.1.0"

configure_logging()

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)

app.include_router(papers.router)
app.include_router(upload.router)
app.include_router(status.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Prometheus metrics exposition."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
