# Feature Specification: Project Scaffold

**Feature Branch**: `001-project-scaffold`
**Created**: 2026-07-19
**Status**: Draft
**Input**: User description: Set up project scaffold with uv workspace monorepo, 3 FastAPI microservices, Docker, CI pipeline (GitHub Actions), pre-commit, and shared libraries. CI pipeline is explicitly in scope for this feature.

## User Scenarios & Testing

### User Story 1 — Developer Initializes and Runs the Project Locally (P1)

A developer clones the repo and starts the entire stack with a single command.

**Why this priority**: Without a working local environment, no other feature can be built or tested. This is the foundation.

**Independent Test**: Can be fully tested by running `docker compose up --build` and verifying all 6 containers (3 services + PG + Redis + OTel) start without errors, health endpoints return 200.

**Acceptance Scenarios**:

1. **Given** the repo is freshly cloned, **When** the developer runs `docker compose up --build` from `backend/infra/docker/`, **Then** all containers start and reach healthy state within 60 seconds.
2. **Given** all containers are running, **When** the developer hits `GET /health` on each service (ports 8001, 8002, 8003), **Then** each returns `{"status": "ok", "service": "<name>", "version": "0.1.0"}`.
3. **Given** the stack is running, **When** the developer modifies a Python source file in a service, **Then** the service auto-restarts with the new code (hot reload).

---

### User Story 2 — Developer Runs Tests and Linting (P2)

A developer writes code and wants to validate quality before pushing.

**Why this priority**: Ensures code quality gates work before other developers contribute.

**Independent Test**: Can be tested by running `pre-commit run --all-files` and `pytest` independently.

**Acceptance Scenarios**:

1. **Given** a developer has made changes, **When** they run `pre-commit run --all-files`, **Then** ruff linting, ruff formatting, mypy type checking, and secret detection all pass.
2. **Given** the project has test files, **When** the developer runs `pytest --cov=backend --cov-fail-under=80`, **Then** all tests pass and coverage meets the threshold.
3. **Given** a `.env` file contains dummy credentials, **When** the developer attempts to commit, **Then** pre-commit blocks the commit and warns about potential secrets.

---

### User Story 3 — CI Pipeline Validates Every PR and Push (P3)

A developer pushes code or opens a PR, and CI automatically validates it.

**Why this priority**: Automates quality enforcement and prevents broken code from reaching main.

**Independent Test**: Can be tested by pushing a branch and observing CI results in GitHub.

**Acceptance Scenarios**:

1. **Given** a developer pushes to a feature branch, **When** CI runs, **Then** it executes lint (pre-commit) and test (pytest) jobs.
2. **Given** a PR is opened against main, **When** CI completes, **Then** the PR shows green checkmarks for lint and test jobs.
3. **Given** lint or tests fail, **When** CI finishes, **Then** the PR shows red status for the failing job. (Branch protection / merge blocking is not configured in this feature.)

---

### Edge Cases

