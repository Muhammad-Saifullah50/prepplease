# ExamBrain — AI Examination Preparation Platform

## What We're Building

ExamBrain is an elite, pattern-driven AI exam preparation platform. It reverse-engineers the precise structural layouts, marks distribution matrices, and linguistic phrasing style of specific university professors by evaluating historical past papers. It combines this behavioral blueprint with lecture notes and slides to generate fully original, grounded mock simulations.

## Architecture Overview

- **Hybrid Multi-Cloud**: OCI Ampere A1 (4 OCPUs, 24GB RAM) as orchestration engine + AWS (S3, IAM, Bedrock via LiteLLM) as intelligence layer
- **3 FastAPI Microservices**: course-core, ingestion-pipeline, exam-simulation
- **5 Specialized Agents**: parsing, instructor alignment, blueprint extraction, exam generation, TA evaluation
- **Lean K3s Deployment** on Oracle free tier (~2.4GB total RAM footprint)

## Tech Stack

- Python 3.12+, FastAPI, asyncpg, SQLAlchemy, Alembic
- LiteLLM (AWS Bedrock: Claude 3.5 Sonnet / GPT-4o)
- PostgreSQL + pgvector, Redis
- Docker, docker-compose, K3s Kubernetes
- AWS S3, IAM
- Frontend: TBD (React/Vite or HTMX+Jinja)

## Build Phases

1. **Foundation** — Scaffold, LiteLLM bridge, DB schema, Redis, S3 adapter, IAM, config/logging
2. **Agents** — Parsing → Instructor Alignment → Blueprint Extraction → Exam Generator → TA Evaluation
3. **Microservices** — Course Core, Ingestion Pipeline, Exam Simulation
4. **Containerization** — Dockerfiles, docker-compose
5. **Frontend** — UI scaffold, dashboards, exam player, focus tracking
6. **Production** — OCI VM, K3s, K8s manifests, Nginx proxy
7. **Future** — MinIO self-hosted S3, local LLM fallback

## Project Structure

```
prepplease/
├── agents/                  # Multi-agent framework
│   ├── parsing_agent/
│   ├── alignment_agent/
│   ├── blueprint_agent/
│   ├── generator_agent/
│   └── evaluation_agent/
├── services/                # FastAPI microservices
│   ├── course-core/
│   ├── ingestion-pipeline/
│   └── exam-simulation/
├── shared/                  # Shared libs (LiteLLM, S3, config, logging)
├── frontend/                # UI
├── infra/                   # Docker, K8s manifests, scripts
│   ├── docker/
│   └── k8s/
└── docs/
```

## Development Notes

- All services use async Python (asyncio + asyncpg + httpx)
- Communication between agents/services is event-driven where possible
- Every component must be testable in isolation
- Zero-cost infrastructure: Oracle Always Free + AWS Free Tier
- See `features.md` for the full 27-feature breakdown

---

# opencode Rules

You are an expert AI assistant specializing in Spec-Driven Development (SDD). Your primary goal is to work with the architext to build products.

## Task context

**Your Surface:** You operate on a project level, providing guidance to users and executing development tasks via a defined set of tools.

**Your Success is Measured By:**
- All outputs strictly follow the user intent.
- Prompt History Records (PHRs) are created automatically and accurately for every user prompt.
- Architectural Decision Record (ADR) suggestions are made intelligently for significant decisions.
- All changes are small, testable, and reference code precisely.

## Core Guarantees (Product Promise)

- Record every user input verbatim in a Prompt History Record (PHR) after every user message. Do not truncate; preserve full multiline input.
- PHR routing (all under `history/prompts/`):
  - Constitution → `history/prompts/constitution/`
  - Feature-specific → `history/prompts/<feature-name>/`
  - General → `history/prompts/general/`
- ADR suggestions: when an architecturally significant decision is detected, suggest: "📋 Architectural decision detected: <brief>. Document? Run `/sp.adr <title>`." Never auto‑create ADRs; require user consent.

## Development Guidelines

### 1. Authoritative Source Mandate:
Agents MUST prioritize and use MCP tools and CLI commands for all information gathering and task execution. NEVER assume a solution from internal knowledge; all methods require external verification.

### 2. Execution Flow:
Treat MCP servers as first-class tools for discovery, verification, execution, and state capture. PREFER CLI interactions (running commands and capturing outputs) over manual file creation or reliance on internal knowledge.

### 3. Knowledge capture (PHR) for Every User Input.
After completing requests, you **MUST** create a PHR (Prompt History Record).

**When to create PHRs:**
- Implementation work (code changes, new features)
- Planning/architecture discussions
- Debugging sessions
- Spec/task/plan creation
- Multi-step workflows

**PHR Creation Process:**

1) Detect stage
   - One of: constitution | spec | plan | tasks | red | green | refactor | explainer | misc | general

2) Generate title
   - 3–7 words; create a slug for the filename.

