# Tasks: Foundation Adapters

**Input**: Design documents from `/specs/002-foundation-adapters/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — Constitution VI (TDD on critical paths) and FR-022 (80% coverage floor, simulated providers) explicitly require tests. Critical-path tests (retry/token tracking, rate-limit counter, migration round-trips) are written FIRST within each story.

**Organization**: Tasks grouped by user story (US1–US5, priorities P1–P5) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US5) — user-story phase tasks only
- All paths are relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies and configuration surface every story needs

- [X] T001 Add new dependencies (`litellm`, `tenacity`, `redis>=5`, `aioboto3`, `pgvector`, `alembic>=1.14`) to `backend/shared/pyproject.toml` and dev deps (`fakeredis[async]`, `pytest-asyncio`) to the workspace test extras; run `uv sync` in `backend/` and verify it resolves
- [X] T002 Extend `Settings` in `backend/shared/src/exambrain_shared/config.py` with optional fields `llm_embedding_model`, `llm_max_retries` (default 3), `llm_retry_deadline_seconds` (default 60), `rate_limit_default_threshold`, `rate_limit_default_window_seconds`, `s3_endpoint_url` — all optional, construction must never raise (research R10; existing `backend/tests/test_config.py` must keep passing)
- [X] T003 [P] Add new error types `ObjectNotFoundError`, `PermissionDeniedError`, `CredentialError`, `TransientLLMError`, `PermanentLLMError` to `backend/shared/src/exambrain_shared/errors.py`, preserving existing `NotConfiguredError` semantics
- [X] T004 [P] Register the `migration` pytest marker (skipped when local Postgres is unreachable) in `backend/pyproject.toml` or `backend/tests/conftest.py`, plus shared async-test fixtures (research R9)

**Checkpoint**: `uv run pytest backend/tests/test_stubs.py backend/tests/test_config.py` passes unchanged

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared ORM base plumbing required before any story's models or adapters

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create `backend/shared/src/exambrain_shared/models/__init__.py` establishing the models subpackage on the shared `Base` from `db.py`, with a timestamp mixin (`id UUID PK default gen_random_uuid()`, `created_at`/`updated_at timestamptz` with onupdate) and the per-service table tagging convention `__table_args__ = {"info": {"service": "<name>"}}` (research R4, data-model.md conventions)

**Checkpoint**: `from exambrain_shared.models import Base` imports cleanly with zero configuration

---

## Phase 3: User Story 1 — Domain Data Foundation (Priority: P1) 🎯 MVP

**Goal**: Versioned, reversible Alembic migrations creating all core domain tables across the three per-service databases, with a `vector(1024)` embedding column and HNSW similarity index.

**Independent Test**: Run migrations against fresh local databases; verify all tables/relationships/vector columns exist; insert and similarity-query a chunk; downgrade cleanly; confirm per-service isolation.

### Tests for User Story 1 (TDD — write first, confirm they fail)

- [X] T006 [P] [US1] Write migration round-trip tests in `backend/tests/test_migrations.py` (marker `migration`): per service — `alembic upgrade head` creates expected tables/constraints, insert a representative row per entity, `alembic downgrade base` leaves no orphaned objects; ingestion DB — insert `document_chunks` row with a 1024-dim embedding, run cosine similarity query returning ranked results, assert wrong-dimension insert fails loudly; cross-service isolation — each service's upgrade touches only its own database (spec US1 acceptance scenarios 1–4)

### Implementation for User Story 1

- [X] T007 [P] [US1] Create ORM models `User`, `Course`, `ExamBlueprint`, `Result` in `backend/shared/src/exambrain_shared/models/course_core.py` per data-model.md (FKs with ON DELETE CASCADE, `UNIQUE(course_id, version)` on blueprints, `UNIQUE exam_session_id` on results, JSONB structure columns, indexes; service tag `course_core`)
- [X] T008 [P] [US1] Create ORM models `PastPaper`, `DocumentChunk` in `backend/shared/src/exambrain_shared/models/ingestion.py` per data-model.md (processing_status CHECK constraint `pending/processing/completed/failed`, `failure_reason`, `embedding Vector(1024)` nullable, hierarchy JSONB, indexes; service tag `ingestion`)
- [X] T009 [P] [US1] Create ORM model `ExamSession` in `backend/shared/src/exambrain_shared/models/exam_sim.py` per data-model.md (status CHECK constraint `active/submitted/locked_out/expired`, identifier-only UUID refs, indexes; service tag `exam_sim`)
- [X] T010 [US1] Export all models from `backend/shared/src/exambrain_shared/models/__init__.py` and update `backend/shared/src/exambrain_shared/__init__.py` if the package re-exports symbols (depends on T007–T009)
- [X] T011 [P] [US1] Update `backend/services/course-core/alembic/env.py` to import `exambrain_shared.models` and add an `include_object` filter selecting only tables tagged `service == "course_core"` (research R4, FR-004)
- [X] T012 [P] [US1] Update `backend/services/ingestion-pipeline/alembic/env.py` with the same pattern filtering to `service == "ingestion"`
- [X] T013 [P] [US1] Update `backend/services/exam-simulation/alembic/env.py` with the same pattern filtering to `service == "exam_sim"`
- [X] T014 [P] [US1] Write migration revision 001 in `backend/services/course-core/alembic/versions/` creating `users`, `courses`, `exam_blueprints`, `results` with all constraints/indexes and a full `downgrade()` (depends on T007, T011)
- [X] T015 [P] [US1] Write migration revision 001 in `backend/services/ingestion-pipeline/alembic/versions/` running `CREATE EXTENSION IF NOT EXISTS vector` then creating `past_papers`, `document_chunks` with `vector(1024)` column and HNSW index (`vector_cosine_ops`), full `downgrade()` (depends on T008, T012; research R5)
- [X] T016 [P] [US1] Write migration revision 001 in `backend/services/exam-simulation/alembic/versions/` creating `exam_sessions` with constraints/indexes and full `downgrade()` (depends on T009, T013)
- [X] T017 [US1] Run the full US1 verification: `docker compose up -d postgres`, apply all three migrations per quickstart.md §2, run `uv run pytest -m migration` until green, then confirm hermetic runs (`uv run pytest`) auto-skip migration tests when Postgres is down

**Checkpoint**: SC-001 (fresh checkout → migrated in <5 min) and SC-002 (similarity query <1 s over 1k chunks) achievable; migrations reversible; per-service isolation proven

---

## Phase 4: User Story 2 — Reliable LLM Access (Priority: P2)

**Goal**: Real async LiteLLM gateway to Bedrock with bounded exponential-backoff retries, transient/permanent error classification, and in-memory per-model token usage tracking.

**Independent Test**: With fake provider config, completion/embedding return results with token counts; simulated transient failure retries and succeeds; permanent error raises immediately without retry; zero config raises `NotConfiguredError` with no network call; cumulative usage inspectable.

### Tests for User Story 2 (TDD — write first, confirm they fail)

- [X] T018 [P] [US2] Write gateway tests in `backend/tests/test_llm.py` monkeypatching `litellm.acompletion`/`litellm.aembedding` (research R9, contracts/llm-gateway.md test contract): canned success → `CompletionResult` fields + usage counters updated; `RateLimitError` twice then success → exactly 3 calls, success; `AuthenticationError` → `PermanentLLMError` after exactly 1 call; retries exhausted → `TransientLLMError` chaining provider error, bounded by attempts and deadline; not-configured → `NotConfiguredError` before any fake is called; `embed` returns 1024-length list; structlog event contains model/tokens/latency and never raw prompt text; `is_configured` accepts AWS cred trio for bedrock provider

### Implementation for User Story 2

- [X] T019 [P] [US2] Implement `UsageRecord`, `UsageSnapshot`, and `UsageTracker` (per-model cumulative counters: prompt_tokens, completion_tokens, calls) in `backend/shared/src/exambrain_shared/llm_usage.py` (research R3, data-model.md UsageRecord)
- [X] T020 [US2] Replace the stub in `backend/shared/src/exambrain_shared/llm.py` with the real `LLMClient` per contracts/llm-gateway.md: `CompletionResult` dataclass; `is_configured` predicate (provider+model+(api key OR AWS trio for bedrock)); `complete()`/`embed()` via `litellm.acompletion`/`aembedding` with `num_retries=0`, credentials passed per call from settings; tenacity `AsyncRetrying` with exponential backoff + jitter bounded by `llm_max_retries` and `llm_retry_deadline_seconds`; transient/permanent exception classification per research R1; per-call `UsageTracker` update and structlog event (model, sha256 prompt hash, latency_ms, token counts — never raw text); `usage` property (depends on T019)
- [X] T021 [US2] Run `uv run pytest backend/tests/test_llm.py backend/tests/test_stubs.py` until green — existing stub tests must pass unchanged (FR-021)

**Checkpoint**: SC-003/SC-004 verifiable with simulated provider; scaffold contract intact

---

## Phase 5: User Story 3 — Session & Rate-Limit Store (Priority: P3)

**Goal**: Async Redis session store with server-enforced TTL and an atomic fixed-window rate limiter, lazily connected.

**Independent Test**: Against fakeredis — store a session with TTL and read it back; observe absence after expiry; increment a counter past threshold and see the limit trip; unreachable Redis raises a clear connection error at call time only.

### Tests for User Story 3 (TDD — write first, confirm they fail)

- [X] T022 [P] [US3] Write store/limiter tests in `backend/tests/test_redis_store.py` using `fakeredis.FakeAsyncRedis` injected via the client factory (research R9): set/get/delete session round-trip with JSON values; TTL expiry via fakeredis time controls → `get_session` returns `None`; absent key → `None`, never raises; `RateLimiter.check` allows N then denies N+1 within a window (exact threshold, SC-005), window key includes window start, EXPIRE set on first hit; concurrent increments stay atomic; not-configured (`redis_url` unset) → `NotConfiguredError`; no connection attempted at import/construct

### Implementation for User Story 3

- [X] T023 [US3] Create `backend/shared/src/exambrain_shared/redis.py` per contracts/session-store.md: `SessionStore` (`set_session` = `SET key json EX ttl`, `get_session` → JSON decode or `None`, `delete_session`, `aclose`), `RateLimiter.check` (atomic `INCR` on `ratelimit:{scope}:{window_start}` + `EXPIRE` when count==1, returns `RateLimitResult(allowed, current_count)`), lazy `Redis.from_url` client created on first operation with an injectable client factory for tests, `is_configured` = `bool(settings.redis_url)`, unreachable store → clear connection error at call time (research R6, FR-011–013)
- [X] T024 [US3] Run `uv run pytest backend/tests/test_redis_store.py backend/tests/test_stubs.py` until green

**Checkpoint**: SC-005 verifiable; new module follows deferred-error pattern

---

## Phase 6: User Story 4 — Course File Storage (Priority: P4)

**Goal**: Real async streaming S3 adapter (upload/download/list-by-prefix/delete) via aioboto3 with distinguishable typed errors.

**Independent Test**: Against an in-memory fake S3 client — upload, list prefix, download byte-identical content, delete; missing key → `ObjectNotFoundError`; no config → `NotConfiguredError` with zero network access; large-file transfer streams without whole-file buffering.

### Tests for User Story 4 (TDD — write first, confirm they fail)

- [X] T025 [P] [US4] Write S3 tests in `backend/tests/test_s3.py` with a hand-rolled in-memory fake aioboto3 client (research R9): upload → list_by_prefix shows `ObjectInfo` → `download`/`download_bytes` byte-identical → delete → gone; paginated listing (>1 page); fake raising `ClientError` payloads → `NoSuchKey`→`ObjectNotFoundError`, `AccessDenied`→`PermissionDeniedError`, `ExpiredToken`→`CredentialError`; not-configured → `NotConfiguredError` for every method with no client construction; streaming upload of a large file-like consumed in chunks (memory-growth proxy for SC-006)

### Implementation for User Story 4

- [X] T026 [US4] Replace the stub in `backend/shared/src/exambrain_shared/s3.py` per contracts/file-storage.md: lazy `aioboto3.Session().client("s3")` as async context manager per operation (honoring `s3_endpoint_url`); `upload(key, bytes | BinaryIO)` via `upload_fileobj` (managed multipart streaming); `download(key, sink)` chunked streaming + `download_bytes(key)` convenience; `list_by_prefix` via `list_objects_v2` paginator returning `ObjectInfo`; `delete`; ClientError → typed-error mapping; `is_configured` = AWS trio + `s3_bucket`; injectable client factory for tests (research R7, FR-014–016)
- [X] T027 [US4] Run `uv run pytest backend/tests/test_s3.py backend/tests/test_stubs.py` until green — not-configured semantics of every stub method unchanged (FR-021)

**Checkpoint**: SC-006 memory behavior test in place; error taxonomy distinguishable

---

## Phase 7: User Story 5 — Credential Safety (Priority: P5)

**Goal**: Read-only least-privilege validation, restart-free credential rotation, and zero secret leakage in logs/errors.

**Independent Test**: With fake STS/IAM clients — validation reports each required permission allowed/denied; missing `iam:SimulatePrincipalPolicy` degrades to `cannot_verify`; after `refresh()` with changed env, operations use new values; captured log output across the suite contains no secret substring.

### Tests for User Story 5 (TDD — write first, confirm they fail)

- [X] T028 [P] [US5] Write credential tests in `backend/tests/test_iam.py` with fake STS/IAM clients (research R8/R9): `get_caller_identity` → `CallerIdentity`; `validate_permissions` over default action list (`s3:GetObject/PutObject/DeleteObject/ListBucket`, `bedrock:InvokeModel`) → per-action allowed/denied; simulate-policy `AccessDenied` → all actions `cannot_verify` (no false pass/fail); expired-credential auth failure → `CredentialError` distinct from `NotConfiguredError`; `refresh()` after monkeypatched env change → new values used without restart; not-configured → `NotConfiguredError`; no-secret-leak assertion — no configured secret value appears in any captured log line, `__repr__`, or exception text (FR-019, SC-007)

### Implementation for User Story 5

- [X] T029 [US5] Replace the stub in `backend/shared/src/exambrain_shared/iam.py` per contracts/credentials.md: `CredentialManager` (with `IAMClient` preserved as alias/subclass so existing imports and `test_stubs.py` pass); `refresh()` re-reading `Settings` bypassing the `lru_cache`; `get_caller_identity()` via aioboto3 STS; `validate_permissions()` via `iam:SimulatePrincipalPolicy` with graceful `cannot_verify` degradation; dataclasses `CallerIdentity`, `PermissionStatus`, `ValidationReport`; secret-safe `__repr__` and error messages referencing source names only; resolve legacy `validate_token` per contract's minimal-diff rule (research R8, FR-017–020)
- [X] T030 [US5] Wire rotation through consumers: verify `LLMClient` and `S3Adapter` read credentials from settings at call time (not cached at construct) so `refresh()` takes effect without restart, in `backend/shared/src/exambrain_shared/llm.py` and `backend/shared/src/exambrain_shared/s3.py`; add a rotation test to `backend/tests/test_iam.py` (FR-018, US5 acceptance scenario 2)
- [X] T031 [US5] Run `uv run pytest backend/tests/test_iam.py backend/tests/test_stubs.py` until green

**Checkpoint**: SC-007 verifiable; all five adapters real; scaffold contract intact everywhere

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, suite-wide guarantees, docs

- [X] T032 Add a suite-wide no-secret-leak check in `backend/tests/conftest.py`: fixture capturing all log output and asserting no configured secret substring appears anywhere across the full test run (SC-007, FR-019)
- [X] T033 Run full quality gates in `backend/`: `uv run pytest --cov --cov-fail-under=80`, `uv run mypy` (strict), `uv run ruff check`, `black --check` — fix any violations; confirm all pre-existing tests (`test_stubs.py`, `test_config.py`, `test_db.py`) pass unchanged (SC-008, FR-022)
- [X] T034 [P] Execute quickstart.md end-to-end on a fresh checkout (stack up → 3× migrations → schema verification → hermetic + migration test runs) and fix any drift between docs and implementation (SC-001)
- [X] T035 [P] Propose the three ADR candidates flagged in plan.md (shared ORM models with per-service metadata partitioning; in-memory-only token tracking; fixed-window rate limiting) via `/sp.adr` — propose only, do not auto-create

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundational)**: Needs T001 (deps installed); T005 blocks all user stories that touch models — strictly it only blocks US1, but the shared errors (T003) and settings (T002) block US2–US5
- **US1 (Phase 3)**: Needs Phases 1–2. Independent of US2–US5
- **US2 (Phase 4)**: Needs T001–T003. Independent of US1, US3–US5
- **US3 (Phase 5)**: Needs T001–T003. Independent of all other stories
- **US4 (Phase 6)**: Needs T001–T003. Independent of all other stories
- **US5 (Phase 7)**: Needs T001–T003; T030 touches `llm.py`/`s3.py`, so it lands after T020 and T026 (US2/US4 implementations)
- **Phase 8 (Polish)**: After all desired stories

### User Story Dependency Graph

```text
Setup (T001–T004) ─→ Foundational (T005)
        │
        ├─→ US1 (T006–T017)  ← MVP, fully independent
        ├─→ US2 (T018–T021)  ← independent
        ├─→ US3 (T022–T024)  ← independent
        ├─→ US4 (T025–T027)  ← independent
        └─→ US5 (T028–T031)  ← T030 depends on US2 T020 + US4 T026
