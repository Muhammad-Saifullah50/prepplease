# ingestion-pipeline production image — build context: backend/ workspace root
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# tesseract binary for local OCR of scanned PDFs (Phase 2 agents, research R3)
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Workspace metadata + lockfile first for layer caching
COPY pyproject.toml uv.lock .python-version ./
COPY shared/pyproject.toml shared/pyproject.toml
COPY services/course-core/pyproject.toml services/course-core/pyproject.toml
COPY services/ingestion-pipeline/pyproject.toml services/ingestion-pipeline/pyproject.toml
COPY services/exam-simulation/pyproject.toml services/exam-simulation/pyproject.toml
COPY agents/pyproject.toml agents/pyproject.toml

# Source
COPY shared/src shared/src
COPY services/course-core/src services/course-core/src
COPY services/ingestion-pipeline/src services/ingestion-pipeline/src
COPY services/exam-simulation/src services/exam-simulation/src
COPY agents/src agents/src

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "ingestion_pipeline.main:app", "--host", "0.0.0.0", "--port", "8000"]
