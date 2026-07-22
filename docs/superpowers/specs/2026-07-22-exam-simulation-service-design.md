# Exam Simulation Service — Design (Feature 15)

**Date:** 2026-07-22
**Feature:** #15 Exam Simulation Service (+ duration-extraction tweaks in Phase-2 agents)
**Status:** Brainstormed — awaiting spec

## Summary

The Exam Simulation Service turns a stored `GeneratedExamRow` (an original mock exam
produced by the Phase-2 generator) into a **live, server-authoritative, monitored exam
attempt**, then hands the finished answers to the existing `evaluate_submission`
pipeline for grading.

This spec also covers a companion change: threading a genuinely-extracted exam
**duration** ("Time allowed: 3 hours") through the Phase-2 agent chain
(parsing → blueprint → generator) so the live exam gets a real time limit rather than
a guessed one.

The service (`exam-simulation`) is already scaffolded (health/metrics `main.py`,
Dockerfiles, alembic migrations creating `exam_sessions` + `generated_exams`). This
feature fills in the runtime.

## Goals

- Start a timed exam attempt from a `generated_exam_id`.
- Server-authoritative countdown timer (client display is a mirror).
- Auto-save answers via a client heartbeat (Redis live buffer).
- Focus-violation tracking with terminal lockout at a configurable threshold.
- Auto-submit + background grading on manual submit, timer expiry, or lockout.
- Extract a real duration from past papers and carry it to the generated exam.

## Non-Goals

- WebSocket / server push (REST + heartbeat only).
- Returning grades synchronously from submit (client polls course-core).
- Multiple concurrent live attempts per user.
- Frontend (features 20/21 consume this API).

## Key Decisions

| # | Decision | Choice |
|---|----------|--------|
| Transport | Real-time channel | REST + client-driven heartbeat; **no WebSocket** |
| Timer | Authority | Server-authoritative deadline; client mirrors |
| Durability | Live answers | Redis `SessionStore` is the live buffer; Postgres only at submit |
| Focus | Lockout policy | Threshold → **terminal lockout + auto-submit + grade**; configurable (default 3); sub-threshold warnings returned |
| Expiry | On deadline | **Auto-submit + grade** (same path as manual submit) |
| Duration | Source | **Extracted** from past papers, threaded parsing→blueprint→generator; config fallback for legacy content |
| Duration | Blueprint merge across papers | **Max** non-null duration |
| Grading | Trigger | Submit returns fast; grade runs as a **background task**; result polled via course-core |
| Session input | Start key | `generated_exam_id` |
| Concurrency | Per user | **One active session per user**; `409 Conflict` otherwise |
| Answers storage | Column | Stored inside existing `exam_content` JSONB — **no new migration** |

## Architecture

```
Client ──REST──> exam-simulation (FastAPI)
                   │  auth: Clerk require_auth + ownership check
                   │  routers/exam_sessions.py
                   │
                   ├── SessionStore (Redis)  ← live doc, TTL = duration + grace
                   ├── ExamSimRepository (Postgres exam_sim DB) ← durable ExamSession
                   └── tasks.py (background) ──> evaluate_submission(...)
                                                     └──> course-core upsert_result
Client polls result via course-core results/dashboard.
```

- **Redis = live buffer**: fast, TTL-bounded, holds in-flight answers/focus/deadline.
- **Postgres `ExamSession` = durable terminal record**: written at start, updated at
  terminal transition; answers frozen into `exam_content` JSONB at submit.
- **Terminal paths funnel into one submit/grade path** — manual submit, timer expiry,
  and focus lockout differ only in the recorded status
  (`submitted` / `expired` / `locked_out`).

## API Surface

All under `/v1`, Clerk `require_auth`, ownership-checked (`session.user_id == current user`).

### `POST /v1/exam-sessions`
- Body: `{ "generated_exam_id": "<uuid>" }`
- Enforces one active session/user → `409 Conflict` + existing session id if one is live.
- Creates `ExamSession` (status `active`, `started_at`), copies **questions only**
  (never rubric/answers) into `exam_content`, computes deadline from extracted duration.
