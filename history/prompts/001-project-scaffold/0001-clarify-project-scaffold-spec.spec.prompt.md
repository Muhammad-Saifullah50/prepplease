---
id: 0001
title: clarify-project-scaffold-spec
stage: spec
date: 2026-07-20
surface: vscode-extension
model: claude-opus-4-8
feature: 001-project-scaffold
branch: 001-project-scaffold
user: user
command: /sp.clarify
labels: [clarification, spec]
links:
  spec: specs/001-project-scaffold/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-project-scaffold/spec.md
tests:
  - none
---

## Prompt

/sp.clarify (no additional user input)

Detect and reduce ambiguity or missing decision points in the active feature specification (001-project-scaffold) and record the clarifications directly in the spec file. Ask up to 5 targeted questions, one at a time, integrating each answer into the spec.

## Response snapshot

Ran ambiguity/coverage scan on specs/001-project-scaffold/spec.md. Asked 4 clarification questions, all answered and integrated:

1. `agents/` directory handling → Scaffold empty package directories (`__init__.py` only, no logic). Added FR-018; updated Key Entities.
2. Database topology → One PostgreSQL instance, separate DB per service (`course_core`, `ingestion`, `exam_sim`). Updated FR-015; added FR-015a.
3. Branch protection / merge blocking → Out of scope; CI reports status only. Updated US3 acceptance scenario 3.
4. 80% coverage scope → All `backend/` code; scaffold ships with tests to hit 80% from day one. Updated FR-009; added FR-009a.

Added `### Session 2026-07-20` under Clarifications with 4 Q/A bullets.

## Outcome

- ✅ Impact: 4 material ambiguities resolved and encoded in spec; ready for /sp.plan
- 🧪 Tests: none (spec-phase)
- 📁 Files: specs/001-project-scaffold/spec.md
- 🔁 Next prompts: /sp.plan
- 🧠 Reflection: Prior session (2026-07-19) had already resolved stub failure and log-level ambiguities; this pass closed scope (agents), data model (DB-per-service), CI policy (no branch protection), and coverage-scope gaps.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
