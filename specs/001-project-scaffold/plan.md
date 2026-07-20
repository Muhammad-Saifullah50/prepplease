# Implementation Plan: Project Scaffold

**Branch**: `001-project-scaffold` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-project-scaffold/spec.md`

## Summary

Bootstrap the ExamBrain backend monorepo: a `uv` workspace under `backend/` containing three FastAPI microservices (course-core :8001, ingestion-pipeline :8002, exam-simulation :8003), a `shared/` library (config, logging, IAM/LiteLLM/S3 stubs, DB base), empty `agents/` packages, Docker Compose orchestration (services + PostgreSQL 17 pgvector + Redis 7 + OTel collector), pre-commit quality gates (ruff, mypy strict, secret detection), and a GitHub Actions CI pipeline (lint + pytest with 80% coverage over `backend/`). Everything is scaffold-level: health/metrics endpoints, deferred-error stubs, alembic skeletons per service — no business logic.

## Technical Context

**Language/Version**: Python 3.12 (pinned via `.python-version`, `python:3.12-slim` base images)
**Primary Dependencies**: FastAPI, uvicorn, pydantic v2 + pydantic-settings, SQLAlchemy 2 (async) + asyncpg, alembic, redis-py (async), litellm (stub wiring only), boto3/aioboto3 (stub wiring only), prometheus-client, structlog (JSON logging)
**Package/Workspace Manager**: `uv` workspace — root `backend/pyproject.toml` with members `services/*` and `shared`
**Storage**: Single PostgreSQL 17 + pgvector container hosting 3 databases (`course_core`, `ingestion`, `exam_sim`) created via init script; Redis 7 for cache/event bus (provisioned only, unused in this feature)
**Testing**: pytest + pytest-asyncio + pytest-cov + httpx (ASGI transport); coverage ≥80% over all `backend/` code
**Target Platform**: Linux containers (Docker Compose local dev; K3s/OCI later — out of scope here)
**Project Type**: Backend monorepo (uv workspace, 3 services + shared lib)
**Performance Goals**: Stack healthy < 60s after `docker compose up --build`; all health endpoints respond < 10s after start; CI < 5 min; pre-commit < 30s
**Constraints**: Zero-cost infra (fits Oracle Always Free RAM budget), async-only I/O, no secrets in repo, mypy strict, hot reload in dev images
**Scale/Scope**: Scaffold only — 3 services, 1 shared package, 5 empty agent packages, no business endpoints beyond `/health` and `/metrics`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. SDD | ✅ PASS | Spec → this plan → tasks; PHR recorded per interaction |
| II. Zero-cost infra | ✅ PASS | Local Docker Compose only; PG+Redis+OTel+3 slim services fit ~2.4GB target |
| III. Agent isolation | ✅ PASS | Agents scaffolded as empty isolated packages; no coupling introduced |
| IV. Async-first | ✅ PASS | asyncpg, async SQLAlchemy, httpx, async redis; no sync I/O in request paths |
| V. LLM abstraction | ✅ PASS | Single `shared/llm.py` LiteLLM stub; provider/model via env config only |
| VI. TDD critical paths | ✅ PASS | No critical-path logic in this feature; scaffold tests ship with feature to hit 80% coverage (FR-009a) |
| VII. Repository pattern | ✅ PASS | `shared/db.py` provides declarative base + session factory; no raw SQL anywhere; schema changes via alembic scaffolds |
| VIII. Code quality | ⚠️ DEVIATION (justified) | Constitution names `black` for formatting; spec FR-008/FR-012 mandate `ruff format`. Ruff's formatter is a black-compatible drop-in (line length 88 retained). See Complexity Tracking. |
| IX. Security by default | ✅ PASS | `.env` gitignored, detect-private-key hook, pydantic validation; `/health` + `/metrics` are the explicit public whitelist (no auth infra exists yet — JWT is future scope per constitution) |
| X. Observability | ✅ PASS | structlog JSON logging, `/health` per service, `/metrics` Prometheus, OTel collector sidecar provisioned |

**Post-Phase-1 re-check**: ✅ PASS — design artifacts introduce no new violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-project-scaffold/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── health-api.yaml  # OpenAPI: /health + /metrics (all 3 services)
└── tasks.md             # Phase 2 output (/sp.tasks — NOT created by /sp.plan)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml               # uv workspace root: members = services/*, shared
├── .python-version              # 3.12
├── .pre-commit-config.yaml
├── shared/
│   ├── pyproject.toml
│   └── src/exambrain_shared/
│       ├── __init__.py
│       ├── config.py            # pydantic-settings BaseSettings (LOG_LEVEL etc.)
│       ├── logging.py           # structlog JSON config, INFO default
│       ├── iam.py               # IAM validation stub (deferred errors)
│       ├── llm.py               # LiteLLM client stub (deferred errors)
│       ├── s3.py                # S3 adapter stub (deferred errors)
│       └── db.py                # async engine/session factory + DeclarativeBase
├── services/
│   ├── course-core/
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── Dockerfile.dev
│   │   ├── .env.example
│   │   ├── alembic.ini
│   │   ├── alembic/
│   │   │   ├── env.py           # async engine, targets course_core DB
│   │   │   └── versions/.gitkeep
│   │   ├── src/course_core/
│   │   │   ├── __init__.py
│   │   │   └── main.py          # FastAPI app: /health, /metrics
│   │   └── tests/
│   │       └── test_health.py
│   ├── ingestion-pipeline/      # same layout, pkg ingestion_pipeline, DB ingestion
│   └── exam-simulation/         # same layout, pkg exam_simulation, DB exam_sim
├── agents/
│   ├── parsing/__init__.py
│   ├── alignment/__init__.py
│   ├── blueprint/__init__.py
│   ├── generator/__init__.py
│   └── evaluation/__init__.py
├── tests/
│   ├── test_config.py           # shared config loading
│   └── test_stubs.py            # deferred-error behavior of iam/llm/s3 stubs
└── infra/
    └── docker/
        ├── docker-compose.yml   # 3 services + pg + redis + otel-collector
        ├── postgres/init-databases.sh   # creates course_core, ingestion, exam_sim
        └── otel/otel-collector-config.yaml

.github/
└── workflows/
    └── ci.yml                   # lint (pre-commit) + test (pytest --cov, ≥80%)

.gitignore                       # python, venvs, IDE, docker, .env
```

**Structure Decision**: uv workspace monorepo rooted at `backend/` (FR-001). Each service is a workspace member with `src/` layout for clean packaging; `shared` is a workspace member imported by all services. `agents/` are plain empty packages (not workspace members — no code, no deps yet). Compose and infra configs live under `backend/infra/docker/` per acceptance scenario US1-1. CI workflow at repo-root `.github/workflows/` as GitHub requires.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `ruff format` instead of `black` (Constitution VIII) | Spec FR-008/FR-012 explicitly mandate ruff for lint+format; one tool = faster pre-commit (<30s SC-002) and one fewer CI dep | Running black alongside ruff duplicates formatting tooling; ruff format is byte-compatible with black at line length 88, so the constitutional intent (deterministic black-style formatting) is preserved. Recommend a PATCH constitution amendment to name "ruff format (black-compatible)". |
