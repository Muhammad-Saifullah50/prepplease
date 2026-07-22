---
id: 0004
title: exam-simulation-tasks-generation
stage: tasks
date: 2026-07-22
surface: agent
model: deepseek-v4-flash-free
feature: 005-exam-simulation
branch: 005-exam-simulation
user: saifullah
command: /sp.tasks
labels: ["tasks", "exam-simulation", "feature-005"]
links:
  spec: specs/005-exam-simulation/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/005-exam-simulation/tasks.md
tests:
  - N/A (task generation, no tests run)
---

## Prompt

run /sp.tasks for this

## Response snapshot

Generated `specs/005-exam-simulation/tasks.md` with 39 tasks across 6 phases:
- Phase 1 Setup (3 tasks): pyproject.toml deps, config.py settings, .env.example
- Phase 2 Foundational (4 tasks): schema migrations, ORM updates, Redis helpers
- Phase 3 US1 — Timed mock exam P1 (11 tasks): TDD tests + attempt lifecycle service/routers
- Phase 4 US2 — Focus-violation lockout P1 (7 tasks): TDD tests + focus tracker service/routers
- Phase 5 US3 — Time-limit extraction P2 (9 tasks): data model + agent prompt changes
- Phase 6 Polish (5 tasks): docker-compose, conftest, edge cases, linting

## Outcome

- ✅ Impact: Complete executable task list for 005-exam-simulation feature, organized by user story with dependencies, parallel opportunities, and TDD test-first approach
- 🧪 Tests: 11 test tasks (5 for US1, 3 for US2, 3 for US3) following TDD red-green-refactor per plan.md
- 📁 Files: specs/005-exam-simulation/tasks.md
- 🔁 Next prompts: Proceed to /sp.implement for Phase 1 (Setup)
- 🧠 Reflection: All 39 tasks validated against checklist format. TDD approach included per constitution mandate. US3 (time-limit extraction) correctly scoped as P2 with cross-service agent prompt changes.

## Evaluation notes (flywheel)

- Failure modes observed: N/A
- Graders run and results (PASS/FAIL): Format validation PASS — all 39 tasks follow `- [ ] Txxx [P?] [Story?] Description with file path`
- Prompt variant (if applicable): standard /sp.tasks
- Next experiment (smallest change to try): Execute Phase 1 Setup tasks to validate dependency wiring
