---
id: 0002
title: clarify-foundation-adapters-spec
stage: spec
date: 2026-07-20
surface: claude-code (vscode)
model: claude-opus-4-8
feature: 002-foundation-adapters
branch: 002-foundation-adapters
user: Muhammad
command: /sp.clarify
labels: [clarification, spec, foundation-adapters]
links:
  spec: specs/002-foundation-adapters/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/002-foundation-adapters/spec.md
tests:
  - none (spec-stage; no code changes)
---

## Prompt

/sp.clarify (no additional user input)

Run the clarification workflow on the active feature spec: scan for ambiguity across the coverage taxonomy (scope, data model, UX, non-functional, integrations, edge cases, constraints, terminology, completion signals), ask up to 5 targeted questions one at a time with recommended options, and integrate each accepted answer directly into the spec.

## Response snapshot

Spec was already well-covered (3 prior clarifications from an earlier session same day). Scan surfaced 2 material gaps, both schema-affecting; both questions asked, both answered with the recommended option A:

1. Q: Is LLM token usage persisted to the database or tracked in-memory only?
   A: In-memory only — cumulative counters per model for process lifetime plus structured log lines per call; no usage table in this feature's migrations. (Updated FR-009 and the Usage Record key entity.)
2. Q: What are the past paper processing status states?
   A: `pending → processing → completed / failed` — four states, linear; failed terminal until reprocessing re-triggered. (Updated FR-005 and the Past Paper key entity.)

Both recorded under `## Clarifications / ### Session 2026-07-20` and integrated into the affected sections with no contradictory text left behind.

## Outcome

- ✅ Impact: Resolved the two remaining schema-affecting ambiguities (usage persistence, past-paper lifecycle); spec ready for /sp.plan.
- 🧪 Tests: N/A — spec-only change.
- 📁 Files: specs/002-foundation-adapters/spec.md (Clarifications, FR-005, FR-009, Key Entities: Past Paper, Usage Record).
- 🔁 Next prompts: /sp.plan
- 🧠 Reflection: Coverage taxonomy scan on an already-clarified spec correctly narrowed to only material, migration-impacting questions instead of padding to the 5-question quota.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
