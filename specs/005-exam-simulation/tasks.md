---
description: "Task list for 005-exam-simulation feature implementation"
---

# Tasks: Exam Simulation Service

**Input**: Design documents from `/specs/005-exam-simulation/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included per TDD mandate in plan.md (Constitution check VI — TDD Critical Paths).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to user story (US1, US2, US3)
- Exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency wiring

- [X] T001 Add redis-py, httpx, tenacity, structlog, pydantic-settings to `backend/services/exam-simulation/pyproject.toml`
- [X] T002 [P] Add exam_sim settings (EXAM_ATTEMPT_DEFAULT_TIMEOUT_MINUTES, EXAM_FOCUS_VIOLATION_LIMIT, EXAM_DEADLINE_POLL_INTERVAL_SECONDS, REDIS_URL) to `backend/shared/src/exambrain_shared/config.py`
- [X] T003 [P] Add new env vars to `backend/services/exam-simulation/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema migrations and data-layer infrastructure that must complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create Alembic migration 003 — add `deadline`, `finished_by`, `answers`, `time_limit_minutes` columns to `exam_sessions` in `backend/services/exam-simulation/alembic/versions/20260720_003_attempt_deadline_answers.py`
- [X] T005 Create Alembic migration 004 — add `time_limit_minutes` column to `generated_exams` in `backend/services/exam-simulation/alembic/versions/20260720_004_time_limit_fields.py`
- [X] T006 [P] Add `time_limit_minutes` field to `ExamSession` and `GeneratedExamRow` ORM models in `backend/shared/src/exambrain_shared/models/exam_sim.py`
- [X] T007 [P] Implement Redis cache helpers for attempt state (write-through, read-through, invalidate) in `backend/shared/src/exambrain_shared/redis.py`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Take a timed mock exam (Priority: P1) 🎯 MVP

**Goal**: A student can start a live timed attempt from a generated mock exam, save answers continuously, resume after interruption, submit early, and have it auto-finish on deadline.

**Independent Test**: Start an exam attempt from a generated exam; confirm questions and countdown appear; save some answers, reload, confirm answers and remaining time persist; let countdown reach zero; confirm attempt auto-finishes and queues for grading.

### Tests for User Story 1 (TDD: write first, ensure red) ⚠️

- [X] T008 [P] [US1] Unit test for attempt start logic (valid generated exam, duplicate active attempt rejection) in `backend/services/exam-simulation/tests/test_attempt_lifecycle.py`
- [X] T009 [P] [US1] Unit test for answer save (partial upsert, non-active attempt rejection) in `backend/services/exam-simulation/tests/test_attempt_lifecycle.py`
- [X] T010 [P] [US1] Unit test for manual submit (active attempt, already-finished idempotency) in `backend/services/exam-simulation/tests/test_attempt_lifecycle.py`
- [X] T011 [P] [US1] Unit test for deadline checker background task (auto-finish, startup catch-up scan) in `backend/services/exam-simulation/tests/test_deadline_checker.py`
- [X] T012 [P] [US1] Integration/API test for full US1 flow (start → poll → save answers → submit) via httpx AsyncClient in `backend/services/exam-simulation/tests/test_api.py`

### Implementation for User Story 1

- [X] T013 [US1] Create attempt request/response schemas (StartAttemptRequest, AttemptStateResponse, SaveAnswersRequest, FinishResponse) in `backend/services/exam-simulation/src/exam_simulation/schemas/attempts.py`
- [X] T014 [US1] Implement dependency injection (auth middleware stubs, repo injection) in `backend/services/exam-simulation/src/exam_simulation/dependencies.py`
- [X] T015 [US1] Implement AttemptLifecycle service (start, save_answers, finish with FOR UPDATE idempotency) in `backend/services/exam-simulation/src/exam_simulation/services/attempt_lifecycle.py`
- [X] T016 [US1] Implement DeadlineChecker background task (10s poll, startup scan, finish expired attempts) in `backend/services/exam-simulation/src/exam_simulation/services/deadline_checker.py`
- [X] T017 [US1] Implement attempt routers (POST start, GET state, PUT answers, POST finish) in `backend/services/exam-simulation/src/exam_simulation/routers/attempts.py`
- [X] T018 [US1] Wire attempt router + deadline checker lifespan into `backend/services/exam-simulation/src/exam_simulation/main.py`

