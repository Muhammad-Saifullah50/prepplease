# Tasks: Foundation Services

**Input**: Design documents from `/specs/004-foundation-services/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — spec.md defines independent test criteria and acceptance scenarios for each user story (SC-009 mandates offline test suite). Test tasks precede implementation within each story.

**Organization**: Phases follow user-story priority order from spec.md: US1 (P1 upload) → US2 (P1 dashboard) → US3 (P2 course management) → US4 (P2 auth/profile). Auth infrastructure (require_auth dependency + lazy user creation) is foundational and blocks all stories.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1/US2/US3/US4 — only on user-story phase tasks

## Path Conventions

Backend uv workspace at `backend/`; services at `backend/services/course-core/` and `backend/services/ingestion-pipeline/`. All paths below are repo-relative (e.g., `services/course-core/...`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add Clerk + Svix + multipart dependencies; extend shared config with Clerk settings; create `.env.example` additions; wire router directories for both services.

- [X] T001 [P] Add `clerk-backend-api`, `svix` dependencies to `services/course-core/pyproject.toml` and `services/ingestion-pipeline/pyproject.toml`; add `python-multipart` to `services/ingestion-pipeline/pyproject.toml`; run `uv sync` to resolve
- [X] T002 Extend `shared/src/exambrain_shared/config.py` Settings with `clerk_secret_key`, `clerk_jwt_key`, `clerk_webhook_signing_secret`, `clerk_authorized_parties` (all `str | None = None`); add `clerk_secret_key` to `_SECRET_FIELDS`; update shared settings tests if any
- [X] T003 [P] Update `services/course-core/.env.example` and `services/ingestion-pipeline/.env.example` with Clerk env vars (`CLERK_SECRET_KEY`, `CLERK_JWT_KEY`, `CLERK_WEBHOOK_SIGNING_SECRET`, `CLERK_AUTHORIZED_PARTIES`) per quickstart.md
- [X] T004 [P] Create `services/course-core/src/course_core/routers/__init__.py` and `services/ingestion-pipeline/src/ingestion_pipeline/routers/__init__.py` as empty package markers

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented — Clerk auth dependency with lazy user creation, Alembic migrations for new columns, streaming S3 upload helper, background task runner.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement `require_auth` FastAPI dependency in `services/course-core/src/course_core/auth.py` — validates Clerk JWT via `clerk_backend_api.authenticate_request()` with `AuthenticateRequestOptions` (research.md pattern); extracts Clerk user ID; performs lazy user creation if Clerk ID not found in local DB; returns `RequestState`; raises `HTTPException(401)` on invalid/missing token
- [X] T006 Implement `require_auth` FastAPI dependency in `services/ingestion-pipeline/src/ingestion_pipeline/auth.py` — follows same pattern as T005; lazy user creation calls course-core DB (shared repo) or duplicates the lookup logic; returns Clerk user ID string
- [X] T007 Create course-core Alembic migration `services/course-core/alembic/versions/20260721_002_foundation_services.py`: add `users.clerk_id` (VARCHAR, unique, nullable), `users.is_active` (BOOLEAN, default true), `users.preferences` (JSONB, default `{}`); add `courses.archived_at` (TIMESTAMPTZ, nullable), `courses.paper_count` (INTEGER, default 0); add partial index on `courses` WHERE `archived_at IS NULL` per data-model.md
- [X] T008 Create ingestion-pipeline Alembic migration `services/ingestion-pipeline/alembic/versions/20260721_002_content_hash_index.py`: add unique index on `past_papers.content_hash` per data-model.md
- [X] T009 Implement streaming S3 upload helper in `services/ingestion-pipeline/src/ingestion_pipeline/s3.py` — wraps existing `S3Adapter.upload()` from `exambrain_shared.s3`; computes SHA-256 content hash during streaming upload via `hashlib`; returns `(s3_key, content_hash)` pair; raises typed errors on failure per shared error hierarchy
- [X] T010 Implement background task runner in `services/ingestion-pipeline/src/ingestion_pipeline/tasks.py` — `run_ingestion(paper_id, course_id)` wrapper around `ingest_course_file()` from `exambrain_agents.pipelines.ingest`; updates `PastPaper` status through lifecycle (pending → processing → completed/failed); per-course serialization via advisory lock reusing pattern from `CourseCoreRepository.write_blueprint_version`; uses `asyncio.create_task()` for lightweight MVP in-process dispatch

**Checkpoint**: Foundation ready — both services can validate Clerk JWTs, migrations are applied, S3 uploads stream with hash computation, background tasks can dispatch. User story implementation can now begin.

---

## Phase 3: User Story 1 — Upload a past paper and track its processing (Priority: P1) 🎯 MVP

**Goal**: A user uploads a PDF/PPTX past paper for a course; the system streams it to S3 (with content-hash dedup), returns a tracking ID immediately, processes asynchronously via `ingest_course_file()`, and exposes a polling status endpoint.

**Independent Test**: Upload a past-paper PDF via `POST /v1/courses/{course_id}/upload`; poll `GET /v1/papers/{paper_id}/status` until it reads "completed"; verify the paper appears with status in the course's paper list (spec US1 Independent Test).

### Tests (write first, verify they fail)

- [X] T011 [P] [US1] Write tests for `services/ingestion-pipeline/tests/test_upload.py`: upload success returns 202 + paper_id + status=pending; duplicate upload returns existing paper_id with duplicate=true; unsupported file type (e.g., `.txt`) returns 415; oversized file (>50MB) returns 413; unauthenticated request returns 401; course ownership check rejects 403 for non-owned course
- [X] T012 [P] [US1] Write tests for `services/ingestion-pipeline/tests/test_status.py`: polling returns status=processing with elapsed_seconds during processing; completed returns status=completed; failed returns status=failed + failure_reason; unknown paper_id returns 404; unauthenticated request returns 401

### Implementation

- [X] T013 [US1] Implement `POST /v1/courses/{course_id}/upload` in `services/ingestion-pipeline/src/ingestion_pipeline/routers/upload.py` — multipart file reception; compute SHA-256 content hash; reject unsupported types (415) and oversized files (413) before S3 storage; check duplicate by content hash (return existing paper_id with duplicate=true); stream to S3 via helper from T009; create `PastPaper` record (status=pending); queue background processing via T010; return 202 with tracking ID
- [X] T014 [US1] Implement `GET /v1/papers/{paper_id}/status` in `services/ingestion-pipeline/src/ingestion_pipeline/routers/status.py` — lookup paper by ID (scope-check course ownership); return status, elapsed_seconds, failure_reason; < 500ms response per FR-023
- [X] T015 [US1] Wire `require_auth` from T006 into ingestion-pipeline `main.py`: register `routers/upload.py` and `routers/status.py` routers; add `require_auth` as global dependency or per-route; register lifespan handler if needed; verify /health remains public
- [X] T016 [US1] Wire background processing in `services/ingestion-pipeline/src/ingestion_pipeline/tasks.py` (completes T010): ensure `ingest_course_file` updates paper status + paper_count on course; handle failures gracefully with failure_reason; log processing lifecycle

**Checkpoint**: US1 complete — a user can upload a paper, poll to completion, and see the ingested paper. First MVP increment ready.

---

## Phase 4: User Story 2 — View course dashboard with performance analytics (Priority: P1)

**Goal**: A user views their course dashboard showing aggregate scores, per-topic strength/weakness breakdown, latest blueprint structure, and past-paper list.

**Independent Test**: With a course that has an uploaded paper, a blueprint, and at least one graded exam result, call the dashboard summary endpoint; verify it returns aggregate score, weak topics, and latest blueprint reference (spec US2 Independent Test).

### Tests (write first, verify they fail)

- [X] T017 [P] [US2] Write tests for `services/course-core/tests/test_dashboard.py`: dashboard summary returns per-course aggregates (paper_count, blueprint_version/exists, completed_exams, average_score); performance endpoint returns aggregate_score, topic_breakdown with strength/weakness labels, recent_exams list; blueprint endpoint returns sections, question_types, marks_distribution, topic_weights, confidence_score; empty course returns "no blueprint" indicator, not broken data; unauthenticated requests return 401; course ownership check returns 403

### Implementation

- [X] T018 [P] [US2] Implement `GET /v1/dashboard/summary` in `services/course-core/src/course_core/routers/dashboard.py` — iterate user's courses; aggregate paper_count, latest_blueprint_version/has_blueprint, completed_exams count, average_score from Results; respond in < 2s for 10 courses / 100 results per FR-022
- [X] T019 [P] [US2] Implement `GET /v1/courses/{course_id}/performance` in `services/course-core/src/course_core/routers/dashboard.py` — aggregate all results for the course; compute per-topic strength/weakness breakdown from evaluation data; return recent exam history
- [X] T020 [P] [US2] Implement `GET /v1/courses/{course_id}/blueprint` in `services/course-core/src/course_core/routers/dashboard.py` — return latest ExamBlueprint sections, question_types, marks distribution, topic_weights, confidence_score per contracts/course-core-api.md
- [X] T021 [P] [US2] Implement `GET /v1/courses/{course_id}/papers` in `services/course-core/src/course_core/routers/papers.py` — list all PastPaper records for the course with status, file_type, file_name, timestamps per contracts/course-core-api.md
- [X] T022 [US2] Wire course-core routers into `main.py`: register `dashboard.py` and `papers.py` routers; add `require_auth` dependency; verify /health remains public

**Checkpoint**: US2 complete — a user can see their dashboard with analytics, blueprint, and paper list. Both P1 stories functional.

---

## Phase 5: User Story 3 — Manage courses and browse blueprints (Priority: P2)

**Goal**: A user creates, reads, updates, and archives courses; browses blueprint version history.

**Independent Test**: Create a course via API, verify it appears in course list; update its name; verify change reflected; soft-delete (archive) it; verify it no longer appears in default list (spec US3 Independent Test).

### Tests (write first, verify they fail)

- [X] T023 [P] [US3] Write tests for `services/course-core/tests/test_courses.py`: create course returns 201 with expected fields; list courses returns user-scoped active/archived courses; get course returns detail with blueprint_summary; update course (rename, instructor) returns updated object; archive (DELETE) sets archived_at — course hidden from default list, data preserved; access denied for non-owned course returns 403; unauthenticated returns 401; already-archived returns 409; blueprint history returns all versions with version numbers and confidence scores

### Implementation

- [X] T024 [P] [US3] Implement `POST /v1/courses` and `GET /v1/courses` in `services/course-core/src/course_core/routers/courses.py` — create course with title, code, instructor_name; list user's active courses (optionally include archived); scope all queries to authenticated user per FR-006
- [X] T025 [P] [US3] Implement `GET /v1/courses/{course_id}` and `PATCH /v1/courses/{course_id}` in `services/course-core/src/course_core/routers/courses.py` — get full course detail with blueprint_summary, paper_count, exam_count; update title, instructor_name; ownership check on every operation
- [X] T026 [P] [US3] Implement `DELETE /v1/courses/{course_id}` (archive) in `services/course-core/src/course_core/routers/courses.py` — soft-delete by setting archived_at per FR-007; reject if already archived (409); all associated data preserved
- [X] T027 [P] [US3] Implement `GET /v1/courses/{course_id}/blueprints` in `services/course-core/src/course_core/routers/courses.py` — return all blueprint versions for the course with version, created_at, confidence_score per contracts/course-core-api.md
- [X] T028 [US3] Wire course routers into `services/course-core/src/course_core/main.py` (if not already done in T022 — otherwise ensure T024–T027 are registered)

**Checkpoint**: US3 complete — users can manage courses and browse blueprints. Course CRUD unblocks the full upload pipeline.

---

## Phase 6: User Story 4 — Register account and manage profile (Priority: P2)

**Goal**: Clerk webhook events sync user lifecycle (created/updated/deleted). Users view and update their profile (display_name, preferences). Lazy user creation was already implemented in foundational auth dependency (T005); webhooks handle offline sync.

**Independent Test**: Simulate Clerk webhook for new user; verify local user record is created. Call profile endpoint; verify user data matches (spec US4 Independent Test).

### Tests (write first, verify they fail)

- [X] T029 [P] [US4] Write tests for `services/course-core/tests/test_webhooks.py`: valid Svix-signed webhook creates/updates/deletes local user; invalid Svix signature returns 401; unknown event type returns 422; `user.deleted` sets is_active=false (soft-delete, not hard-delete); duplicate webhook for already-synced user is no-op (upsert)
- [X] T030 [P] [US4] Write tests for `services/course-core/tests/test_users.py`: GET /v1/users/me returns current user profile; PATCH /v1/users/me updates display_name and preferences; unauthenticated request returns 401; lazy creation of user on first API call (if not exists) — verify email and display_name populated

### Implementation

- [X] T031 [US4] Implement `POST /v1/webhooks/clerk` in `services/course-core/src/course_core/webhooks.py` — verify Svix signature via `svix.Webhook.verify()` using `CLERK_WEBHOOK_SIGNING_SECRET`; handle `user.created` → upsert local User; `user.updated` → update local fields (email, display_name); `user.deleted` → set `is_active=false`; return 200 `{"status": "ok"}` on success; return 401 on invalid signature; log all events
- [X] T032 [P] [US4] Implement `GET /v1/users/me` and `PATCH /v1/users/me` in `services/course-core/src/course_core/routers/users.py` — read current user profile (id, clerk_id, email, display_name, preferences); update display_name and/or preferences; scope to authenticated user
- [X] T033 [US4] Wire webhooks and users routers into `services/course-core/src/course_core/main.py` — register `webhooks.py` as public route (no auth, Svix-signed) per FR-021; register `users.py` with `require_auth` dependency

**Checkpoint**: US4 complete — Clerk webhooks sync user lifecycle; users can view and update profile. Auth loop fully closed.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, coverage, quickstart validation, logging audit, security hardening.

- [X] T034 Run Alembic migrations for both services against local Postgres via `docker compose up` per quickstart.md; verify no errors
- [X] T035 Verify ≥80% coverage on both services: `uv run pytest --cov=course_core --cov=ingestion_pipeline`; close gaps
- [X] T036 Quality gates: `uv run ruff check services/` and `uv run mypy services/course-core/src/ services/ingestion-pipeline/src/` — fix all violations
- [X] T037 Audit auth: verify every non-health endpoint enforces `require_auth`; verify `WHITELIST` of public paths is minimal (only /health, /metrics, webhooks); verify auth tests cover 401 on every protected route
- [X] T038 Audit logging: grep-level check that no log call in course-core or ingestion-pipeline emits raw document text, LLM prompts, student answers, or secrets; verify REDACTED fields pattern from shared config is used
- [X] T039 Run full offline test suite with network blocked: `uv run pytest -m 'not live_llm'` — verify SC-009 compliance (no network-dependent tests except migration tests that require local Postgres)
- [X] T040 Run quickstart.md API flow end-to-end: start both services, create course, upload paper, poll status, check dashboard — verify SC-001 through SC-008

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: none — start immediately; T001, T003, T004 in parallel
- **Phase 2 (Foundational)**: depends on Phase 1 — BLOCKS all stories
  - T007 migration depends on T002 (Settings extended for Clerk — migration doesn't use Clerk but env/conn setup benefits from shared config)
  - T009 S3 helper depends on existing shared `S3Adapter` (already in place)
  - T010 task runner depends on existing `exambrain_agents.pipelines.ingest` (already in place)
- **Phase 3 (US1 P1)**: depends on Phase 2; requires course to exist (can be seeded via test fixture or manual DB insert — course CRUD is P2)
- **Phase 4 (US2 P1)**: depends on Phase 2; reads data produced by US1 (blueprints, papers) and US3 (courses)
- **Phase 5 (US3 P2)**: depends on Phase 2; no dependency on US1/US2 for implementation but needed at runtime for full flow
- **Phase 6 (US4 P2)**: depends on Phase 2 T005 (require_auth with lazy user creation is a prerequisite for webhook sync flow); T030/T033 depend on T005
- **Phase 7 (Polish)**: depends on all story phases (or at least Phase 2 for migration checks)

### Story Dependency Graph

```text
Setup → Foundational ─┬→ US1 (upload/ingest, P1 MVP)
                       ├→ US2 (dashboard/analytics, P1; reads US1/US3 data)
                       ├→ US3 (course CRUD, P2; needed by US1 at runtime)
                       └→ US4 (auth webhooks, P2; foundational auth in Phase 2)
