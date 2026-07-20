---
id: 0005
title: implement-foundation-adapters
stage: green
date: 2026-07-20
surface: vscode-claude-code
model: claude-opus-4-8
feature: 002-foundation-adapters
branch: 002-foundation-adapters
user: Muhammad
command: /sp.implement
labels: [implementation, adapters, migrations, tdd]
links:
  spec: specs/002-foundation-adapters/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/shared/pyproject.toml
  - backend/pyproject.toml
  - backend/shared/src/exambrain_shared/config.py
  - backend/shared/src/exambrain_shared/errors.py
  - backend/shared/src/exambrain_shared/llm.py
  - backend/shared/src/exambrain_shared/llm_usage.py
  - backend/shared/src/exambrain_shared/redis.py
  - backend/shared/src/exambrain_shared/s3.py
  - backend/shared/src/exambrain_shared/iam.py
  - backend/shared/src/exambrain_shared/models/__init__.py
  - backend/shared/src/exambrain_shared/models/course_core.py
  - backend/shared/src/exambrain_shared/models/ingestion.py
  - backend/shared/src/exambrain_shared/models/exam_sim.py
  - backend/services/course-core/alembic/env.py
  - backend/services/course-core/alembic/versions/20260720_001_course_core_initial_schema.py
  - backend/services/ingestion-pipeline/alembic/env.py
  - backend/services/ingestion-pipeline/alembic/versions/20260720_001_ingestion_initial_schema.py
  - backend/services/exam-simulation/alembic/env.py
  - backend/services/exam-simulation/alembic/versions/20260720_001_exam_sim_initial_schema.py
  - backend/tests/conftest.py
tests:
  - backend/tests/test_migrations.py
  - backend/tests/test_models.py
  - backend/tests/test_llm.py
  - backend/tests/test_redis_store.py
  - backend/tests/test_s3.py
  - backend/tests/test_iam.py
---

## Prompt

/sp.implement (no additional user input) — execute the implementation plan for
feature 002-foundation-adapters by processing all tasks in tasks.md: five real
foundation adapters replacing the exambrain-shared stubs (Alembic domain
migrations with pgvector, LiteLLM Bedrock gateway, Redis session store +
rate limiter, aioboto3 streaming S3 adapter, IAM credential manager), TDD on
critical paths, 80% coverage floor, scaffold contract preserved.

## Response snapshot

All 35 tasks (T001–T035) completed across 8 phases:

- **Setup**: added litellm/tenacity/redis/aioboto3/pgvector/alembic deps +
  fakeredis/psycopg dev deps; extended Settings (retry, embedding model, rate
  limit, s3 endpoint fields + secret-redacting __repr_args__); five new typed
  errors; migration pytest marker with auto-skip; suite-wide no-secret-leak
  conftest fixture.
- **US1**: shared ORM models tagged per service (course_core / ingestion /
  exam_sim), include_object filters in all three alembic env.py files, three
  revision-001 migrations (vector(1024) + HNSW cosine index in ingestion),
  4 migration round-trip tests + 8 hermetic model-metadata tests. Migrations
  applied to the local docker Postgres and verified.
- **US2**: real LLMClient via litellm.acompletion/aembedding with tenacity
  bounded retry (attempts + deadline), transient/permanent classification,
  in-memory UsageTracker, structlog events (prompt hash only), bedrock AWS-trio
  is_configured. 9 tests.
- **US3**: new redis.py — SessionStore (SET/EX JSON, None on absent) +
  RateLimiter (atomic INCR fixed window), lazy client factory. 8 tests.
- **US4**: real S3Adapter — upload_fileobj streaming, chunked download,
  paginated list_by_prefix, ClientError → typed error mapping. 8 tests.
- **US5**: CredentialManager (IAMClient alias preserved) — STS identity,
  simulate-principal-policy validation with cannot_verify degradation,
  restart-free refresh(), secret-safe repr. 8 tests.
- **Gates**: 62 passed, coverage 94% (≥80), mypy strict clean, ruff clean,
  black applied. test_stubs/test_config/test_db pass unchanged (FR-021).

## Outcome

- ✅ Impact: all five foundation adapters real; scaffold contract intact; three service DBs migrated with reversible revisions
- 🧪 Tests: 62 passed (58 hermetic + 4 migration), coverage 94.35%
- 📁 Files: 20 source/config files changed, 6 test files added
- 🔁 Next prompts: /sp.adr for the three flagged ADR candidates; /sp.git.commit_pr to commit and open PR
- 🧠 Reflection: fakeredis lacks server time travel — TTL expiry tested via pexpire shrink; litellm exception types must be referenced via litellm.exceptions for mypy strict

## Evaluation notes (flywheel)

- Failure modes observed: collinear test vectors gave identical cosine distance (test bug, fixed); pydantic Settings repr leaked secrets (fixed with __repr_args__ redaction); sync stub-era get_caller_identity call needed a sync config check before coroutine creation
- Graders run and results (PASS/FAIL): pytest PASS, coverage PASS (94%), mypy strict PASS, ruff PASS, black PASS
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): consider a live smoke-test marker for Bedrock once AWS credentials are provisioned
