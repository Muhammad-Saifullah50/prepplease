# Quickstart: Project Scaffold

**Feature**: 001-project-scaffold | **Date**: 2026-07-20

## Prerequisites

- Docker + Docker Compose v2
- [uv](https://docs.astral.sh/uv/) (for local dev outside containers)
- Python 3.12 (uv installs it automatically via `.python-version`)

## 1. Run the full stack

```bash
cd backend/infra/docker
docker compose up --build
```

Expect 6 healthy containers within 60 seconds: `course-core`, `ingestion-pipeline`, `exam-simulation`, `postgres`, `redis`, `otel-collector`.

Verify health endpoints:

```bash
curl http://localhost:8001/health   # {"status":"ok","service":"course-core","version":"0.1.0"}
curl http://localhost:8002/health   # {"status":"ok","service":"ingestion-pipeline","version":"0.1.0"}
curl http://localhost:8003/health   # {"status":"ok","service":"exam-simulation","version":"0.1.0"}
curl http://localhost:8001/metrics  # Prometheus text format
```

Hot reload: edit any file under `backend/services/*/src/` or `backend/shared/src/` — the affected service restarts automatically.

## 2. Local development (no Docker)

```bash
cd backend
uv sync                 # installs the whole workspace + dev deps
uv run uvicorn course_core.main:app --port 8001 --reload
```

## 3. Quality gates

```bash
cd backend
uv run pre-commit install          # once, installs the git hook
uv run pre-commit run --all-files  # ruff check, ruff format, mypy, secret scan, hygiene hooks
uv run pytest --cov --cov-fail-under=80  # coverage sources (all backend packages) configured in pyproject.toml
```

## 4. Environment variables

Copy per-service examples; never commit real values (`.env` is gitignored):

```bash
cp services/course-core/.env.example services/course-core/.env
```

Key variables: `LOG_LEVEL` (default `INFO`), `DATABASE_URL`, `REDIS_URL`, `OTEL_EXPORTER_OTLP_ENDPOINT`. AWS/LLM variables may stay empty — stubs raise only when the operation is invoked.

## 5. Databases & migrations

The single PostgreSQL container hosts `course_core`, `ingestion`, and `exam_sim` (created at init). Each service has its own alembic scaffold:

```bash
cd backend/services/course-core
uv run alembic revision -m "example" # no models yet — versions/ is empty in this feature
```

## 6. CI

Push a branch or open a PR against `main` — GitHub Actions runs **lint** (pre-commit) and **test** (pytest with 80% coverage gate). Both must be green; branch protection is not configured in this feature.

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `port is already allocated` | Free ports 8001-8003, 5432, 6379, 4317-4318 or stop the conflicting stack |
| `docker: command not found` | Install Docker; Compose v2 required |
| S3/LLM/IAM calls raise `NotConfiguredError` | Expected without AWS credentials — configure env vars only when those features land |
| pre-commit blocks commit on `.env` | Working as intended (secret detection) — keep secrets out of git |
