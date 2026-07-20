# Research: Project Scaffold

**Feature**: 001-project-scaffold | **Date**: 2026-07-20

No `NEEDS CLARIFICATION` items remained in Technical Context (spec clarifications sessions 2026-07-19/20 resolved all ambiguities). Research below records the technology decisions and their rationale.

## R1: uv workspace layout

- **Decision**: Root `backend/pyproject.toml` declares `[tool.uv.workspace] members = ["services/*", "shared"]`. Each service and `shared` has its own `pyproject.toml`; services depend on `exambrain-shared` via `[tool.uv.sources] exambrain-shared = { workspace = true }`. Single lockfile (`uv.lock`) at workspace root.
- **Rationale**: uv workspaces give one resolved dependency set across services (consistent versions), editable local installs of `shared`, and fast CI installs (`uv sync --frozen`). Matches FR-001.
- **Alternatives considered**: (a) Independent per-service projects with path deps — drift between services, slower CI, no unified lock. (b) Single flat package — breaks independent deployability of services (Key Entities).

## R2: Service package layout

- **Decision**: `src/` layout per service (`services/course-core/src/course_core/`), hyphenated directory names, underscored package names.
- **Rationale**: src layout prevents accidental imports of uninstalled code, standard for uv/hatchling builds; import-safe names required by Python.
- **Alternatives considered**: Flat layout — allows importing from CWD, masks packaging errors.

## R3: FastAPI health/metrics implementation

- **Decision**: Each service `main.py` builds a FastAPI app exposing `GET /health` (static JSON `{"status": "ok", "service": "<name>", "version": "0.1.0"}`) and `GET /metrics` via `prometheus-client`'s `make_asgi_app()` mounted at `/metrics`.
- **Rationale**: FR-003/FR-004; `prometheus-client` ASGI app is the canonical zero-config Prometheus exposition; no DB/Redis checks in health at scaffold stage so services start without dependencies (edge case: missing AWS creds must not break health).
- **Alternatives considered**: `prometheus-fastapi-instrumentator` — richer defaults but extra dep; not needed for scaffold. Deep health checks (DB ping) — deferred; would couple health to infra availability contrary to FR-017's spirit.

## R4: Shared stubs with deferred errors (FR-017)

