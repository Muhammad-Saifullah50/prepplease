# ExamBrain Constitution

## Core Principles

### I. Spec-Driven Development (SDD) — NON-NEGOTIABLE
All work follows the strict sequence: Spec → Plan → Tasks → Implementation. Every user prompt must be recorded as a Prompt History Record (PHR) in `history/prompts/`. All architecturally significant decisions require an Architecture Decision Record (ADR) proposed to the user for consent — never auto-created.

### II. Zero-Cost Infrastructure Mandate
Every design decision must fit within Oracle Always Free (4 OCPUs, 24GB RAM) + AWS Free Tier. Total target RAM footprint: ~2.4GB. No paid infrastructure services, no provisioned concurrency, no reserved instances unless explicitly approved in writing. If a design exceeds these limits, it must be re-architected.

### III. Agent Isolation & Contract-First
The 5 specialized agents (parsing, instructor alignment, blueprint extraction, exam generation, TA evaluation) MUST:
- Communicate via well-defined interfaces with no shared state
- Have independent, versioned prompt templates
- Be testable in isolation with mocked dependencies
- Use event-driven communication (Redis pub/sub or message queue) rather than direct coupling

### IV. Async-First, Everywhere
All services MUST use async Python: `asyncio` + `asyncpg` + `httpx`. No synchronous blocking I/O in request paths. Database connections, HTTP calls, and LLM invocations must all be non-blocking.

### V. LLM Provider Abstraction
All LLM invocations MUST go through LiteLLM. Providers (AWS Bedrock Claude 3.5 Sonnet, GPT-4o) must be swappable via environment configuration. Never hardcode a provider name, model ID, or API key outside of configuration. The provider abstraction layer must be a single, well-defined module.

### VI. TDD on Critical Paths — NON-NEGOTIABLE
The following MUST follow Red-Green-Refactor:
- Blueprint extraction logic (marks distribution, pattern recognition)
- Exam generation algorithms (question selection, paper assembly)
- Marks calculation and grading logic

Minimum 80% code coverage across `agents/` and `services/`. All bug fixes MUST start with a failing test.

### VII. Repository Pattern & Data Integrity
All database access MUST go through a repository layer. No raw SQL in route handlers, no direct `Session` usage in API endpoints. All schema changes MUST use Alembic migrations — never alter the database schema directly. Use `pgvector` for embeddings via the repository layer.

### VIII. Code Quality & Standards — NON-NEGOTIABLE
- **No workarounds, no hacks** — If a pattern feels wrong, fix it properly or open an issue. Never leave `# TODO`, `# FIXME`, `# HACK`, or `# XXX` in committed code.
- **Self-documenting code** — Every function and method MUST have a Google-style docstring (args, returns, raises). Type hints are required everywhere (enforced with `mypy strict`). No inline comments explaining what the code does (the code and types should make that obvious); only use comments to explain why a non-obvious decision was made.
- **Minimal diffs** — Change only what's required by the spec or task. No refactoring of unrelated code, no incidental cleanup, no "while we're here" changes.
- **Linting & formatting** — `ruff` for linting, `black` (line length 88) for formatting. Both MUST pass via pre-commit hook and CI. Formatting is fully automated and non-negotiable.
- **No dead code** — Unused imports, unreachable branches, commented-out code, and orphaned functions are unacceptable. Remove them immediately.
- **Naming conventions**: Python functions/variables in `snake_case`, classes in `PascalCase`, database columns in `snake_case`, environment variables in `SCREAMING_SNAKE_CASE`, API routes in `kebab-case`.

### IX. Security by Default
- No secrets in committed files — `.env` in `.gitignore`, all secrets via environment variables
- FastAPI routes require authentication by default (explicit whitelist for public routes)
- Input validation using Pydantic v2 at every API boundary
- S3 access via signed URLs with expiration, never public buckets
- Rate limiting on all public endpoints

### X. Observability & Operations
- Structured JSON logging on all services
- Health check endpoints on every service (`/health`)
- All LLM calls must log: provider, model, prompt hash, latency, token count (never log raw prompts or responses)
- Redis for caching and event bus — cache hit rates must be measurable

## Tech Stack Constraints

| Layer | Technology | Constraint |
|---|---|---|
| Language | Python 3.12+ | No other languages without ADR |
| API Framework | FastAPI | All services |
| Database | PostgreSQL + pgvector | Via asyncpg + SQLAlchemy |
| Cache/Queue | Redis | Event bus + caching |
| LLM Gateway | LiteLLM → AWS Bedrock | Single abstraction layer |
| Object Storage | AWS S3 (future: MinIO) | Signed URLs only |
| Containerization | Docker + docker-compose | Local dev |
| Orchestration | K3s on OCI | Production |
| Auth | Future: JWT-based | Whitelist-by-default |

## Development Workflow

1. All work begins with a spec in `specs/<feature>/spec.md`
2. Architecture decisions documented in `specs/<feature>/plan.md`
3. Tasks broken down in `specs/<feature>/tasks.md`
4. Implementation: TDD on critical paths, test-after acceptable on UI/non-critical
5. Every PR must pass: `ruff` → `black --check` → `mypy` → `pytest`
6. PHR created after every significant user interaction
7. ADR proposed for any architecture-significant decision

## Governance

This constitution is the single source of truth for all development standards. It supersedes all other practices, guidelines, and preferences.

**Amendment Process:**
1. Propose change via PR with documented rationale
2. Update constitution with version bump
3. Migration plan if breaking changes
4. Merge only after validation and user approval

**Version Semantics:**
- MAJOR: Backward-incompatible governance changes (principle removal/redefinition)
- MINOR: New principles or materially expanded guidance
- PATCH: Clarifications, wording, formatting fixes

**Compliance:** All contributions must adhere to these principles. Violations of NON-NEGOTIABLE items are grounds for PR rejection.

**Version**: 1.0.0 | **Ratified**: 2026-07-19 | **Last Amended**: 2026-07-19
