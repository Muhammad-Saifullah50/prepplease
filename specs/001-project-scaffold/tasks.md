# Tasks: Project Scaffold

**Input**: Design documents from `/specs/001-project-scaffold/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/health-api.yaml, quickstart.md

**Tests**: Included — spec FR-009a explicitly requires scaffold tests (health endpoints, config, stub deferred-error behavior) to reach the 80% coverage gate.

**Organization**: Tasks are grouped by user story so each story is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 (local stack), US2 (tests & linting), US3 (CI pipeline)

## Path Conventions

Backend monorepo per plan.md: uv workspace rooted at `backend/` with `services/*`, `shared/`, `agents/`, `tests/`, `infra/docker/`; CI at repo-root `.github/workflows/`.

---

## Phase 1: Setup (Workspace Skeleton)

**Purpose**: Repo hygiene and the uv workspace root every other task builds on.

- [X] T001 Create `.gitignore` at repo root excluding Python artifacts (`__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`), virtualenvs (`.venv/`), IDE files (`.idea/`, `.vscode/`), Docker artifacts, and `.env` files (FR-014)
- [X] T002 Create `backend/.python-version` pinning `3.12` (FR-013)
- [X] T003 Create workspace root `backend/pyproject.toml` with `[tool.uv.workspace] members = ["services/*", "shared"]`, shared dev dependencies (pytest, pytest-asyncio, pytest-cov, httpx, mypy, ruff, pre-commit), `[tool.ruff]` (line-length 88), `[tool.mypy]` (strict), and `[tool.pytest.ini_options]` (asyncio mode auto) per research R1/R10 (FR-001, FR-012)
- [X] T004 [P] Create empty agent packages: `backend/agents/parsing/__init__.py`, `backend/agents/alignment/__init__.py`, `backend/agents/blueprint/__init__.py`, `backend/agents/generator/__init__.py`, `backend/agents/evaluation/__init__.py` — no logic (FR-018)

---

## Phase 2: Foundational (Shared Library)

**Purpose**: The `exambrain-shared` package all three services import. BLOCKS all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create `backend/shared/pyproject.toml` (package `exambrain-shared`, src layout, deps: pydantic, pydantic-settings, structlog, SQLAlchemy 2 async, asyncpg, prometheus-client) and `backend/shared/src/exambrain_shared/__init__.py`
- [X] T006 [P] Implement `backend/shared/src/exambrain_shared/config.py` — pydantic-settings `Settings` with `LOG_LEVEL` (default `"INFO"`), `DATABASE_URL`, `REDIS_URL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, AWS/LLM fields defaulting to `None`; never raises at import (FR-016, data-model Shared Library)
- [X] T007 [P] Implement `backend/shared/src/exambrain_shared/logging.py` — structlog JSON configuration, level from `LOG_LEVEL` env var, default INFO, stdlib integration for uvicorn per research R5 (FR-016)
- [X] T008 [P] Implement `backend/shared/src/exambrain_shared/iam.py`, `llm.py`, and `s3.py` — stub classes whose `__init__` only reads config; every operation method raises `NotConfiguredError(RuntimeError)` at call time when config is absent; no client construction or network I/O at import per research R4 (FR-005, FR-017)
- [X] T009 [P] Implement `backend/shared/src/exambrain_shared/db.py` — lazy async engine/session factory (`create_async_engine` on first use) and SQLAlchemy 2 `DeclarativeBase`; no connection at import (FR-005)
- [X] T010 Run `uv sync` in `backend/` to generate `backend/uv.lock` and verify the workspace resolves (depends on T003, T005)

**Checkpoint**: `exambrain-shared` importable; workspace locks cleanly — user stories can begin.

---

## Phase 3: User Story 1 — Developer Initializes and Runs the Project Locally (Priority: P1) 🎯 MVP

**Goal**: `docker compose up --build` from `backend/infra/docker/` starts 6 healthy containers; each service answers `/health` and `/metrics`; hot reload works.

**Independent Test**: Run `docker compose up --build`; verify all 6 containers healthy within 60s, `curl` ports 8001-8003 `/health` returns the exact FR-003 payload, edit a source file and observe auto-restart.

### Implementation for User Story 1

- [X] T011 [P] [US1] Create course-core service package: `backend/services/course-core/pyproject.toml` (package `course_core`, version 0.1.0, deps: fastapi, uvicorn, alembic, `exambrain-shared` via `[tool.uv.sources] workspace = true`), `src/course_core/__init__.py`, and `src/course_core/main.py` — FastAPI app with `GET /health` returning `{"status": "ok", "service": "course-core", "version": "0.1.0"}` and prometheus-client `make_asgi_app()` mounted at `/metrics`, structlog configured via shared logging (FR-002, FR-003, FR-004; research R3)
- [X] T012 [P] [US1] Create ingestion-pipeline service package: same layout under `backend/services/ingestion-pipeline/` with package `ingestion_pipeline`, service name `ingestion-pipeline` in health payload (FR-002, FR-003, FR-004)
- [X] T013 [P] [US1] Create exam-simulation service package: same layout under `backend/services/exam-simulation/` with package `exam_simulation`, service name `exam-simulation` in health payload (FR-002, FR-003, FR-004)
- [X] T014 [P] [US1] Create alembic scaffold for course-core: `backend/services/course-core/alembic.ini` and `alembic/env.py` using `async_engine_from_config` with asyncpg `DATABASE_URL` from env (fallback `postgresql+asyncpg://…/course_core`), `target_metadata` from shared `DeclarativeBase`, plus `alembic/versions/.gitkeep` (FR-015; research R7)
- [X] T015 [P] [US1] Create alembic scaffold for ingestion-pipeline targeting the `ingestion` database: `backend/services/ingestion-pipeline/alembic.ini`, `alembic/env.py`, `alembic/versions/.gitkeep` (FR-015)
- [X] T016 [P] [US1] Create alembic scaffold for exam-simulation targeting the `exam_sim` database: `backend/services/exam-simulation/alembic.ini`, `alembic/env.py`, `alembic/versions/.gitkeep` (FR-015)
- [X] T017 [P] [US1] Create `.env.example` for each service: `backend/services/course-core/.env.example`, `backend/services/ingestion-pipeline/.env.example`, `backend/services/exam-simulation/.env.example` with `LOG_LEVEL=INFO`, service-specific `DATABASE_URL`, `REDIS_URL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, empty AWS/LLM placeholders (FR-002)
- [X] T018 [P] [US1] Create `Dockerfile` and `Dockerfile.dev` for course-core in `backend/services/course-core/`: base `python:3.12-slim`, install uv, `uv sync --frozen` (prod: `--no-dev`); prod runs `uvicorn course_core.main:app --host 0.0.0.0 --port 8000`; dev adds `--reload --reload-dir` for service and shared src (FR-002, FR-007, FR-010; research R8)
- [X] T019 [P] [US1] Create `Dockerfile` and `Dockerfile.dev` for ingestion-pipeline in `backend/services/ingestion-pipeline/` (same pattern, app `ingestion_pipeline.main:app`) (FR-002, FR-007, FR-010)
- [X] T020 [P] [US1] Create `Dockerfile` and `Dockerfile.dev` for exam-simulation in `backend/services/exam-simulation/` (same pattern, app `exam_simulation.main:app`) (FR-002, FR-007, FR-010)
- [X] T021 [P] [US1] Create `backend/infra/docker/postgres/init-databases.sh` — creates `course_core`, `ingestion`, `exam_sim` databases and enables the `vector` extension in each; executable, POSIX sh (FR-015a; research R6)
- [X] T022 [P] [US1] Create `backend/infra/docker/otel/otel-collector-config.yaml` — OTLP receivers on 4317 (gRPC) and 4318 (HTTP), `debug` exporter, minimal pipeline (research R9)
- [X] T023 [US1] Create `backend/infra/docker/docker-compose.yml` orchestrating: 3 services built from `Dockerfile.dev` (ports 8001:8000, 8002:8000, 8003:8000; volume mounts of `../../services/<svc>/src` and `../../shared/src`; per-service env incl. `DATABASE_URL`, `REDIS_URL`, `OTEL_EXPORTER_OTLP_ENDPOINT`), `pgvector/pgvector:pg17` (5432, init script mount, `pg_isready` healthcheck), `redis:7-alpine` (6379, `redis-cli ping` healthcheck), `otel/opentelemetry-collector-contrib` (4317, 4318); services `depends_on` postgres+redis healthy (FR-006, FR-007, FR-011; depends on T011–T022)
- [X] T024 [US1] Validate US1 end-to-end: `docker compose up --build` from `backend/infra/docker/` → 6 healthy containers < 60s, `curl` all three `/health` payloads match FR-003 exactly, `/metrics` returns Prometheus text, edit a src file and confirm hot reload (SC-001, SC-004; acceptance US1-1..3)

**Checkpoint**: Full local stack runs — MVP delivered.

---

## Phase 4: User Story 2 — Developer Runs Tests and Linting (Priority: P2)

**Goal**: `pre-commit run --all-files` and `pytest --cov=backend --cov-fail-under=80` both pass locally; secret detection blocks credential commits.

**Independent Test**: Run `uv run pre-commit run --all-files` (all hooks green < 30s) and `uv run pytest --cov=backend --cov-fail-under=80` (all pass, ≥80%); stage a file with a private key and confirm the commit is blocked.

### Tests for User Story 2 (these ARE the deliverable — FR-009a)

- [X] T025 [P] [US2] Write `backend/services/course-core/tests/test_health.py` — httpx `ASGITransport` against `course_core.main:app`; assert `/health` returns exact payload `{"status": "ok", "service": "course-core", "version": "0.1.0"}` and `/metrics` returns 200 (research R12)
- [X] T026 [P] [US2] Write `backend/services/ingestion-pipeline/tests/test_health.py` — same pattern for `ingestion_pipeline.main:app`, service name `ingestion-pipeline`
- [X] T027 [P] [US2] Write `backend/services/exam-simulation/tests/test_health.py` — same pattern for `exam_simulation.main:app`, service name `exam-simulation`
- [X] T028 [P] [US2] Write `backend/tests/test_config.py` — `Settings` loads with no env (optional fields `None`), `LOG_LEVEL` defaults to `INFO`, and env override works (FR-016)
- [X] T029 [P] [US2] Write `backend/tests/test_stubs.py` — importing `iam`/`llm`/`s3` never raises; instantiating without config succeeds; calling any operation raises `NotConfiguredError` (FR-017)

### Implementation for User Story 2

- [X] T030 [US2] Create `backend/.pre-commit-config.yaml` with hooks: `ruff check --fix`, `ruff format`, mypy strict as a local hook running `uv run mypy` (workspace venv per research R10), `detect-private-key`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files` (FR-008, FR-012)
- [X] T031 [US2] Configure coverage in `backend/pyproject.toml` (`[tool.coverage]` source/paths covering shared, services, agents) so `uv run pytest --cov=backend --cov-fail-under=80` from `backend/` measures all backend code (FR-009a; depends on T025–T029)
- [X] T032 [US2] Validate US2: run `uv run pre-commit run --all-files` (zero violations, < 30s) and `uv run pytest --cov=backend --cov-fail-under=80` (all pass, ≥80%); fix any lint/type/coverage findings across backend files (SC-002, SC-005; acceptance US2-1..3)

**Checkpoint**: Quality gates pass locally; coverage ≥80%.

---

## Phase 5: User Story 3 — CI Pipeline Validates Every PR and Push (Priority: P3)

**Goal**: GitHub Actions runs lint + test jobs on push to main and PRs, reporting pass/fail status.

**Independent Test**: Push the branch and confirm both `lint` and `test` jobs run and go green in GitHub Actions (< 5 min).

### Implementation for User Story 3

- [X] T033 [US3] Create `.github/workflows/ci.yml` — triggers `push` (branches: main) + `pull_request`; job **lint**: checkout, `astral-sh/setup-uv`, cached pre-commit, `pre-commit run --all-files`; job **test**: checkout, `astral-sh/setup-uv`, `uv sync --frozen` in `backend/`, `uv run pytest --cov=backend --cov-fail-under=80`; no service containers (research R11) (FR-009)
- [ ] T034 [US3] Validate US3: push the feature branch, confirm both jobs execute and report status in < 5 min; verify a deliberate failure shows red (SC-003; acceptance US3-1..3)

**Checkpoint**: CI enforces lint + coverage on every push/PR.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T035 [P] Verify repo state against `specs/001-project-scaffold/quickstart.md` — every documented command works verbatim (compose up, uv sync, pre-commit, pytest, alembic revision)
- [X] T036 [P] Cross-check generated `/health` + `/metrics` behavior against `specs/001-project-scaffold/contracts/health-api.yaml` (status codes, payload schema, content types)
- [X] T037 Final sweep: `uv run pre-commit run --all-files` and `uv run pytest --cov=backend --cov-fail-under=80` green from a clean checkout; no `.env` or secrets tracked by git (Constitution IX)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Foundational)**: needs T003 (workspace root); BLOCKS all user stories
- **Phase 3 (US1)**: needs Phase 2 (services import `exambrain-shared`)
- **Phase 4 (US2)**: needs Phase 2; tests T025–T027 need US1's service packages (T011–T013) but NOT the Docker tasks — US2 is testable without a running stack
- **Phase 5 (US3)**: needs Phase 4 artifacts (pre-commit config, tests) to have anything to run in CI
- **Phase 6 (Polish)**: needs all stories complete

### Key Task Dependencies

- T010 ← T003, T005 (lockfile needs workspace + shared package)
- T023 ← T011–T022 (compose references all service builds + infra configs)
- T031 ← T025–T029 (coverage config validated against real tests)
- T033 ← T030, T031 (CI runs pre-commit + pytest as configured)

### Parallel Opportunities

- **Phase 2**: T006, T007, T008, T009 — four independent shared modules
- **Phase 3**: T011–T022 — 12 parallel tasks (3 service packages, 3 alembic scaffolds, 3 env examples via T017, 3 Dockerfile pairs, 2 infra configs); only T023/T024 are sequential
- **Phase 4**: T025–T029 — five independent test files
- **Phase 6**: T035, T036 in parallel

---

## Parallel Example: User Story 1

```bash
# After Phase 2, launch service scaffolds concurrently:
Task: "Create course-core service package in backend/services/course-core/"        # T011
Task: "Create ingestion-pipeline service package in backend/services/ingestion-pipeline/"  # T012
Task: "Create exam-simulation service package in backend/services/exam-simulation/"        # T013
Task: "Create postgres init script backend/infra/docker/postgres/init-databases.sh"        # T021
Task: "Create OTel config backend/infra/docker/otel/otel-collector-config.yaml"            # T022
# Then T023 (docker-compose.yml) once all inputs exist, then T024 to validate.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational)
2. Phase 3 (US1): full local stack via Docker Compose
3. **STOP and VALIDATE** with T024 — 6 healthy containers, health payloads exact, hot reload works
4. Demo-able MVP: `docker compose up --build`

### Incremental Delivery

1. Setup + Foundational → workspace resolves, shared lib importable
2. US1 → running stack (MVP)
3. US2 → quality gates + 80% coverage locally
4. US3 → CI enforces the same gates remotely
5. Polish → quickstart/contract verification, final clean-checkout sweep

### Parallel Team Strategy

After Phase 2, one developer can drive US1 (Docker/compose) while another writes US2's test files against the service packages as soon as T011–T013 land; US3 waits on US2's configs.
