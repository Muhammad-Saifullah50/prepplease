# ingestion-pipeline production image — build context: backend/ workspace root
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Workspace metadata + lockfile first for layer caching
COPY pyproject.toml uv.lock .python-version ./
COPY shared/pyproject.toml shared/pyproject.toml
COPY services/course-core/pyproject.toml services/course-core/pyproject.toml
COPY services/ingestion-pipeline/pyproject.toml services/ingestion-pipeline/pyproject.toml
COPY services/exam-simulation/pyproject.toml services/exam-simulation/pyproject.toml

# Source
COPY shared/src shared/src
COPY services/course-core/src services/course-core/src
COPY services/ingestion-pipeline/src services/ingestion-pipeline/src
COPY services/exam-simulation/src services/exam-simulation/src

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "ingestion_pipeline.main:app", "--host", "0.0.0.0", "--port", "8000"]
