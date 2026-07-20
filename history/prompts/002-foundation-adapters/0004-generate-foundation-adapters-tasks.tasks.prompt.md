---
id: 0004
title: Generate foundation adapters tasks
stage: tasks
date: 2026-07-20
surface: vscode-claude-code
model: claude-opus-4-8[1m]
feature: 002-foundation-adapters
branch: 002-foundation-adapters
user: Muhammad
command: /sp.tasks
labels: [tasks, foundation-adapters, sdd]
links:
  spec: specs/002-foundation-adapters/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/002-foundation-adapters/tasks.md
tests:
  - none (task generation only)
---

## Prompt

/sp.tasks (no additional user input)

Generate an actionable, dependency-ordered tasks.md for feature 002-foundation-adapters based on plan.md, spec.md, research.md, data-model.md, contracts/ (llm-gateway, session-store, file-storage, credentials), and quickstart.md. Tasks must be organized by user story with strict checklist format `- [ ] T### [P?] [US?] description + file path`, phases for Setup/Foundational/per-story/Polish, dependency graph, parallel examples, and MVP-first implementation strategy.

## Response snapshot

Generated specs/002-foundation-adapters/tasks.md with 35 tasks across 8 phases:

- Phase 1 Setup (T001–T004): deps, Settings fields, new error types, pytest migration marker
- Phase 2 Foundational (T005): models subpackage + timestamp mixin + service-tagging convention
- Phase 3 US1 Domain Data Foundation P1/MVP (T006–T017, 12 tasks): migration round-trip tests first, 3 model modules, 3 env.py include_object filters, 3 revision-001 migrations (pgvector ext + HNSW in ingestion), verification run
- Phase 4 US2 Reliable LLM Access P2 (T018–T021, 4 tasks): TDD gateway tests, UsageTracker, real LiteLLM+tenacity LLMClient
- Phase 5 US3 Session & Rate-Limit Store P3 (T022–T024, 3 tasks): fakeredis tests, SessionStore + RateLimiter
- Phase 6 US4 Course File Storage P4 (T025–T027, 3 tasks): fake-client tests, streaming aioboto3 adapter
- Phase 7 US5 Credential Safety P5 (T028–T031, 4 tasks): validation/rotation/no-leak tests, CredentialManager, rotation wiring through llm.py/s3.py
- Phase 8 Polish (T032–T035): suite-wide secret-leak check, quality gates (cov 80/mypy/ruff/black), quickstart validation, ADR proposals

Tests included per Constitution VI / FR-022 (TDD on critical paths). US1–US4 fully independent; US5's T030 depends on US2/US4 implementations. ~17 [P]-parallelizable tasks. MVP = US1.

## Outcome

- ✅ Impact: tasks.md ready for /sp.implement; all tasks LLM-executable with exact file paths
- 🧪 Tests: none run (artifact generation); test tasks embedded per story
- 📁 Files: specs/002-foundation-adapters/tasks.md (new)
- 🔁 Next prompts: /sp.analyze for cross-artifact consistency, then /sp.implement
- 🧠 Reflection: contracts were precise enough that each adapter maps to exactly one test task + one implementation task; migration story dominates task count due to 3-service topology

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): format validation PASS (all 35 tasks follow checkbox/ID/label/path format)
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