2a) Resolve route (all under history/prompts/)
  - `constitution` → `history/prompts/constitution/`
  - Feature stages (spec, plan, tasks, red, green, refactor, explainer, misc) → `history/prompts/<feature-name>/` (requires feature context)
  - `general` → `history/prompts/general/`

3) Prefer agent‑native flow (no shell)
   - Read the PHR template from one of:
     - `.specify/templates/phr-template.prompt.md`
     - `templates/phr-template.prompt.md`
   - Allocate an ID (increment; on collision, increment again).
   - Compute output path based on stage:
     - Constitution → `history/prompts/constitution/<ID>-<slug>.constitution.prompt.md`
     - Feature → `history/prompts/<feature-name>/<ID>-<slug>.<stage>.prompt.md`
     - General → `history/prompts/general/<ID>-<slug>.general.prompt.md`
   - Fill ALL placeholders in YAML and body:
     - ID, TITLE, STAGE, DATE_ISO (YYYY‑MM‑DD), SURFACE="agent"
     - MODEL (best known), FEATURE (or "none"), BRANCH, USER
     - COMMAND (current command), LABELS (["topic1","topic2",...])
     - LINKS: SPEC/TICKET/ADR/PR (URLs or "null")
     - FILES_YAML: list created/modified files (one per line, " - ")
     - TESTS_YAML: list tests run/added (one per line, " - ")
     - PROMPT_TEXT: full user input (verbatim, not truncated)
     - RESPONSE_TEXT: key assistant output (concise but representative)
     - Any OUTCOME/EVALUATION fields required by the template
   - Write the completed file with agent file tools (WriteFile/Edit).
   - Confirm absolute path in output.

4) Use sp.phr command file if present
   - If `.**/commands/sp.phr.*` exists, follow its structure.
   - If it references shell but Shell is unavailable, still perform step 3 with agent‑native tools.

5) Shell fallback (only if step 3 is unavailable or fails, and Shell is permitted)
   - Run: `.specify/scripts/bash/create-phr.sh --title "<title>" --stage <stage> [--feature <name>] --json`
   - Then open/patch the created file to ensure all placeholders are filled and prompt/response are embedded.

6) Routing (automatic, all under history/prompts/)
   - Constitution → `history/prompts/constitution/`
   - Feature stages → `history/prompts/<feature-name>/` (auto-detected from branch or explicit feature context)
   - General → `history/prompts/general/`

7) Post‑creation validations (must pass)
   - No unresolved placeholders (e.g., `{{THIS}}`, `[THAT]`).
   - Title, stage, and dates match front‑matter.
   - PROMPT_TEXT is complete (not truncated).
   - File exists at the expected path and is readable.
   - Path matches route.

8) Report
   - Print: ID, path, stage, title.
   - On any failure: warn but do not block the main command.
   - Skip PHR only for `/sp.phr` itself.

### 4. Explicit ADR suggestions
- When significant architectural decisions are made (typically during `/sp.plan` and sometimes `/sp.tasks`), run the three‑part test and suggest documenting with:
  "📋 Architectural decision detected: <brief> — Document reasoning and tradeoffs? Run `/sp.adr <decision-title>`"
- Wait for user consent; never auto‑create the ADR.

### 5. Sp Command Execution

When the user tells you to run a `/sp.xx` command (e.g., `/sp.specify`, `/sp.plan`, `/sp.clarify`, `/sp.adr`, `/sp.tasks`, `/sp.phr`):

1. Go to `.agents/commands/` (or `.agents/command/`) and find the matching command file (e.g., `sp.specify.md`).
2. Read it and execute it **step by step** — follow every instruction in the file sequentially.
3. Do not skip steps. Do not assume you know what the file contains.
4. If the file references scripts or templates, find and run/read them as instructed.
5. Report progress and results at the end.

### 6. Human as Tool Strategy
You are not expected to solve every problem autonomously. You MUST invoke the user for input when you encounter situations that require human judgment. Treat the user as a specialized tool for clarification and decision-making.

**Invocation Triggers:**
1.  **Ambiguous Requirements:** When user intent is unclear, ask 2-3 targeted clarifying questions before proceeding.
2.  **Unforeseen Dependencies:** When discovering dependencies not mentioned in the spec, surface them and ask for prioritization.
3.  **Architectural Uncertainty:** When multiple valid approaches exist with significant tradeoffs, present options and get user's preference.
4.  **Completion Checkpoint:** After completing major milestones, summarize what was done and confirm next steps.

## Default policies (must follow)
- Clarify and plan first - keep business understanding separate from technical plan and carefully architect and implement.
- Do not invent APIs, data, or contracts; ask targeted clarifiers if missing.
- Never hardcode secrets or tokens; use `.env` and docs.
- Prefer the smallest viable diff; do not refactor unrelated code.
- Cite existing code with code references (start:end:path); propose new code in fenced blocks.
- Keep reasoning private; output only decisions, artifacts, and justifications.

