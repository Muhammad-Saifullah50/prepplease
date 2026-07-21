---
id: 0004
title: phase2-agents-task-generation
stage: tasks
date: 2026-07-20
surface: vscode-extension (Claude Code)
model: claude-opus-4-8[1m]
feature: 003-phase2-agents
branch: 003-phase2-agents
user: Muhammad
command: /sp.tasks
labels: [tasks, agents, sdd]
links:
  spec: specs/003-phase2-agents/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/003-phase2-agents/tasks.md
tests:
  - none (task-generation artifact; test tasks defined within tasks.md)
---

## Prompt

/sp.tasks (no additional user input)

Generate an actionable, dependency-ordered tasks.md for feature 003-phase2-agents based on plan.md, spec.md, research.md, data-model.md, contracts/ (agent-outputs, pipelines, tools), and quickstart.md. Tasks must be organized by user story with strict checklist format (`- [ ] T00X [P?] [Story?] Description with file path`), phases for Setup / Foundational / per-story / Polish, dependency graph, parallel examples, and MVP strategy.

## Response snapshot

Generated specs/003-phase2-agents/tasks.md with 57 tasks across 7 phases:

- Phase 1 Setup (T001–T004): uv workspace member `exambrain-agents`, root tooling wiring, tesseract in Docker, shared Settings extensions.
- Phase 2 Foundational (T005–T012): tracing-disabled package init, error hierarchy, `model_for` config resolver, FakeModel, `run_agent` runner with error translation + retry helper, shared alignment schema, test scaffolding + runner tests.
- Phase 3 US1 ingest/blueprint, P1 MVP (T013–T028, 16 tasks): TDD tests first (extraction, chunking, parsing agent, blueprint agent critical path, full ingest pipeline), then ingestion migration, parsing/blueprint schemas, extraction tools, chunker, parsing + blueprint agents, ingestion/course-core repositories with advisory lock, `ingest_course_file` pipeline.
- Phase 4 US3 exam generation, P1 (T029–T037, 9 tasks): generated_exams migration, generation schemas, retrieval tool, generator agent, exam-sim repo, `generate_exam` pipeline with validation + corrective retry.
- Phase 5 US2 instructor alignment, P2 (T038–T046, 9 tasks): course-core migration, matching tools, alignment agent, banding re-enforcement, integration into ingest pipeline, alignment-as-tool attachment to blueprint agent (FR-008).
- Phase 6 US4 evaluation, P2 (T047–T052, 6 tasks): evaluation agent (rubric-strict, prompt-injection-safe), results upsert repo, `evaluate_submission` pipeline.
- Phase 7 Polish (T053–T057): live_llm smoke tests, public API/quickstart verification, coverage + quality gates, FR-022 logging audit, migration walkthrough.

Ordering note: US3 sequenced before US2 (both P1 headline capability first); US2 integrates into US1 files afterward. Tests included per Constitution VI TDD mandate. Parallel opportunities and MVP-first strategy documented.

## Outcome

- ✅ Impact: tasks.md created — feature ready for /sp.implement
- 🧪 Tests: TDD test tasks embedded per story (FakeModel offline suite, migration markers, live_llm opt-in)
- 📁 Files: specs/003-phase2-agents/tasks.md (new)
- 🔁 Next prompts: /sp.analyze for cross-artifact consistency; /sp.implement to execute
- 🧠 Reflection: story-phase mapping required re-sequencing (P1 pair first) and splitting FR-008 handoff out of US1 into US2 to keep stories independently testable

## Evaluation notes (flywheel)

- Failure modes observed: none — all design artifacts present and consistent
- Graders run and results (PASS/FAIL): checklist-format self-check PASS (all 57 tasks have checkbox, ID, labels where required, file paths)
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): consider auto-validating task format with a lint script in check-prerequisites
