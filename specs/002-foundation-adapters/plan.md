# Implementation Plan: Foundation Adapters

**Branch**: `002-foundation-adapters` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-foundation-adapters/spec.md`

## Summary

Replace the deferred-error stubs in `exambrain-shared` with five real foundation adapters: (1) versioned Alembic migrations creating the core domain schema across the three per-service databases (course_core, ingestion, exam_sim) with pgvector 1024-dim embedding columns; (2) an async LiteLLM gateway to AWS Bedrock with bounded exponential-backoff retries and in-memory token tracking; (3) an async Redis session store with TTL entries and fixed-window rate-limit counters; (4) an async streaming S3 adapter via aioboto3; (5) an IAM credential manager providing read-only least-privilege validation and restart-free rotation. All adapters preserve the existing scaffold contract: import never fails, construction never fails, unconfigured operations raise `NotConfiguredError` at call time.

## Technical Context

**Language/Version**: Python 3.12+ (uv workspace monorepo, `backend/`)
**Primary Dependencies**: SQLAlchemy 2 (async) + asyncpg, Alembic 1.14+, pgvector (Python bindings for `Vector` column type), LiteLLM (Bedrock provider), tenacity (retry/backoff), redis-py ≥5 (async, `redis.asyncio`), aioboto3, structlog, pydantic-settings
**Storage**: PostgreSQL 17 + pgvector (three per-service databases: `course_core`, `ingestion`, `exam_sim`); Redis 7 (session state, rate-limit counters); AWS S3 (course files)
**Testing**: pytest + pytest-asyncio (auto mode), pytest-cov (80% floor); external providers simulated — LiteLLM mocked at the `acompletion`/`aembedding` boundary, Redis via `fakeredis`, S3/IAM via `moto`-style or hand-rolled fakes; migration tests against the local docker Postgres
**Target Platform**: Linux containers (docker-compose local; K3s on OCI production)
**Project Type**: Backend monorepo — shared library (`backend/shared`) + three services with per-service Alembic trees
**Performance Goals**: Similarity query over 1k chunks < 1 s local (HNSW index); LLM round-trip success ≥95% first attempt with automatic transient-retry; session expiry within 5 s of nominal TTL; credential validation < 10 s
**Constraints**: Zero-cost infra (Oracle Free + AWS Free Tier); no import-time/startup network I/O anywhere; streaming S3 transfers (100 MB file with <25% memory growth); no secrets in logs/errors/repo; existing scaffold tests pass unchanged
**Scale/Scope**: 5 adapters in `exambrain-shared` + 3 initial migration revisions (one per service); single-developer local stack; ~8 domain entities

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|---|---|---|
| I | Spec-Driven Development | ✅ PASS | Spec → this plan → tasks; PHR recorded; ADR candidates flagged below |
| II | Zero-Cost Infrastructure | ✅ PASS | Reuses existing local Postgres/Redis containers; Bedrock + S3 within AWS Free Tier / pay-per-token; no new infra |
| III | Agent Isolation & Contract-First | ✅ PASS | Adapters are shared-library contracts consumed by agents; no agent coupling introduced |
| IV | Async-First | ✅ PASS | All adapters async (`asyncpg`, `redis.asyncio`, `aioboto3`, LiteLLM `acompletion`); no sync I/O in request paths (Alembic CLI runs are operator-time, not request-time) |
| V | LLM Provider Abstraction | ✅ PASS | Single LiteLLM gateway module; provider/model from env config only; Bedrock ↔ other providers is a config change |
| VI | TDD on Critical Paths | ✅ PASS | Retry/token-tracking, rate-limit counter, and migration round-trips test-first; 80% coverage floor kept |
| VII | Repository Pattern & Data Integrity | ✅ PASS | Schema changes exclusively via Alembic; ORM models on shared `Base`; pgvector via SQLAlchemy column types (repository layer proper lands with services in later features) |
| VIII | Code Quality | ✅ PASS | mypy strict, ruff, black 88, Google docstrings, no TODO/HACK markers |
| IX | Security by Default | ✅ PASS | Secrets env-only, never logged (FR-019/020); read-only IAM validation; S3 signed-URL use remains for later API features |
| X | Observability | ✅ PASS | Structured logs per LLM call (model, tokens, latency — never raw prompts); usage counters inspectable |

**Post-Phase-1 re-check**: ✅ PASS — design introduces no violations; no Complexity Tracking entries needed.

**ADR candidates** (to propose, not auto-create): (a) shared ORM models in `exambrain-shared` with per-service metadata partitioning; (b) in-memory-only token usage tracking; (c) fixed-window rate limiting.

## Project Structure

### Documentation (this feature)

```text
specs/002-foundation-adapters/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (adapter Python contracts)
│   ├── llm-gateway.md
│   ├── session-store.md
│   ├── file-storage.md
│   └── credentials.md
└── tasks.md             # Phase 2 (/sp.tasks — NOT created by /sp.plan)
```

### Source Code (repository root)

```text
backend/
├── shared/
│   ├── pyproject.toml                    # + litellm, tenacity, redis, aioboto3, pgvector
│   └── src/exambrain_shared/
│       ├── config.py                     # + redis/S3/Bedrock/retry settings fields
│       ├── errors.py                     # + ObjectNotFoundError, PermissionDeniedError,
│       │                                 #   CredentialError, TransientLLMError, PermanentLLMError
│       ├── db.py                         # unchanged public API
│       ├── llm.py                        # real LiteLLM gateway (replaces stub)
│       ├── llm_usage.py                  # in-memory UsageTracker (per-model counters)
│       ├── redis.py                      # NEW: SessionStore + RateLimiter (lazy async client)
│       ├── s3.py                         # real aioboto3 adapter (replaces stub)
│       ├── iam.py                        # real credential manager + validation (replaces stub)
│       └── models/                       # NEW: ORM models on shared Base
│           ├── __init__.py
│           ├── course_core.py            # User, Course, ExamBlueprint, Result
│           ├── ingestion.py              # PastPaper, DocumentChunk (Vector(1024))
│           └── exam_sim.py               # ExamSession
├── services/
│   ├── course-core/alembic/versions/     # rev 001: users, courses, exam_blueprints, results
│   ├── ingestion-pipeline/alembic/versions/  # rev 001: past_papers, document_chunks (+ pgvector ext, HNSW index)
│   └── exam-simulation/alembic/versions/     # rev 001: exam_sessions
└── tests/
    ├── test_stubs.py                     # unchanged — must keep passing
    ├── test_llm.py                       # NEW: gateway, retries, usage tracking
    ├── test_redis_store.py               # NEW: TTL, counters (fakeredis)
    ├── test_s3.py                        # NEW: streaming ops (simulated backend)
    ├── test_iam.py                       # NEW: validation, rotation, no-secret-leak
    └── test_migrations.py                # NEW: upgrade/downgrade round-trip per service
```

**Structure Decision**: All adapter code lives in `backend/shared/src/exambrain_shared/` (single shared library, per Constitution V's "single well-defined module" for LLM and the existing stub layout). ORM models are added under a new `models/` subpackage, split by owning service; each service's Alembic tree filters to its own tables via `include_object` so `alembic upgrade` per service touches only that service's database (FR-004). Tests live in the existing `backend/tests/` workspace-root suite.

## Complexity Tracking

No constitution violations — table intentionally empty.
