---
id: 0003
title: phase2-agents-implementation-plan
stage: plan
date: 2026-07-20
surface: vscode-extension (Claude Code)
model: claude-opus-4-8[1m]
feature: 003-phase2-agents
branch: 003-phase2-agents
user: Muhammad
command: /sp.plan
labels: [plan, agents, openai-agents-sdk, pipelines]
links:
  spec: specs/003-phase2-agents/spec.md
  ticket: n/a
  adr: proposed (3 candidates in plan.md)
  pr: n/a
files:
  - specs/003-phase2-agents/plan.md
  - specs/003-phase2-agents/research.md
  - specs/003-phase2-agents/data-model.md
  - specs/003-phase2-agents/contracts/pipelines.md
  - specs/003-phase2-agents/contracts/agent-outputs.md
  - specs/003-phase2-agents/contracts/tools.md
  - specs/003-phase2-agents/quickstart.md
  - AGENTS.md
tests:
  - none (planning artifacts only)
---

## Prompt

/sp.plan (no additional user input) — Execute the implementation planning workflow for feature 003-phase2-agents: fill plan.md Technical Context and Constitution Check, generate research.md (Phase 0), data-model.md / contracts/ / quickstart.md (Phase 1), update agent context, and stop before task generation.

## Response snapshot

Planned the five-agent library (`exambrain-agents`) as a new uv workspace member under backend/agents/ with src layout. Key decisions (research.md R1–R12): OpenAI Agents SDK with LitellmModel preserving the LiteLLM→Bedrock mandate; FR-008 handoff implemented as alignment-agent-as-tool inside the blueprint agent; pypdfium2 + pytesseract + python-pptx for deterministic extraction (zero-cost, local OCR); rapidfuzz similarity with code-enforced 0.90/0.70 banding; chunking deterministic + embeddings via existing LLMClient (1024-dim); per-course blueprint serialization via pg_advisory_xact_lock; three additive Alembic migrations (instructors + instructor_resolutions in course-core, parsing_confidence/needs_review on past_papers, generated_exams in exam-sim); FakeModel at the SDK Model seam for offline tests plus live_llm opt-in marker; per-agent model env overrides falling back to LLM_MODEL. Constitution check passes with one justified deviation (code-driven pipelines instead of Redis pub/sub agent communication — Complexity Tracking + ADR candidate). Three contracts written: pipeline entry points, agent output schemas, read-only tools.

## Outcome

- ✅ Impact: Complete Phase 0+1 planning artifacts for 003-phase2-agents; ready for /sp.tasks
- 🧪 Tests: none (planning only); test strategy defined (FakeModel, live_llm/migration markers, ≥80% coverage)
- 📁 Files: plan.md, research.md, data-model.md, contracts/{pipelines,agent-outputs,tools}.md, quickstart.md, AGENTS.md updated
- 🔁 Next prompts: /sp.tasks to generate dependency-ordered tasks; ADR proposals for the 3 flagged candidates
- 🧠 Reflection: Codebase exploration up front (002 foundation adapters inventory) let every decision reuse existing machinery instead of inventing new infra

## Evaluation notes (flywheel)

- Failure modes observed: none — setup script, exploration, and artifact generation all succeeded first pass
- Graders run and results (PASS/FAIL): Constitution gate PASS (1 justified deviation documented)
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
