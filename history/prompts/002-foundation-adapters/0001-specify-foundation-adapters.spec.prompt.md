---
id: 0001
title: specify-foundation-adapters
stage: spec
date: 2026-07-20
surface: claude-code (vscode)
model: claude-opus-4-8
feature: 002-foundation-adapters
branch: 002-foundation-adapters
user: Muhammad
command: /sp.specify
labels: [spec, foundation, llm, schema, redis, s3, iam]
links:
  spec: specs/002-foundation-adapters/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/002-foundation-adapters/spec.md
  - specs/002-foundation-adapters/checklists/requirements.md
tests:
  - "Spec quality checklist: 16/16 pass"
---

## Prompt

/sp.specify Foundation adapters: implement features 2-6 from features.md as one feature — real LiteLLM Bedrock bridge (async, retries, token tracking), PostgreSQL+pgvector schema migrations (users, courses, past papers, exam blueprints, sessions, results), async Redis session store (caching, rate-limiting, real-time state), async S3 file adapter (upload/download/list via aioboto3), IAM credential manager (encrypted local cred store, rotation handling, least-privilege validation) — replacing the deferred-error stubs in exambrain-shared

## Response snapshot

Created branch 002-foundation-adapters and spec.md covering features 2–6 as five prioritized user stories: P1 domain schema + migrations, P2 LLM gateway (retries, token tracking), P3 Redis session/rate-limit store, P4 S3 file adapter (streaming), P5 credential safety (validation, rotation, no-secrets-in-logs). 22 FRs, 8 entities, 8 measurable SCs. Asked 3 clarifying questions; user answered: Titan V2 embeddings (1024-d), entity ownership by service domain (course_core/ingestion/exam_sim), Bedrock available today. Answers encoded in Clarifications section and FR-002/FR-004/FR-007. Quality checklist 16/16 pass.

## Outcome

- ✅ Impact: Combined foundation-adapters spec ready for planning; all clarifications resolved inline.
- 🧪 Tests: Spec quality checklist all pass; no NEEDS CLARIFICATION markers remain.
- 📁 Files: spec.md + checklists/requirements.md under specs/002-foundation-adapters/.
- 🔁 Next prompts: /sp.plan to produce research/data-model/contracts; optionally /sp.clarify for deeper probing first.
- 🧠 Reflection: Bundling 5 foundation features into one spec works because they share the stub-replacement contract (FR-021); priority ordering keeps each story independently deliverable.

## Evaluation notes (flywheel)

- Failure modes observed: none — script-created spec file required Read-before-Write once.
- Graders run and results (PASS/FAIL): checklist PASS (16/16).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): run /sp.plan and verify the entity ownership map survives constitution check (agent isolation).
