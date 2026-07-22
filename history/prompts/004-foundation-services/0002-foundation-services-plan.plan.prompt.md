---
id: 0002
title: foundation-services-plan
stage: plan
date: 2026-07-21
surface: agent
model: deepseek-v4-flash-free
feature: 004-foundation-services
branch: 004-foundation-services
user: saifullah
command: /sp.plan
labels: [plan, architecture, clerk-auth, foundation-services, course-core, ingestion-pipeline]
links:
  spec: specs/004-foundation-services/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/004-foundation-services/plan.md
  - specs/004-foundation-services/research.md
  - specs/004-foundation-services/data-model.md
  - specs/004-foundation-services/quickstart.md
  - specs/004-foundation-services/contracts/course-core-api.md
  - specs/004-foundation-services/contracts/ingestion-pipeline-api.md
  - AGENTS.md
tests:
  - (planned, not yet created)
---

## Prompt

run the /sp.plan comamnd for this feature

remember to add that we will use clerk python backend sdk for api auth https://clerk.com/changelog/2024-10-08-python-backend-sdk-beta

## Response snapshot

Executed `/sp.plan` for feature `004-foundation-services` (Foundation Services). The plan covers Course Core and Ingestion Pipeline FastAPI services with:
- Clerk Python backend SDK (`clerk-backend-api`) for JWT authentication + webhook sync
- Auth via FastAPI dependency injection (`require_auth` dependency using `authenticate_request()`)
- Course CRUD, dashboard analytics, file upload to S3, async background ingestion
- Per-course serialization via advisory locks
- Zero-cost infra constraint preserved (Clerk free tier: 10k MAU)

Created artifacts:
1. `plan.md` — Technical Context, Constitution Check, project structure, complexity tracking
2. `research.md` — Clerk SDK integration pattern resolved (official SDK, FastAPI DI pattern, test strategy)
3. `data-model.md` — Entity changes (clerk_id, is_active, preferences on User; archived_at, paper_count on Course)
4. `contracts/course-core-api.md` — 12 endpoints (users, courses, dashboard, webhooks)
5. `contracts/ingestion-pipeline-api.md` — 2 endpoints (upload, status poll)
6. `quickstart.md` — setup guide with Clerk config, test commands, full API flow

Agent context updated via `update-agent-context.sh`.

## Outcome

- ✅ Impact: Architecture plan complete for 004-foundation-services. Clerk auth integrated as core dependency. Ready for task breakdown.
- 🧪 Tests: Not yet created — test strategy documented in research.md (httpx AsyncClient, dependency_overrides for auth)
- 📁 Files: 6 artifacts created under specs/004-foundation-services/
- 🔁 Next prompts: /sp.tasks to break into actionable implementation tasks
- 🧠 Reflection: Clerk Python SDK (`clerk-backend-api`) is the recommended approach per Clerk's official docs (2026). The `authenticate_request()` function accepts FastAPI `Request` directly. Webhook verification requires separate `svix` package.

## Evaluation notes (flywheel)

- Failure modes observed: None during planning
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Run /sp.tasks on the plan
