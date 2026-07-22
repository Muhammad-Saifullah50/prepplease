---
id: 0003
title: foundation-services-tasks
stage: tasks
date: 2026-07-21
surface: agent
model: deepseek-v4-flash-free
feature: 004-foundation-services
branch: 004-foundation-services
user: saifullah
command: /sp.tasks for this feature
labels: ["tasks", "foundation-services", "course-core", "ingestion-pipeline", "clerk-auth"]
links:
  spec: specs/004-foundation-services/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/004-foundation-services/tasks.md
tests:
  - (test tasks defined inline in tasks.md; no test files created in this PHR)
---

## Prompt

run /sp.tasks for this fgeature

## Response snapshot

Generated specs/004-foundation-services/tasks.md with 40 tasks across 7 phases: Setup (4), Foundational (6), US1 Upload P1 (6), US2 Dashboard P1 (6), US3 Course CRUD P2 (6), US4 Auth/Profile P2 (5), Polish (7). MVP scope = US1+US2. Auth infrastructure placed in Phase 2 as blocking prerequisite (require_auth + lazy user creation via clerk-backend-api).

## Outcome

- ✅ Impact: Generated actionable, dependency-ordered tasks.md for the 004-foundation-services feature, replacing template placeholders with real tasks derived from spec, plan, data-model, contracts, and research documents.
- 🧪 Tests: Test tasks included in US phases (T011, T012, T017, T023, T029, T030) — tests to be written before implementation within each story.
- 📁 Files: specs/004-foundation-services/tasks.md (new file, 350+ lines)
- 🔁 Next prompts: /sp.implement — to begin executing tasks in phase order
- 🧠 Reflection: Auth was the trickiest structural decision: placed Clerk require_auth + lazy user creation in Phase 2 (foundational) since it blocks all stories, while the webhook handler and profile endpoints (US4) are P2. This avoids the circular dependency where auth is P2 but needed by P1 stories.

## Evaluation notes (flywheel)

- Failure modes observed: none — all required design documents were available and complete
- Graders run and results (PASS/FAIL): null
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null — proceed to /sp.implement
