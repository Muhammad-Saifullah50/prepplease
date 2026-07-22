---
id: 0002
title: Clarify exam simulation spec ambiguities
stage: spec
date: 2026-07-22
surface: cli
model: claude-sonnet-5
feature: 005-exam-simulation
branch: 005-exam-simulation
user: Muhammad
command: /sp.clarify
labels: [clarify, spec]
links:
  spec: specs/005-exam-simulation/spec.md
  ticket:
  adr:
  pr:
files:
  - specs/005-exam-simulation/spec.md
tests:
  - none
---

## Prompt

/sp.clarify (no additional arguments)

## Response snapshot

Ran the clarification workflow against specs/005-exam-simulation/spec.md. Scanned the spec against the ambiguity taxonomy and identified 5 high-impact underspecified points, all in Functional Scope & Non-Functional Quality Attributes: the default focus-violation lockout limit, the default exam duration fallback, the answer-autosave trigger cadence, whether flickering focus-loss events should be coalesced, and how remaining-time/warning updates reach the client. Asked all 5 via AskUserQuestion with a recommended option each; user accepted the recommendation on 4 of 5 and picked "every reported event counts separately" (not the recommended debounce) for focus-violation coalescing.

Answers:
- Default focus-violation limit: 3 violations
- Default exam duration fallback: 120 minutes
- Answer-save trigger: debounced on change
- Focus-violation counting: every reported event counts separately (no coalescing)
- Update delivery: client polling (REST)

Integrated a `## Clarifications` / `### Session 2026-07-22` section with all 5 Q&A bullets, then applied each answer inline: FR-004 and FR-014 now specify client polling as the delivery mechanism; FR-005 now specifies debounced-on-change saving; FR-014 now states the default limit (3) and that events are not coalesced; FR-021 now states the 120-minute default. No contradictory prior text remained to remove — the original FRs used deliberately vague language ("configurable limit", "reasonable default") that the clarifications now pin down without altering scope.

## Outcome

- ✅ Impact: 5 ambiguities resolved and written into spec.md (Clarifications section + inline FR updates to FR-004, FR-005, FR-014, FR-021)
- 🧪 Tests: none (spec-only change, no code)
- 📁 Files: specs/005-exam-simulation/spec.md
- 🔁 Next prompts: /sp.plan (all critical ambiguities for planning are resolved)
- 🧠 Reflection: Update-delivery mechanism (polling vs push) is a plan-level architectural question but was included here because it materially changes FR-004/FR-014 wording; worth double-checking during /sp.plan that REST polling is sufficient for the "prompt" countdown/warning UX implied by SC-001/SC-005.

## Evaluation notes (flywheel)

- Failure modes observed: none — all 5 questions were answerable via the multiple-choice format, no disambiguation retries needed.
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
