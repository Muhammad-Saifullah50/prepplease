---
id: 0001
title: Specify exam simulation service
stage: spec
date: 2026-07-22
surface: cli
model: claude-opus-4-8
feature: 005-exam-simulation
branch: 005-exam-simulation
user: Muhammad
command: /sp.specify
labels: [spec, exam-simulation, feature-15]
links:
  spec: specs/005-exam-simulation/spec.md
  ticket:
  adr:
  pr:
files:
  - specs/005-exam-simulation/spec.md
  - specs/005-exam-simulation/checklists/requirements.md
  - docs/superpowers/specs/2026-07-22-exam-simulation-service-design.md
tests:
  - (none — spec stage, no code)
---

## Prompt

Brainstorm feature 15 from features.md (Exam Simulation Service) with the user, then
specify it. Feature 15: "Real-time session mgmt, countdown timer, auto-save buffer,
focus-violation lockout." Brainstorming session explored the existing codebase
(course-core / ingestion-pipeline service patterns, exam-simulation scaffold,
ExamSession/GeneratedExamRow models, SessionStore, evaluate_submission pipeline) and
worked through six sequential decisions with the user: transport (REST + heartbeat vs.
WebSocket), live-answer durability (Redis buffer vs. Postgres), focus-violation policy
(threshold → lockout + auto-submit), timer-expiry behavior (auto-submit + grade) and
duration source (extracted from past papers, not guessed from marks), grading trigger
(background task, result via course-core), and session concurrency (one active session
per user, `generated_exam_id` as start key). The user also asked to fold in a companion
change: extracting real "Time allowed" durations from past papers and threading them
through the parsing → blueprint → generator agent chain, with blueprint-level merging
across source papers resolved as MAX non-null duration. All decisions were written to
a design doc, then `/sp.specify` was invoked to produce the formal spec on a new
`005-exam-simulation` branch.

## Response snapshot

Created design doc at
`docs/superpowers/specs/2026-07-22-exam-simulation-service-design.md` capturing all
brainstormed decisions (transport, durability, focus lockout, expiry, duration
extraction + merge rule, grading trigger, concurrency). Ran
`create-new-feature.sh --number 5 --short-name exam-simulation`, creating branch
`005-exam-simulation` and `specs/005-exam-simulation/spec.md`. Wrote the spec with 3
prioritized user stories (P1: timed attempt lifecycle, P1: focus-violation lockout, P2:
authentic duration extraction), 8 edge cases, 21 functional requirements grouped by
lifecycle/integrity/access-control/duration-extraction, 4 key entities (Exam Attempt,
Generated Mock Exam, Course Blueprint, Past Paper), and 7 measurable success criteria —
all technology-agnostic (no mention of REST/Redis/FastAPI, which remain in the design
doc for the planning stage). Validated the spec against the quality checklist
(`specs/005-exam-simulation/checklists/requirements.md`); all items passed on the first
pass since every ambiguous point had already been resolved during brainstorming rather
than left as a `[NEEDS CLARIFICATION]` marker.

## Outcome

- ✅ Impact: Feature 15 (Exam Simulation Service) is fully specified and ready for
  `/sp.plan`; the spec also scopes the duration-extraction thread through the Phase-2
  parsing/blueprint/generator agents as part of the same feature.
- 🧪 Tests: None (spec stage — no code changes).
- 📁 Files: `specs/005-exam-simulation/spec.md`,
  `specs/005-exam-simulation/checklists/requirements.md`,
  `docs/superpowers/specs/2026-07-22-exam-simulation-service-design.md`.
- 🔁 Next prompts: `/sp.plan` to produce the implementation plan for
  `005-exam-simulation`.
- 🧠 Reflection: Resolving every ambiguous decision during brainstorming (before
  invoking `/sp.specify`) meant the generated spec needed zero `[NEEDS CLARIFICATION]`
  markers and passed the quality checklist on the first pass — front-loading the
  judgment calls into a conversational design phase kept the formal spec purely
  declarative.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): spec quality checklist — PASS (all items).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
