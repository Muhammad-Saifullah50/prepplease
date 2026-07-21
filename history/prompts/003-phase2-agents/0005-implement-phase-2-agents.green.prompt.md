---
id: 0005
title: Implement Phase 2 Agents
stage: green
date: 2026-07-21
surface: cli
model: claude-fable-5
feature: 003-phase2-agents
branch: 003-phase2-agents
user: saifullah
command: /sp.implement
labels: [implementation, agents, tdd]
links:
  spec: specs/003-phase2-agents/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/agents/pyproject.toml
  - backend/agents/src/exambrain_agents/ (full library: config, errors, runner, testing, chunking, schemas/, tools/, parsing/, alignment/, blueprint/, generator/, evaluation/, repositories/, pipelines/)
  - backend/agents/tests/ (12 test modules + fixtures)
  - backend/services/course-core/alembic/versions/20260720_002_instructors.py
  - backend/services/ingestion-pipeline/alembic/versions/20260720_002_parsing_state.py
  - backend/services/exam-simulation/alembic/versions/20260720_002_generated_exams.py
  - backend/shared/src/exambrain_shared/config.py (agent settings)
  - backend/shared/src/exambrain_shared/models/ (Instructor, InstructorResolution, GeneratedExamRow, PastPaper columns)
  - backend/pyproject.toml, backend/conftest.py, backend/.pre-commit-config.yaml
  - backend/services/*/Dockerfile* (agents member + tesseract)
tests:
  - 151 passed, 2 skipped (tesseract absent locally), 6 deselected (live_llm opt-in)
  - Migration + repository integration tests green against docker Postgres
  - Agents suite passes under unshare -rn (zero network, SC-007)
  - Coverage 91% total; ruff + ruff format + mypy strict all green
---

## Prompt

/sp.implement (no user input) — execute the full 57-task breakdown in
specs/003-phase2-agents/tasks.md: five OpenAI Agents SDK agents (parsing,
alignment, blueprint, generator, evaluation) as installable library
exambrain-agents with code-driven typed pipelines, read-only tools,
blueprint→alignment agent-as-tool handoff, per-agent model overrides,
needs_review flagging, three Alembic migrations, chunking+embedding, TDD
on critical paths, offline FakeModel test suite.

## Response snapshot

All 57 tasks completed and committed phase-by-phase:

- Setup: promoted backend/agents to uv workspace member (src layout),
  extended root tooling config, added tesseract + agents member to all
  Dockerfiles, added 9 agent settings fields to shared Settings.
- Foundational: typed errors, model_for() resolver (LitellmModel,
  per-agent env override → LLM_MODEL), FakeModel implementing the SDK
  Model seam, run_agent() wrapper (error translation, corrective-retry
  helper, content-free logging), tracing disabled at import.
- US1 ingest: pypdfium2/pytesseract/python-pptx extraction tools with OCR
  routing, hierarchy-aware ~500-token chunker, parsing agent (re-extract
  tools), blueprint agent + domain validation (evidence/weights/marks),
  ingestion migration, ingest_course_file() with lifecycle, atomic chunk
  replace, advisory-lock blueprint versioning, idempotent re-runs.
- US3 generate: generated_exams migration + ORM, retrieval tool (pgvector
  cosine), generator agent with course-scoped search tool,
  generate_exam() with full blueprint/citation/rubric validation, one
  corrective retry, needs_review persistence.
- US2 alignment: instructors migration, normalize_name + rapidfuzz
  scoring tools, alignment agent, enforce_banding() (band-b can never
  merge regardless of agent output), pipeline integration + as_tool
  attachment to blueprint agent for sightings.
- US4 evaluate: evaluation agent (no tools, answers as quoted untrusted
  data), arithmetic validation, result upsert (one per session),
  needs-review envelope in question_scores JSONB.
- Polish: live_llm opt-in smoke tests for all five agents, public API
  exports verified against quickstart, repository integration tests +
  full quickstart walkthrough against real migrated DBs, coverage 91%,
  suite proven offline via network-namespace isolation, log audit clean.

Notable decisions: moved backend/tests → backend/shared/tests to resolve
a pytest importlib module-name collision with agents/tests; agents/tests
has an __init__.py to prevent shadowing the SDK's `agents` package;
blueprint agent uses non-strict output schema (free-form
marks_distribution dict); repo standard is ruff format (not black).

## Outcome

- ✅ Impact: Complete Phase 2 agents library; all four user stories
  independently functional offline; MVP (ingest→blueprint) plus
  generate/align/evaluate delivered.
- 🧪 Tests: 151 passed, 2 skipped, 6 deselected; migration +
  integration suites green on docker Postgres; offline proof via
  unshare; 91% coverage.
- 📁 Files: new workspace member backend/agents (~40 source/test
  files), 3 migrations, shared models/settings extensions, Docker/tooling
  updates.
- 🔁 Next prompts: ADR for code-driven pipelines vs Constitution III
  eventing; Phase 3 service endpoints wrapping these pipelines.
- 🧠 Reflection: pytest importlib-mode naming interacts badly with a
  workspace dir named after a third-party package (`agents`); the
  tests-__init__ + shared/tests move is the durable fix.

## Evaluation notes (flywheel)

- Failure modes observed: SDK strict-schema rejection of dict fields;
  pytest module-name collisions; FakeModel script exhaustion on
  unexpected corrective retries (fixed by aligning test evidence sets).
- Graders run and results (PASS/FAIL): ruff PASS, ruff format PASS,
  mypy strict PASS, pytest PASS, coverage ≥80% PASS, offline-suite PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): consider a shared repository
  base class if Phase 3 adds more aggregates.