```

### Within Each User Story

- Tests written FIRST and confirmed failing before implementation (Constitution VI)
- Models → env.py filters → migration revisions (US1); tracker → gateway (US2)
- Story verification task (run tests green) closes each story

### Parallel Opportunities

- Phase 1: T003, T004 in parallel (after T001)
- US1: T007+T008+T009 in parallel; then T011+T012+T013 in parallel; then T014+T015+T016 in parallel
- After Foundational: US1, US2, US3, US4 can proceed fully in parallel (different files); US5 tests (T028) can start in parallel, T029 too — only T030 waits on US2/US4
- Test-writing tasks T006, T018, T022, T025, T028 all touch different files — parallelizable across stories

---

## Parallel Example: User Story 1

```bash
# After T005, launch all three model modules together:
Task: "Create course_core models in backend/shared/src/exambrain_shared/models/course_core.py"
Task: "Create ingestion models in backend/shared/src/exambrain_shared/models/ingestion.py"
Task: "Create exam_sim model in backend/shared/src/exambrain_shared/models/exam_sim.py"

# Then all three env.py filters together:
Task: "include_object filter in backend/services/course-core/alembic/env.py"
Task: "include_object filter in backend/services/ingestion-pipeline/alembic/env.py"
Task: "include_object filter in backend/services/exam-simulation/alembic/env.py"

# Then all three revision-001 migrations together.
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phases 1–2 (Setup + Foundational)
2. Phase 3 (US1): migration tests → models → env filters → revisions → green
3. **STOP and VALIDATE**: quickstart §1–3 — fresh stack migrated and similarity-queryable
4. This alone unblocks every Phase 2 agent's persistence needs

### Incremental Delivery

1. US1 → migrated schema (MVP)
2. US2 → LLM gateway (unblocks all five agents)
3. US3 → session store (unblocks exam-simulation)
4. US4 → file storage (unblocks ingestion pipeline)
5. US5 → credential hardening across US2/US4
6. Polish → coverage, quality gates, quickstart validation, ADR proposals

Each story leaves the scaffold contract intact — services boot with zero config; only invoked operations fail.

---

## Notes

- FR-021 is a standing constraint on every implementation task: `test_stubs.py` must pass unchanged after each story
- Migration tests (`-m migration`) need the docker Postgres; all other tests are hermetic
- Commit after each task or logical group; stop at any checkpoint to validate the story independently