```

### Within Each User Story

Tests first (must fail) → implementation → wire into service main.py.

### Parallel Opportunities

- Phase 1: T001, T003, T004 in parallel
- Phase 2: T005/T006 (auth for both services) in parallel; T007/T008 (two service migrations) in parallel; T009/T010 in parallel
- US1: T011/T012 (tests for upload/status) in parallel; T013/T014 (upload/status impl) in parallel
- US2: T017 (tests) then T018–T021 (all [P] parallel from different files)
- US3: T023 (tests) then T024–T027 (all [P] parallel)
- US4: T029/T030 (webhook/user tests) in parallel; T031/T032 in parallel

### Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: "Upload endpoint tests in test_upload.py"         # T011
Task: "Status endpoint tests in test_status.py"          # T012

# Then parallel implementation:
Task: "POST /upload router in routers/upload.py"        # T013
Task: "GET /status router in routers/status.py"          # T014
Task: "Wire auth + routers into main.py"                 # T015
Task: "Background processing wiring in tasks.py"         # T016
```

---

## Implementation Strategy

### MVP First (US1 + US2 only)

1. Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2)
2. **STOP and VALIDATE**: Both P1 stories work end-to-end — upload a paper, poll to completion, check dashboard analytics
3. This delivers the core value: ingestion + analytics

### Incremental Delivery

1. Setup + Foundational → auth and infrastructure ready
2. US1 + US2 → MVP: upload and dashboard ✅
3. US3 → course management (unblocks full UX) ✅
4. US4 → webhook sync completes the auth loop ✅
5. Polish → coverage, quality gates, quickstart verification

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (upload/ingest) + US2 (dashboard)
   - Developer B: US3 (course CRUD) + US4 (webhooks/profile)
3. Stories integrate independently after Phase 2

---

## Notes

- Total: 40 tasks (Setup 4, Foundational 6, US1 6, US2 6, US3 6, US4 5, Polish 7)
- Lazy user creation lives in the foundational `require_auth` dependency (T005/T006), not in a user story — all endpoints benefit automatically
- US1 upload endpoint routing is in `ingestion-pipeline` service (port 8002); all other endpoints are in `course-core` (port 8001)
- Every persistence write uses existing repositories from `exambrain_agents.repositories` (CourseCoreRepository, IngestionRepository)
- Auth is enforced by default on all routes; public routes (/health, /metrics) explicitly whitelisted; webhook endpoint is Svix-signed (no Bearer token)
- Commit after each task or logical group; stop at any phase checkpoint to validate the story independently