**Checkpoint**: US1 fully functional — student can sit a timed mock exam end-to-end

---

## Phase 4: User Story 2 — Exam integrity: focus-violation lockout (Priority: P1)

**Goal**: A student who repeatedly switches away from the exam receives warnings, and after the configured limit (default: 3), their attempt is locked and auto-finished.

**Independent Test**: Start an attempt and report focus-loss events one at a time; confirm warnings under limit; cross the limit and confirm lockout + grading queue.

### Tests for User Story 2 (TDD: write first, ensure red) ⚠️

- [X] T019 [P] [US2] Unit test for focus violation recording (increment count, under-limit response) in `backend/services/exam-simulation/tests/test_focus_tracker.py`
- [X] T020 [P] [US2] Unit test for lockout on limit cross (status change, auto-finish, re-entry rejection) in `backend/services/exam-simulation/tests/test_focus_tracker.py`
- [X] T021 [P] [US2] Integration/API test for focus-violation flow (report → poll state → cross limit → lockout) via httpx AsyncClient in `backend/services/exam-simulation/tests/test_api.py`

### Implementation for User Story 2

- [X] T022 [US2] Create focus violation request/response schemas in `backend/services/exam-simulation/src/exam_simulation/schemas/focus.py`
- [X] T023 [US2] Implement FocusTracker service (report_violation, check_limit, lockout) in `backend/services/exam-simulation/src/exam_simulation/services/focus_tracker.py`
- [X] T024 [US2] Implement focus violation router (POST report) in `backend/services/exam-simulation/src/exam_simulation/routers/focus.py`
- [X] T025 [US2] Wire focus router into `backend/services/exam-simulation/src/exam_simulation/main.py`

**Checkpoint**: US1 + US2 both functional — timed attempts with integrity monitoring

---

## Phase 5: User Story 3 — Exam duration reflects real exam conditions (Priority: P2)

**Goal**: Past paper time limits are extracted, merged into blueprints, carried through to generated exams, and applied to live attempt countdowns.

**Independent Test**: Ingest past papers with stated time limits; confirm blueprint reflects longest duration; confirm generated exam carries it; confirm attempt countdown uses it.

### Tests for User Story 3 (TDD: write first, ensure red) ⚠️

- [X] T026 [P] [US3] Unit test for parsing agent time-limit extraction (LLM instruction integration) in `backend/agents/tests/test_agent_parsing.py`
- [X] T027 [P] [US3] Unit test for blueprint duration merging (longest wins, all-null → null) in `backend/agents/tests/test_agent_blueprint.py`
- [X] T028 [P] [US3] Unit test for attempt start with known time limit vs default fallback (ExamAttempt creation) in `backend/services/exam-simulation/tests/test_attempt_lifecycle.py`

### Implementation for User Story 3

#### Data model changes (cross-service)

- [X] T029 [P] [US3] Add `time_limit_minutes: int | None` to `PastPaper` ORM model in `backend/shared/src/exambrain_shared/models/ingestion.py`
- [X] T030 [P] [US3] Add `time_limit_minutes: int | None` to `ExamBlueprint` ORM model in `backend/shared/src/exambrain_shared/models/course_core.py`

#### Agent schema & prompt changes