- What happens when Docker Compose runs on a system without Docker installed? — User gets a clear error message from the Docker CLI.
- What happens when `make` or `uv` is missing? — Pre-commit and setup scripts should detect missing tooling early.
- What happens when ports 8001-8003 or 5432 or 6379 are already in use? — Docker Compose logs port conflict errors.
- What happens when AWS credentials are not configured? — Services still start and expose health endpoints; only S3/Bedrock operations fail with clear error messages.

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a `backend/` top-level directory with a `pyproject.toml` defining a `uv` workspace linking all services under `services/`.
- **FR-002**: Each service (course-core, ingestion-pipeline, exam-simulation) MUST have its own `pyproject.toml`, Dockerfile, Dockerfile.dev, `.env.example`, and `alembic/` scaffold.
- **FR-003**: Each service MUST expose `GET /health` returning `{"status": "ok", "service": "<name>", "version": "0.1.0"}`.
- **FR-004**: Each service MUST expose `GET /metrics` for Prometheus metric scraping.
- **FR-005**: A `shared/` package MUST exist containing modules for config, logging, IAM validation, LiteLLM client stub, S3 adapter stub, and database base.
- **FR-006**: The project MUST include `docker-compose.yml` orchestrating all 3 services, PostgreSQL 17 (with pgvector), Redis 7, and an OpenTelemetry collector sidecar.
- **FR-007**: Docker development images MUST mount source code as volumes for hot reload.
- **FR-008**: The project MUST include `.pre-commit-config.yaml` with hooks for ruff check, ruff format, mypy, detect-private-key, trailing-whitespace, end-of-file-fixer, check-yaml, and check-added-large-files.
- **FR-009**: CI pipeline (GitHub Actions) MUST run pre-commit checks and pytest with 80% coverage threshold (measured over all `backend/` code) on push to main and pull requests.
- **FR-009a**: The scaffold MUST include tests covering health endpoints, config loading, and shared-stub deferred-error behavior sufficient to meet the 80% coverage threshold at feature completion.
- **FR-010**: Each service MUST use `python:3.12-slim` as base image.
- **FR-011**: Port mapping MUST be: course-core (8001), ingestion-pipeline (8002), exam-simulation (8003), PostgreSQL (5432), Redis (6379), OTel collector gRPC (4317), OTel collector HTTP (4318).
- **FR-012**: The project MUST use `ruff` for linting and `mypy` (strict mode) for type checking.
- **FR-013**: A `.python-version` file MUST pin Python 3.12.
- **FR-014**: `.gitignore` MUST exclude Python artifacts, virtual environments, IDE files, Docker artifacts, and `.env` files.
- **FR-015**: Each service MUST include an `alembic/` directory with `env.py` and `alembic.ini` configured for async PostgreSQL, targeting that service's own database.
- **FR-015a**: The single PostgreSQL instance MUST host a separate database per service (`course_core`, `ingestion`, `exam_sim`), created automatically at container initialization.
- **FR-016**: Each service MUST use INFO as default log level, configurable via `LOG_LEVEL` environment variable.
- **FR-017**: Shared library stubs (S3, LiteLLM, IAM) MUST NOT fail on import or startup — errors MUST be deferred until the specific operation is called at runtime.
- **FR-018**: The project MUST scaffold empty package directories under `agents/` (parsing, alignment, blueprint, generator, evaluation), each containing only an `__init__.py` — no agent logic in this feature.

### Conventions

- All commit messages SHOULD follow the `conventional commits` format (`feat:`, `fix:`, `chore:`, etc.). This is a team convention, not an enforced requirement.

### Key Entities

- **Service**: A FastAPI microservice (course-core, ingestion-pipeline, exam-simulation). Each is independently deployable.
- **Shared Library**: Reusable Python modules under `shared/` used across all services.
- **Infrastructure**: Docker Compose, OTel collector config, and future K8s manifests in `infra/`.
- **Agent**: Independent processing units under `agents/` — parsing, alignment, blueprint, generator, evaluation. Scaffolded as empty packages in this feature; logic deferred to future features.

## Clarifications

### Session 2026-07-19

- Q: How should shared stubs (S3, LiteLLM, IAM) handle missing AWS credentials? → A: Fail at runtime — raise errors only when the specific S3/Bedrock call is made, not during service startup.
- Q: What default log level should services use? → A: INFO by default, overridable via `LOG_LEVEL` env variable per service.

### Session 2026-07-20

- Q: How should the `agents/` directory (parsing, alignment, blueprint, generator, evaluation) be handled in this scaffold feature? → A: Scaffold empty package directories (structure only, `__init__.py` each, no logic).
- Q: Do the services share one database or use separate databases? → A: One PostgreSQL instance with a separate database per service (`course_core`, `ingestion`, `exam_sim`).
- Q: Is GitHub branch protection (merge blocking) in scope? → A: No — branch protection is not configured; CI reports pass/fail status only.
- Q: What does the 80% coverage threshold apply to at scaffold completion? → A: All `backend/` code — the scaffold ships with tests (health endpoints, config, stub deferred-error behavior) that reach 80% from day one.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A developer can clone the repo and have the full stack running locally with `docker compose up` in under 2 minutes.
- **SC-002**: `pre-commit run --all-files` completes in under 30 seconds with zero violations.
- **SC-003**: CI pipeline completes lint + test jobs in under 5 minutes.
- **SC-004**: All three services start simultaneously and all health endpoints respond within 10 seconds.
- **SC-005**: Coverage threshold of 80% is enforced — any drop below fails the CI pipeline.