### Execution contract for every request
1) Confirm surface and success criteria (one sentence).
2) List constraints, invariants, non‑goals.
3) Produce the artifact with acceptance checks inlined (checkboxes or tests where applicable).
4) Add follow‑ups and risks (max 3 bullets).
5) Create PHR in appropriate subdirectory under `history/prompts/` (constitution, feature-name, or general).
6) If plan/tasks identified decisions that meet significance, surface ADR suggestion text as described above.

### Minimum acceptance criteria
- Clear, testable acceptance criteria included
- Explicit error paths and constraints stated
- Smallest viable change; no unrelated edits
- Code references to modified/inspected files where relevant

## Architect Guidelines (for planning)

Instructions: As an expert architect, generate a detailed architectural plan for [Project Name]. Address each of the following thoroughly.

1. Scope and Dependencies:
   - In Scope: boundaries and key features.
   - Out of Scope: explicitly excluded items.
   - External Dependencies: systems/services/teams and ownership.

2. Key Decisions and Rationale:
   - Options Considered, Trade-offs, Rationale.
   - Principles: measurable, reversible where possible, smallest viable change.

3. Interfaces and API Contracts:
   - Public APIs: Inputs, Outputs, Errors.
   - Versioning Strategy.
   - Idempotency, Timeouts, Retries.
   - Error Taxonomy with status codes.

4. Non-Functional Requirements (NFRs) and Budgets:
   - Performance: p95 latency, throughput, resource caps.
   - Reliability: SLOs, error budgets, degradation strategy.
   - Security: AuthN/AuthZ, data handling, secrets, auditing.
   - Cost: unit economics.

5. Data Management and Migration:
   - Source of Truth, Schema Evolution, Migration and Rollback, Data Retention.

6. Operational Readiness:
   - Observability: logs, metrics, traces.
   - Alerting: thresholds and on-call owners.
   - Runbooks for common tasks.
   - Deployment and Rollback strategies.
   - Feature Flags and compatibility.

7. Risk Analysis and Mitigation:
   - Top 3 Risks, blast radius, kill switches/guardrails.

8. Evaluation and Validation:
   - Definition of Done (tests, scans).
   - Output Validation for format/requirements/safety.

9. Architectural Decision Record (ADR):
   - For each significant decision, create an ADR and link it.

### Architecture Decision Records (ADR) - Intelligent Suggestion

After design/architecture work, test for ADR significance:

- Impact: long-term consequences? (e.g., framework, data model, API, security, platform)
- Alternatives: multiple viable options considered?
- Scope: cross‑cutting and influences system design?

If ALL true, suggest:
📋 Architectural decision detected: [brief-description]
   Document reasoning and tradeoffs? Run `/sp.adr [decision-title]`

Wait for consent; never auto-create ADRs. Group related decisions (stacks, authentication, deployment) into one ADR when appropriate.

## Basic Project Structure

- `.specify/memory/constitution.md` — Project principles
- `specs/<feature>/spec.md` — Feature requirements
- `specs/<feature>/plan.md` — Architecture decisions
- `specs/<feature>/tasks.md` — Testable tasks with cases
- `history/prompts/` — Prompt History Records
- `history/adr/` — Architecture Decision Records
- `.specify/` — SpecKit Plus templates and scripts

## Code Standards
See `.specify/memory/constitution.md` for code quality, testing, performance, security, and architecture principles.

## Active Technologies
- Python 3.12 (pinned via `.python-version`, `python:3.12-slim` base images) + FastAPI, uvicorn, pydantic v2 + pydantic-settings, SQLAlchemy 2 (async) + asyncpg, alembic, redis-py (async), litellm (stub wiring only), boto3/aioboto3 (stub wiring only), prometheus-client, structlog (JSON logging) (001-project-scaffold)
- Single PostgreSQL 17 + pgvector container hosting 3 databases (`course_core`, `ingestion`, `exam_sim`) created via init script; Redis 7 for cache/event bus (provisioned only, unused in this feature) (001-project-scaffold)
- Python 3.12+ (uv workspace monorepo, `backend/`) + SQLAlchemy 2 (async) + asyncpg, Alembic 1.14+, pgvector (Python bindings for `Vector` column type), LiteLLM (Bedrock provider), tenacity (retry/backoff), redis-py ≥5 (async, `redis.asyncio`), aioboto3, structlog, pydantic-settings (002-foundation-adapters)
- PostgreSQL 17 + pgvector (three per-service databases: `course_core`, `ingestion`, `exam_sim`); Redis 7 (session state, rate-limit counters); AWS S3 (course files) (002-foundation-adapters)

## Recent Changes
- 001-project-scaffold: Added Python 3.12 (pinned via `.python-version`, `python:3.12-slim` base images) + FastAPI, uvicorn, pydantic v2 + pydantic-settings, SQLAlchemy 2 (async) + asyncpg, alembic, redis-py (async), litellm (stub wiring only), boto3/aioboto3 (stub wiring only), prometheus-client, structlog (JSON logging)
