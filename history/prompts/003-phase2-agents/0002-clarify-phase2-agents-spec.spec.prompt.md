---
id: 0002
title: clarify-phase2-agents-spec
stage: spec
date: 2026-07-20
surface: claude-code (vscode)
model: claude-opus-4-8
feature: 003-phase2-agents
branch: 003-phase2-agents
user: Muhammad
command: /sp.clarify
labels: [clarification, spec, phase2-agents]
links:
  spec: specs/003-phase2-agents/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/003-phase2-agents/spec.md
tests:
  - none (spec-stage; no code changes)
---

## Prompt

/sp.clarify (no additional user input)

Goal: Detect and reduce ambiguity or missing decision points in the active feature specification (specs/003-phase2-agents/spec.md) and record the clarifications directly in the spec file. Structured taxonomy scan (functional scope, domain/data model, UX flow, non-functional attributes, integrations, edge cases, constraints, terminology, completion signals), then up to 5 interactive multiple-choice questions with recommendations, integrating each accepted answer into the spec incrementally.

## Response snapshot

Ran structured ambiguity scan on the Phase 2 Agents spec; most categories Clear. Asked 4 questions, all answered (3 accepted recommendations, 1 chose recommended option B):

1. Low-confidence ("needs review") papers in blueprint extraction → A: excluded entirely until flag cleared; later re-run incorporates them. (FR-009, Edge Cases updated)
2. Concurrent ingestion / blueprint version conflicts → A: serialized per course; later run supersedes with full paper set. (FR-010 updated)
3. "Decisive" vs "ambiguous" instructor similarity → A: three fixed bands, configurable defaults: ≥0.90 auto-match, 0.70–0.90 needs review, <0.70 new professor. (FR-007 updated)
4. Usability of "needs review" generated exams → B: fully usable — can be taken and graded; flag persists for later review tooling. (FR-015 updated)

Added `## Clarifications` → `### Session 2026-07-20` with all four Q/A bullets. Sections touched: Clarifications, Edge Cases, FR-007, FR-009, FR-010, FR-015.

## Outcome

- ✅ Impact: 4 high-impact ambiguities resolved and encoded into the spec; alignment thresholds, blueprint concurrency, review-flag semantics now deterministic and testable.
- 🧪 Tests: N/A (spec stage)
- 📁 Files: specs/003-phase2-agents/spec.md (updated)
- 🔁 Next prompts: /sp.plan
- 🧠 Reflection: Spec was already strong; remaining gaps were policy decisions (thresholds, concurrency, flag semantics) rather than missing scope.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
