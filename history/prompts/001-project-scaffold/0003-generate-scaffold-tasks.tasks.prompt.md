---
id: 0003
title: generate-scaffold-tasks
stage: tasks
date: 2026-07-20
surface: claude-code (vscode)
model: claude-opus-4-8
feature: 001-project-scaffold
branch: 001-project-scaffold
user: user
command: /sp.tasks
labels: [tasks, scaffold, uv-workspace, fastapi, docker, ci]
links:
  spec: specs/001-project-scaffold/spec.md
  ticket: n/a
  adr: n/a
  pr: n/a
files:
  - specs/001-project-scaffold/tasks.md
tests:
  - n/a (task generation only; test tasks T025–T029 defined for implementation)
---

## Prompt

/sp.tasks (no additional user input)

Generate an actionable, dependency-ordered tasks.md for feature 001-project-scaffold based on available design artifacts: plan.md, spec.md, research.md, data-model.md, contracts/health-api.yaml, quickstart.md. Organize tasks by user story (P1 local stack, P2 tests/linting, P3 CI), strict checklist format `- [ ] T### [P?] [US?] description with file path`, tests included per FR-009a.

## Response snapshot

Generated specs/001-project-scaffold/tasks.md with 37 tasks across 6 phases:
- Phase 1 Setup (T001–T004): gitignore, .python-version, uv workspace root, empty agent packages
- Phase 2 Foundational (T005–T010): exambrain-shared package (config, logging, iam/llm/s3 deferred-error stubs, lazy db), uv.lock
- Phase 3 US1/P1 MVP (T011–T024): 3 service packages with /health + /metrics, 3 alembic scaffolds, .env.examples, Dockerfile pairs, postgres init script, OTel config, docker-compose.yml, end-to-end validation
- Phase 4 US2/P2 (T025–T032): 5 test files (health×3, config, stubs) per FR-009a, pre-commit config, coverage config, local validation
- Phase 5 US3/P3 (T033–T034): GitHub Actions ci.yml (lint + test jobs), push validation
- Phase 6 Polish (T035–T037): quickstart verification, contract cross-check, clean-checkout sweep
21 tasks marked [P]; dependency graph and per-story parallel examples included; MVP = US1.

## Outcome

- ✅ Impact: tasks.md ready for /sp.implement; every task has an exact file path and FR traceability
- 🧪 Tests: test tasks placed in US2 phase (they ARE the FR-009a deliverable, not TDD gates for the scaffold)
- 📁 Files: specs/001-project-scaffold/tasks.md created
- 🔁 Next prompts: /sp.analyze for cross-artifact consistency, then /sp.implement
- 🧠 Reflection: US2 tests depend on US1 service packages (T011–T013) but not Docker tasks — noted explicitly so the stories stay independently testable

## Evaluation notes (flywheel)

- Failure modes observed: create-phr.sh requires the full numbered feature slug (001-project-scaffold), not the short name
- Graders run and results (PASS/FAIL): format check PASS — all 37 tasks follow checkbox + ID + [P?] + [Story?] + path format
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