- [X] T031 [P] [US3] Add `time_limit_minutes: int | None` to `ParsedDocument` schema in `backend/agents/src/exambrain_agents/schemas/parsing.py`; update parsing prompt to extract + normalize time limit in `backend/agents/src/exambrain_agents/parsing/prompt.py`
- [X] T032 [P] [US3] Add `time_limit_minutes: int | None` to `BlueprintStructure` schema in `backend/agents/src/exambrain_agents/schemas/blueprint.py`; update blueprint prompt to merge longest duration in `backend/agents/src/exambrain_agents/blueprint/prompt.py`
- [X] T033 [P] [US3] Add `time_limit_minutes: int | None` to `GeneratedExam` schema in `backend/agents/src/exambrain_agents/schemas/generation.py`; update generator prompt for pass-through in `backend/agents/src/exambrain_agents/generator/prompt.py`
- [X] T034 [US3] Update ingest pipeline to persist `time_limit_minutes` from parsed document to past paper in `backend/agents/src/exambrain_agents/pipelines/ingest.py`

**Checkpoint**: US3 complete — all generated mock exams carry authentic time limits from source papers

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration, edge cases, operational readiness

- [ ] T035 [P] Add `REDIS_URL` to `backend/infra/docker/docker-compose.yml` for exam-simulation service (file not found — deferred)
- [X] T036 [P] Update `conftest.py` with Redis test fixtures and async test helpers in `backend/services/exam-simulation/tests/conftest.py`
- [X] T037 Add edge-case integration tests (concurrent finish requests, deadline+manual race, interrupted session recovery, own-attempt-only access) in `backend/services/exam-simulation/tests/test_api.py`
- [ ] T038 Run quickstart.md validation — confirm all API flows work end-to-end (requires running service)
- [ ] T039 Code cleanup: ruff, black, mypy strict pass across all modified files (requires CI)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — core attempt lifecycle, no story dependencies
- **US2 (Phase 4)**: Depends on Foundational — uses attempt state from US1 but independently testable
- **US3 (Phase 5)**: Depends on Foundational — data model + agent changes, independent of US1/US2 runtime
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — No dependencies on other stories
- **US2 (P1)**: Can start after Foundational — uses US1's attempt model but independently testable with mocks
- **US3 (P2)**: Can start after Foundational — independent agent/schema changes

### Within Each User Story

- Tests written FIRST and FAIL before implementation (TDD)
- Schemas before services
- Services before routers
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T002 and T003 can run in parallel (Setup)
- T006 and T007 can run in parallel (Foundational)
- US1 tests (T008-T012) can run in parallel with each other
- US1 implementation (T013-T018): T013 and T014 can run in parallel; T015-T016 can run in parallel after T014
- US2 tests (T019-T021) can run in parallel
- US2 implementation: T022 can start after T015 (shares attempt service)
- US3 data model tasks (T029-T030) can run in parallel with US3 agent schema tasks (T031-T033)
- US3 is fully independent of US1/US2 runtime logic

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (TDD):
Task: T008 Unit test for attempt start in test_attempt_lifecycle.py
Task: T009 Unit test for answer save in test_attempt_lifecycle.py
Task: T010 Unit test for manual submit in test_attempt_lifecycle.py
Task: T011 Unit test for deadline checker in test_deadline_checker.py
Task: T012 Integration test for US1 flow in test_api.py

# Launch schemas + deps together:
Task: T013 Create attempt schemas in schemas/attempts.py
Task: T014 Implement dependency injection in dependencies.py

# Launch services together:
Task: T015 Implement AttemptLifecycle service
Task: T016 Implement DeadlineChecker background task
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (attempt lifecycle)
4. **STOP and VALIDATE**: Test US1 independently — start, poll, save, submit, deadline expiry
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (attempt lifecycle) → Test independently → **MVP**
3. Add US2 (focus violations) → Test independently → Deploy
4. Add US3 (time-limit extraction) → Test independently → Deploy
5. Each story adds value without breaking previous ones

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (attempt lifecycle)
   - Developer B: US2 (focus violations)
   - Developer C: US3 (time-limit extraction + agent prompts)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (TDD red-green-refactor)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
