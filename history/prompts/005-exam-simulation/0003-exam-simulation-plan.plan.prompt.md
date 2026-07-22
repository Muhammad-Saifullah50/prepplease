---
id: 0003
title: exam-simulation-plan
stage: plan
date: 2026-07-22
surface: agent
model: deepseek-v4-flash-free
feature: 005-exam-simulation
branch: 005-exam-simulation
user: saifullah
command: /sp.plan
labels: ["plan", "exam-simulation", "attempt-lifecycle", "time-limit-extraction"]
links:
  spec: specs/005-exam-simulation/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/005-exam-simulation/plan.md
  - specs/005-exam-simulation/research.md
  - specs/005-exam-simulation/data-model.md
  - specs/005-exam-simulation/quickstart.md
  - specs/005-exam-simulation/contracts/attempts-api.md
  - specs/005-exam-simulation/contracts/focus-api.md
  - AGENTS.md
tests:
  - null
---

## Prompt

use rthe /sp.plan command to plan this feature

## Response snapshot

Executed /sp.plan for feature 005-exam-simulation. Created plan.md, research.md (7 decisions including deadline enforcement, finish idempotency, Redis caching, and LLM-based time-limit extraction), data-model.md (ExamAttempt entity with status transitions, modified ExamBlueprint/PastPaper/GeneratedExamRow for time_limit), quickstart.md, and two API contract specs for attempts and focus-violation endpoints. Updated AGENTS.md via update-agent-context.sh.

## Outcome

- ✅ Impact: Design for exam-simulation service — attempt lifecycle, focus-violation lockout, time-limit extraction across parsing→blueprint→generation pipeline
- 🧪 Tests: Not yet created (deferred to /sp.tasks)
- 📁 Files: plan.md, research.md, data-model.md, quickstart.md, contracts/attempts-api.md, contracts/focus-api.md, AGENTS.md
- 🔁 Next prompts: /sp.tasks to break plan into implementation tasks
- 🧠 Reflection: Duration extraction touches 3 agents (parsing, blueprint, generator) but changes are additive fields + prompts only — no coupling introduced. Redis cache layer keeps polling fast without sacrificing durability.

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
