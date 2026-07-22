# Implementation Plan: Exam Simulation Service

**Branch**: `005-exam-simulation` | **Date**: 2026-07-22 | **Spec**: `specs/005-exam-simulation/spec.md`
**Input**: Feature specification from `/specs/005-exam-simulation/spec.md`

## Summary

The Exam Simulation Service turns a stored generated mock exam into a live, timed, monitored exam attempt, then hands finished answers to the existing TA evaluation pipeline for grading. It also adds exam-duration extraction to the parsing → blueprint → generation pipeline so simulated exams use authentic time limits. Two high-impact workstreams: (1) the attempt lifecycle + integrity system (new service logic), and (2) duration plumbing (cross-cutting schema + agent changes).

## Technical Context

**Language/Version**: Python 3.12+ (pinned `.python-version`)
**Primary Dependencies**: FastAPI, SQLAlchemy 2 (async), asyncpg, pydantic v2, LiteLLM, redis-py (async), tenacity, structlog, pydantic-settings
**Storage**: PostgreSQL 17 + pgvector (exam_sim DB for attempts; course_core DB for results/blueprints; ingestion DB for past_papers); Redis 7 (live attempt state cache)
**Testing**: pytest, pytest-asyncio, httpx (AsyncClient), pytest-cov (≥80%)
**Target Platform**: Linux server (OCI Ampere A1 + AWS), containerized via Docker
**Project Type**: Web application — backend microservice (existing scaffold at `backend/services/exam-simulation/`)
**Performance Goals**: Start attempt → seen in <3s (SC-001); manual submit acknowledged in <2s (SC-005); deadline auto-finish within seconds of expiry (SC-003); polling response <500ms p95
**Constraints**: ~2.4GB total RAM footprint (zero-cost infra); async everywhere; repository pattern; no raw SQL in handlers; Alembic migrations only; cross-DB references are identifier-only UUIDs (no FKs between databases)
**Scale/Scope**: Single microservice in a 3-service system; target ~10k active students; attempt state held in Redis with PG as durable backing

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. SDD | ✅ PASS | Spec → Plan → Tasks sequence followed; PHR recorded |
| II. Zero-Cost | ✅ PASS | Fits within existing OCI + AWS free tiers; no new infra |
| III. Agent Isolation | ✅ PASS (resolved) | Changes are additive fields + prompts only; no shared state introduced; all agents remain testable in isolation |
| IV. Async-First | ✅ PASS | All new code uses asyncpg/httpx/asyncio |
| V. LLM Abstraction | ✅ PASS | Evaluation pipeline already uses LiteLLM; no new LLM calls in attempt lifecycle |
| VI. TDD Critical Paths | ✅ PASS | Attempt lifecycle (start, save, finish, deadline), focus-violation lockout, time-limit extraction — all TDD red-green-refactor |
| VII. Repository Pattern | ✅ PASS | All DB access through existing repo layer; new repos for attempts |
| VIII. Code Quality | ✅ PASS | ruff + black + mypy strict + no TODOs |
| IX. Security | ✅ PASS | Auth on all endpoints; Pydantic validation; own-attempt-only access |
| X. Observability | ✅ PASS | structlog JSON logging; /health endpoint; attempt-state metrics |

## Project Structure

### Documentation (this feature)

```text
specs/005-exam-simulation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/sp.tasks command)
```

### Source Code (repository root)

```text
backend/
├── shared/
│   └── src/exambrain_shared/
│       ├── config.py                          # + exam_sim settings
│       ├── models/
│       │   ├── exam_sim.py                    # + deadline, answers, time_limit fields
│       │   ├── course_core.py                 # + ExamBlueprint.time_limit
│       │   └── ingestion.py                   # + PastPaper.time_limit
│       └── ...
├── services/
│   └── exam-simulation/
│       ├── src/exam_simulation/
│       │   ├── main.py                        # existing scaffold → add routers, lifespan
│       │   ├── routers/
│       │   │   ├── __init__.py
│       │   │   ├── attempts.py                # start, poll answers, submit/finish
│       │   │   └── focus.py                   # report focus violation
│       │   ├── schemas/
│       │   │   ├── __init__.py
│       │   │   ├── attempts.py                # request/response schemas
│       │   │   └── focus.py
│       │   ├── services/
│       │   │   ├── __init__.py
│       │   │   ├── attempt_lifecycle.py       # start, save, finish, deadline logic
│       │   │   ├── focus_tracker.py           # violation tracking + lockout
│       │   │   └── deadline_checker.py        # background deadline enforcer
│       │   └── dependencies.py                # auth, repo injection
│       ├── tests/
│       │   ├── conftest.py
│       │   ├── test_attempt_lifecycle.py
│       │   ├── test_focus_tracker.py
│       │   ├── test_deadline_checker.py
│       │   └── test_api.py
│       ├── alembic/versions/
│       │   ├── 20260720_003_attempt_deadline_answers.py
│       │   └── 20260720_004_time_limit_fields.py
│       └── Dockerfile
├── agents/
│   └── src/exambrain_agents/
│       ├── schemas/
│       │   ├── parsing.py                     # + ParsedDocument.time_limit
│       │   ├── blueprint.py                   # + BlueprintStructure.time_limit
│       │   └── generation.py                  # + GeneratedExam.time_limit (check)
│       ├── parsing/prompt.py                  # + time-limit extraction instruction
│       ├── blueprint/prompt.py                # + duration-merging instruction
│       ├── generator/prompt.py                # + time_limit pass-through (FR-020)
│       ├── repositories/
│       │   ├── exam_sim.py                    # + session CRUD, answer save, focus update
│       │   └── course_core.py                 # + blueprint time_limit read
│       └── pipelines/
│           └── ingest.py                      # + time_limit extract step
└── infra/
    └── docker/
        └── docker-compose.yml                 # + REDIS_URL for exam-sim service
```

**Structure Decision**: Web application (backend-only). Changes span 3 services (shared/models, exam-simulation service, agents) to thread the time-limit concept through the entire pipeline. The exam-simulation service gets the most new code (routers, schemas, service layer, background tasks).

## Complexity Tracking

> No constitution violations that require justification. All additions follow existing patterns and fit within the project's architecture.
