---
id: 0003
title: foundation-adapters-implementation-plan
stage: plan
date: 2026-07-20
surface: claude-code (vscode)
model: claude-opus-4-8
feature: 002-foundation-adapters
branch: 002-foundation-adapters
user: Muhammad
command: /sp.plan
labels: [plan, adapters, migrations, llm, redis, s3, iam]
links:
  spec: specs/002-foundation-adapters/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/002-foundation-adapters/plan.md
  - specs/002-foundation-adapters/research.md
  - specs/002-foundation-adapters/data-model.md
  - specs/002-foundation-adapters/quickstart.md
  - specs/002-foundation-adapters/contracts/llm-gateway.md
  - specs/002-foundation-adapters/contracts/session-store.md
  - specs/002-foundation-adapters/contracts/file-storage.md
  - specs/002-foundation-adapters/contracts/credentials.md
tests:
  - none (planning artifact only)
---

## Prompt

/sp.plan (no additional user input) — Execute the implementation planning workflow for feature 002-foundation-adapters using the plan template: fill Technical Context, run Constitution Check, produce Phase 0 research.md resolving unknowns, Phase 1 data-model.md, contracts/, quickstart.md, update agent context, re-check constitution post-design.

## Response snapshot

Explored the existing scaffold (exambrain-shared stubs, per-service alembic trees, docker-compose with pgvector pg17 + 3 databases, uv workspace, strict quality gates). Produced:

- **plan.md**: Technical Context (Python 3.12, LiteLLM+tenacity, redis-py asyncio, aioboto3, pgvector Vector(1024)); Constitution Check — all 10 principles PASS, no complexity entries; project structure keeping all adapters in exambrain-shared with a new models/ subpackage split by owning service and per-service Alembic `include_object` filtering.
- **research.md**: 10 decisions — direct litellm.acompletion + tenacity bounded retries (no Router); Bedrock SigV4 config predicate (AWS trio replaces api-key for bedrock provider); in-memory UsageTracker; shared Base + include_object per-service migration filtering; HNSW cosine index on 1024-dim embeddings; redis.asyncio lazy client with fixed-window INCR limiter; aioboto3 streaming upload_fileobj; env-source credential refresh + simulate-principal-policy read-only validation with cannot_verify degradation; hermetic test strategy (fakeredis, fake aioboto3, litellm monkeypatch, migration marker against docker Postgres); new optional Settings fields.
- **data-model.md**: 7 tables across 3 databases with FK/identifier-only split, past-paper status lifecycle, Redis key conventions, UsageRecord as non-DB structure.
- **contracts/**: 4 adapter contracts (llm-gateway, session-store, file-storage, credentials) each with interface, error contract, behavioral guarantees, and test contract.
- **quickstart.md**: stack bring-up, per-service migration commands, verification queries, adapter usage examples, new env vars.
- Agent context updated via update-agent-context.sh opencode.

## Outcome

- ✅ Impact: Complete Phase 0+1 planning artifacts for feature 002; constitution gates pass pre- and post-design.
- 🧪 Tests: None (planning only); test contracts defined per adapter for implementation phase.
- 📁 Files: plan.md, research.md, data-model.md, quickstart.md, 4 contract docs.
- 🔁 Next prompts: /sp.tasks to generate dependency-ordered tasks; propose ADRs (shared-models topology, in-memory usage tracking, fixed-window limiting).
- 🧠 Reflection: All spec clarifications were already resolved in /sp.clarify, so research consolidated technology decisions rather than resolving unknowns; stub-contract preservation (FR-021) shaped every interface choice.

## Evaluation notes (flywheel)

- Failure modes observed: none — setup script, exploration, and artifact generation completed cleanly.
- Graders run and results (PASS/FAIL): Constitution Check PASS (10/10 principles, pre- and post-design).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
