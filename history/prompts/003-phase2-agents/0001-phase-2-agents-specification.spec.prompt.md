---
id: 0001
title: Phase 2 agents specification
stage: spec
date: 2026-07-20
surface: agent
model: claude-opus-4-8
feature: 003-phase2-agents
branch: 003-phase2-agents
user: saifullah
command: /sp.specify
labels: ["agents", "openai-agents-sdk", "spec", "phase-2"]
links:
  spec: specs/003-phase2-agents/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/003-phase2-agents/spec.md
 - specs/003-phase2-agents/checklists/requirements.md
tests:
 - none (spec stage)
---

## Prompt

Phase 2 Agents — five OpenAI Agents SDK agents (parsing, instructor alignment, blueprint extraction, exam generator, TA evaluation) packaged as backend/agents library with code-driven typed pipelines, read-only tools, targeted blueprint→alignment handoff, per-agent model overrides, needs_review flagging, new instructors and generated_exams tables, chunking+embedding owned here

(Preceded by a brainstorming session: user asked to spec Phase 2 agents built on OpenAI Agents SDK, with alignment, blueprint extractor, and generator collaborating via handoffs; verbatim: "ok so now we have to discuss phase 2 agents. The agent will be built using openai agents sdk. read its docs whenever you need. doint manke any assumptoons about it and not write legacy coide . thw alignment agent, blueprint extractir nd the generatir agent will collaboirate with each other so understand their handoffs and toole required. help me secify this featyure. ask any questions you want. after we have discsuused we will then wroite its soec")

## Response snapshot

Created feature branch `003-phase2-agents` and wrote spec.md covering all five Phase 2 agents (features 8–12). Key decisions captured from brainstorming Q&A: code-driven pipeline orchestration (not LLM-driven); SDK LitellmModel for Bedrock; agents get read-only tools while pipeline code persists; everything is an SDK Agent with deterministic machinery as tools; instructor identity = unique normalized names with fuzzy matching (no alias table); delivery as installable library with typed pipeline entry points; agentic RAG tool for generation grounding; generator emits rubric; new instructors + generated_exams tables; chunking+embedding owned by Phase 2; needs_review flagging instead of blocking; per-agent model env overrides; fake-model CI testing + opt-in live tests; one real SDK handoff (blueprint→alignment on instructor sightings). 4 user stories, 24 FRs, 8 SCs. Quality checklist passes all items.

## Outcome

- ✅ Impact: Spec + requirements checklist created on new branch 003-phase2-agents
- 🧪 Tests: none (spec stage)
- 📁 Files: specs/003-phase2-agents/spec.md, specs/003-phase2-agents/checklists/requirements.md
- 🔁 Next prompts: /sp.clarify (optional) or /sp.plan
- 🧠 Reflection: Brainstorming answers eliminated all NEEDS CLARIFICATION markers before spec writing

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): requirements checklist PASS (all items)
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