- Writes Redis live doc + Postgres row.
- Returns: session id, questions, `duration_minutes`, `remaining_seconds`, `deadline`.

### `GET /v1/exam-sessions/{id}`
- **Resume** (page reload): current live state from Redis — questions, saved answers,
  `remaining_seconds`, `status`, focus warnings.

### `POST /v1/exam-sessions/{id}/heartbeat`
- Body: `answers` buffer (full or partial) + `focus_violations_delta` (new violations
  since last beat).
- Server: lazily checks deadline → `expired`; increments focus counter → `locked_out`
  at threshold; writes answer buffer to Redis.
- Returns: `remaining_seconds`, `status`, `focus_warnings` (`n of MAX`).

### `POST /v1/exam-sessions/{id}/submit`
- Finalize: freeze answers → Postgres, `status=submitted`, `ended_at`, delete Redis doc,
  kick off background grade.
- Returns `202` "submitted, grading in progress". Grade not returned here.

**Lazy expiry:** any request arriving past the deadline is treated as expiry even
without a heartbeat. **Idempotency:** once terminal, heartbeat/submit return the
terminal state instead of re-grading.

## Live State, Timer, Focus, Lockout

- **Redis doc** (`session:{id}`, TTL = duration + small grace):
  `{ generated_exam_id, user_id, course_id, questions, answers, focus_violations, deadline, status }`.
- **Timer**: `remaining_seconds = max(0, deadline - now)`. `<= 0` on any request →
  `expired` → submit/grade path.
- **Focus**: heartbeat sends *deltas*; server increments `focus_violations`. Below
  `MAX_FOCUS_VIOLATIONS` (config, default 3) → return warning. At/over → `locked_out`
  → submit/grade path. Terminal, no resume.

## Duration Extraction (agent-chain changes)

1. **Parsing agent** — add `duration_minutes: int | None` to `ParsedDocument`; prompt
   extracts the printed time limit (e.g. "Time allowed: 3 hours" → 180). `None` if absent.
2. **Blueprint agent** — add `duration_minutes: int | None` to `BlueprintStructure`;
   **merge across source papers = max non-null** (falls back to `None` if none stated).
3. **Generator** — include `duration_minutes` in `GeneratedExamRow.content`.
4. **Fallback in feature 15** — if content lacks a duration, use config
   `EXAM_DURATION_MINUTES` (default 120), clamped to `[EXAM_DURATION_MIN, EXAM_DURATION_MAX]`
   (e.g. 15–240). Guarantees legacy/already-generated exams still run.

## Code Touch-points

- **Service** (`exam_simulation/`): `auth.py` (reuse Clerk pattern),
  `routers/exam_sessions.py`, `tasks.py` (background grade wrapper), wire routers in `main.py`.
- **Repository**: extend `ExamSimRepository` — `create_session`,
  `get_active_session_for_user`, `update_session_terminal`, fill out `get_session`.
- **Shared**: reuse `SessionStore`; add config keys `MAX_FOCUS_VIOLATIONS`,
  `EXAM_DURATION_MINUTES`, `EXAM_DURATION_MIN`, `EXAM_DURATION_MAX`.
- **Agents**: parsing/blueprint schema + prompt edits; generator content edit.
- **DB**: no new tables; answers reuse `exam_content` JSONB → **no migration**.

## Testing

- Unit: timer math, focus threshold, duration derivation/merge, config fallback + clamp.
- Router tests: fake Redis + repo (mirror existing `conftest.py`), auth/ownership,
  409 conflict, lazy expiry, idempotent terminal.
- Extraction: parsing/blueprint schema + merge-rule tests.
- End-to-end: start → heartbeat (autosave + focus) → submit → background grade with a
  stubbed evaluator.

## Dependencies / Consumers

- **Consumes**: `GeneratedExamRow` (generator, feature 11), `SessionStore` (feature 4),
  `evaluate_submission` (feature 12), Clerk auth (feature 13 pattern).
- **Consumed by**: Exam Player UI (feature 20), Focus Tracking UI (feature 21),
  course-core results/dashboard (grade polling).