- **Decision**: `iam.py`, `llm.py`, `s3.py` define classes whose `__init__` only reads config; any operation method raises a domain error (`NotConfiguredError` subclass of `RuntimeError`) at call time when credentials/config are absent. No client construction or network I/O at import/startup.
- **Rationale**: Clarification 2026-07-19 mandates runtime-deferred failures; services must boot and pass health checks with zero AWS config.
- **Alternatives considered**: Lazy client with startup validation — fails startup, rejected by clarification. `NotImplementedError` — semantically wrong (it's unconfigured, not unimplemented).

## R5: Logging

- **Decision**: `structlog` configured for JSON output in `shared/logging.py`; level from `LOG_LEVEL` env var, default `INFO` (FR-016). Uvicorn access logs left standard.
- **Rationale**: Constitution X requires structured JSON logging; structlog is the de-facto async-friendly choice and integrates with stdlib logging for uvicorn.
- **Alternatives considered**: `python-json-logger` on stdlib — workable but weaker context-binding; `loguru` — non-stdlib model, poorer mypy strict support.

## R6: Database topology & init

- **Decision**: One `pgvector/pgvector:pg17` container; `/docker-entrypoint-initdb.d/init-databases.sh` creates `course_core`, `ingestion`, `exam_sim` databases and enables the `vector` extension in each. Each service's `DATABASE_URL` points at its own DB.
- **Rationale**: FR-006/FR-015a; single instance conserves the zero-cost RAM budget while separate databases preserve service isolation (Constitution III/VII). Official pgvector image ships PG17 + extension.
- **Alternatives considered**: Three PG containers — ~3× RAM, violates zero-cost mandate. Single shared DB with schemas — weaker isolation, cross-service migration hazards.

## R7: Alembic per service, async

- **Decision**: Each service carries `alembic.ini` + `alembic/env.py` configured with `async_engine_from_config` (asyncpg URL from env `DATABASE_URL`, fallback to that service's default), `target_metadata` from the service's (currently empty) model base, empty `versions/`.
- **Rationale**: FR-015; per-service migration history matches per-service databases; async env.py aligns with Constitution IV.
- **Alternatives considered**: Single shared alembic — entangles service schemas, blocks independent deploys.

## R8: Docker images & hot reload

- **Decision**: `Dockerfile` (prod-ish): `python:3.12-slim`, install uv, `uv sync --frozen --no-dev` of the workspace filtered to the service, run `uvicorn <pkg>.main:app`. `Dockerfile.dev`: same base with dev deps, `uvicorn --reload --reload-dir` and compose volume mounts of `backend/services/<svc>/src` and `backend/shared/src` (FR-007).
- **Rationale**: FR-002/FR-010; volume mounts + `--reload` give hot reload (US1-3) including shared-lib changes.
- **Alternatives considered**: `watchfiles` sidecar — uvicorn --reload already uses watchfiles internally. Multi-stage distroless — premature for scaffold.

## R9: OTel collector

- **Decision**: `otel/opentelemetry-collector-contrib` container with minimal config: OTLP receivers on 4317 (gRPC) / 4318 (HTTP), `debug` exporter. Services get `OTEL_EXPORTER_OTLP_ENDPOINT` env; actual SDK instrumentation deferred.
- **Rationale**: FR-006/FR-011 require the sidecar and ports; wiring app-level tracing is beyond scaffold scope.
- **Alternatives considered**: Full instrumentation now — scope creep; no spec requirement.

## R10: Pre-commit & formatting toolchain

- **Decision**: `.pre-commit-config.yaml` with: `ruff check --fix`, `ruff format`, `mypy` (strict, via local hook running `uv run mypy`), `detect-private-key`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files` (FR-008). Line length 88.
- **Rationale**: FR-008/FR-012. `ruff format` is black-compatible at length 88, satisfying Constitution VIII's intent with one tool (see plan Complexity Tracking). mypy as a local hook uses the workspace venv so it sees real dependency types (pre-commit's mirrors-mypy runs in an isolated env missing project deps).
- **Alternatives considered**: black + ruff — duplicate tooling, slower (SC-002 <30s). mirrors-mypy hook — false positives from missing stubs/deps.

## R11: CI pipeline

- **Decision**: `.github/workflows/ci.yml`, triggers `push` to `main` + `pull_request`. Two jobs: **lint** (`astral-sh/setup-uv`, `pre-commit run --all-files` with pre-commit cache) and **test** (`uv sync`, `uv run pytest --cov=backend --cov-fail-under=80`). Test job runs without service containers — scaffold tests use ASGI transport, no live DB needed.
- **Rationale**: FR-009/SC-003/SC-005; uv + cached pre-commit keeps runtime well under 5 min. No branch protection (clarification 2026-07-20).
- **Alternatives considered**: Spinning up compose in CI — slow, unnecessary for scaffold tests; can be added when integration tests exist.

## R12: Test strategy for 80% coverage (FR-009a)

- **Decision**: Tests: (1) per-service `test_health.py` using `httpx.ASGITransport` against the app — asserts `/health` payload and `/metrics` 200; (2) `backend/tests/test_config.py` — settings load, `LOG_LEVEL` default INFO and override; (3) `backend/tests/test_stubs.py` — importing stubs never raises, calling operations without config raises `NotConfiguredError`. Coverage measured over all `backend` packages via `pytest-cov` with `--cov-fail-under=80`.
- **Rationale**: Scaffold code surface is small (health apps, config, logging, stubs, db base); these tests cover the executable lines well above 80%.
- **Alternatives considered**: Testcontainers-based DB tests — no schema exists yet; nothing meaningful to test.
