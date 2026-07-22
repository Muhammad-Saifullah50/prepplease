---
id: 0001
title: foundation-services-spec
stage: spec
date: 2026-07-21
surface: agent
model: deepseek-v4-flash-free
feature: 004-foundation-services
branch: 004-foundation-services
user: saifullah
command: /sp.specify Phase 3a
labels: ["phase3", "microservices", "course-core", "ingestion-pipeline", "spec"]
links:
  spec: specs/004-foundation-services/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/004-foundation-services/spec.md
  - specs/004-foundation-services/checklists/requirements.md
tests:
  - null
---

## Prompt

so we have to now specify the phase3 from features.md. go through it and brainstrom with me . then we wil eorte the soec

[Full brainstorming session followed. Key decisions:
- Split Phase 3 into sub-phases: 3a (Course Core + Ingestion Pipeline) and 3b (Exam Simulation)
- Keep 3 separate services (course-core:8001, ingestion-pipeline:8002, exam-sim:8003)
- Course Core: full dashboard + analytics
- Ingestion: async with polling using BackgroundTasks
- Auth: Clerk with webhooks + JWT validation
- Exam auto-save: Redis buffer
- Focus violation: auto-lockout on threshold
- Server-authoritative timer (REST polling, not WebSocket)
- Clerk webhooks for user sync + lazy creation on first API call]

User typed: "ok ue the /sp.specify command to spes 3a"

Then: "yes write the spec now. add to the spec the tou will use cleark skills ti setup auth ans webhooks etc. i have installed clerk skills"

## Response snapshot

Followed /sp.specify command flow:
1. Generated short name "foundation-services" for branch 004-foundation-services
2. Created branch and spec file via create-new-feature.sh script
3. Loaded spec-template.md and wrote the full specification with:
   - 4 User Stories (P1: upload/ingestion + dashboard; P2: course CRUD + Clerk auth)
   - 23 Functional Requirements covering auth, courses, upload, dashboard, security, performance
   - 10 Success Criteria (measurable, technology-agnostic)
   - 12 Edge Cases
   - Key Entities and Out of Scope section
4. Created quality checklist at specs/004-foundation-services/checklists/requirements.md
5. All checklist items pass — no [NEEDS CLARIFICATION] markers remain
6. Created PHR at history/prompts/004-foundation-services/0001-foundation-services-spec.spec.prompt.md

## Outcome

- ✅ Impact: Phase 3a spec written — defines Course Core Service and Ingestion Pipeline Service with 4 user stories, 23 FRs, 10 SCs
- 🧪 Tests: No tests in this spec phase; testing defined in acceptance scenarios
- 📁 Files: specs/004-foundation-services/spec.md, specs/004-foundation-services/checklists/requirements.md
- 🔁 Next prompts: /sp.plan for 004-foundation-services (architecture plan), then /sp.tasks
- 🧠 Reflection: Clean scope boundary with Phase 3b (exam simulation deferred). Clerk auth approach well-defined with webhooks + JWT validation + lazy creation. All [NEEDS CLARIFICATION] resolved during brainstorming before writing.

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): N/A — spec phase, no graders
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Run /sp.plan to produce architecture plan
