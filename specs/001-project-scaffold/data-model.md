# Data Model: Project Scaffold

**Feature**: 001-project-scaffold | **Date**: 2026-07-20

This feature is infrastructure scaffolding — no domain entities or database tables are created. The "entities" below are structural/configuration artifacts.

## Service

A FastAPI microservice; independently deployable workspace member.

| Field | Value / Rule |
|---|---|
| name | `course-core` \| `ingestion-pipeline` \| `exam-simulation` |
| package | `course_core` \| `ingestion_pipeline` \| `exam_simulation` |
| port | 8001 \| 8002 \| 8003 (FR-011) |
| database | `course_core` \| `ingestion` \| `exam_sim` (FR-015a) |
| version | `0.1.0` (reported by `/health`) |
| base image | `python:3.12-slim` (FR-010) |
| required files | `pyproject.toml`, `Dockerfile`, `Dockerfile.dev`, `.env.example`, `alembic.ini`, `alembic/env.py` (FR-002, FR-015) |

**Validation rules**: health payload must be exactly `{"status": "ok", "service": "<name>", "version": "0.1.0"}` (FR-003); default log level INFO, overridable via `LOG_LEVEL` (FR-016).

## Shared Library (`exambrain-shared`)

| Module | Responsibility | Failure semantics |
|---|---|---|
| `config.py` | pydantic-settings `Settings` (LOG_LEVEL, DATABASE_URL, REDIS_URL, AWS/LLM config, service metadata) | Missing optional config → fields default to `None`; never raises at import |
| `logging.py` | structlog JSON configuration | None |
| `iam.py` | IAM validation stub | Ops raise `NotConfiguredError` at call time (FR-017) |
| `llm.py` | LiteLLM client stub | Ops raise `NotConfiguredError` at call time (FR-017) |
| `s3.py` | S3 adapter stub | Ops raise `NotConfiguredError` at call time (FR-017) |
| `db.py` | Async engine/session factory, `DeclarativeBase` | Engine created lazily; no connection at import |

**State transition (stubs)**: `Unconfigured → (operation called) → NotConfiguredError` / `Configured → (operation called) → delegates` (delegation bodies deferred to future features).

## Agent Package

Empty namespace placeholders (FR-018): `agents/{parsing,alignment,blueprint,generator,evaluation}/__init__.py`. No fields, no logic, not workspace members.

## Infrastructure Components (docker-compose)

| Component | Image | Ports | Notes |
|---|---|---|---|
| course-core | build `Dockerfile.dev` | 8001:8000 | src volume mounts, `--reload` |
| ingestion-pipeline | build `Dockerfile.dev` | 8002:8000 | src volume mounts, `--reload` |
| exam-simulation | build `Dockerfile.dev` | 8003:8000 | src volume mounts, `--reload` |
| postgres | `pgvector/pgvector:pg17` | 5432 | init script creates 3 DBs + vector ext; healthcheck `pg_isready` |
| redis | `redis:7-alpine` | 6379 | healthcheck `redis-cli ping` |
| otel-collector | `otel/opentelemetry-collector-contrib` | 4317, 4318 | debug exporter only |

**Relationships**: services `depends_on` postgres (healthy) and redis (healthy); each service → its own database within the single postgres instance; all services → otel-collector via `OTEL_EXPORTER_OTLP_ENDPOINT`.
