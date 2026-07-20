# Feature Specification: Foundation Adapters

**Feature Branch**: `002-foundation-adapters`
**Created**: 2026-07-20
**Status**: Draft
**Input**: User description: "Foundation adapters: implement features 2-6 from features.md as one feature — real LiteLLM Bedrock bridge (async, retries, token tracking), PostgreSQL+pgvector schema migrations (users, courses, past papers, exam blueprints, sessions, results), async Redis session store (caching, rate-limiting, real-time state), async S3 file adapter (upload/download/list via aioboto3), IAM credential manager (encrypted local cred store, rotation handling, least-privilege validation) — replacing the deferred-error stubs in exambrain-shared"

## Clarifications

### Session 2026-07-20

- Q: Which embedding model does the project standardize on? → A: Amazon Titan Text Embeddings V2 — vector columns fixed at 1024 dimensions.
- Q: Which service database owns which entities? → A: By service domain — course_core: users, courses, exam blueprints, results; ingestion: past papers, document chunks (+vectors); exam_sim: exam sessions. Identifier-only cross-database references.
- Q: Is AWS Bedrock available today? → A: Yes — Bedrock is the primary configured provider; tests still run against simulated providers.
- Q: Is LLM token usage persisted to the database or tracked in-memory only? → A: In-memory only — cumulative counters per model for process lifetime plus structured log lines per call; no usage table is created by this feature's migrations.
- Q: What are the past paper processing status states? → A: `pending → processing → completed / failed` — four states, linear lifecycle; failed is terminal until reprocessing is re-triggered.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Domain Data Foundation (Priority: P1)

As a service developer, I need the core domain data model (users, courses, past papers, exam blueprints, exam sessions, results) created and versioned through migrations, so that every later feature (parsing agents, exam generation, evaluation) has a persistent, consistent place to store and query its data — including vector embeddings for semantic search.

**Why this priority**: Every Phase 2 agent and Phase 3 service depends on this schema. Without it, no other adapter has anything meaningful to persist. It is also the only sub-feature with zero external-account dependencies, so it can be delivered and validated immediately.

**Independent Test**: Run migrations against a fresh local database; verify all tables, relationships, and vector columns exist; insert and query a representative record for each entity; roll the migration back cleanly.

**Acceptance Scenarios**:

1. **Given** a fresh database with no tables, **When** the developer runs the migration command, **Then** all core entity tables are created with their relationships and constraints, and the migration completes without errors.
2. **Given** a migrated database, **When** the developer inserts a document chunk with an embedding vector and runs a similarity query, **Then** the query returns nearest-neighbor results ordered by similarity.
3. **Given** a migrated database, **When** the developer runs the downgrade command, **Then** the schema returns to its prior state without orphaned objects.
4. **Given** two services pointing at their own databases, **When** each runs its own migrations, **Then** neither service's schema changes affect the other's database.

---

### User Story 2 - Reliable LLM Access (Priority: P2)

As an agent developer, I need a single async gateway for all LLM calls that handles provider selection, transient-failure retries, and per-call token/cost tracking, so that agents can request completions and embeddings without knowing which provider is behind them, and the project can monitor spend.

**Why this priority**: All five Phase 2 agents call an LLM; this is the highest-leverage adapter after the schema. It depends only on configuration, not on other adapters.

**Independent Test**: With valid provider configuration, request a completion and an embedding through the gateway and receive results with token usage recorded; with a simulated transient provider failure, observe automatic retry and eventual success; with no configuration, observe the existing clear "not configured" error at call time.

**Acceptance Scenarios**:

1. **Given** valid LLM configuration, **When** an agent requests a completion, **Then** the response text is returned along with prompt/completion token counts for that call.
2. **Given** the provider returns a transient error (rate limit or timeout), **When** a completion is requested, **Then** the gateway retries with backoff and returns the result if a retry succeeds, or a clear error after retries are exhausted.
3. **Given** no LLM configuration, **When** any LLM operation is invoked, **Then** the operation fails immediately with the existing "not configured" error and no network call is attempted.
4. **Given** several completed calls, **When** the developer inspects usage, **Then** cumulative token counts per model are available for the process lifetime.

---

### User Story 3 - Session & Rate-Limit Store (Priority: P3)

As a service developer, I need an async key-value session store with expiring entries and counters, so that exam sessions can keep real-time state (timer, auto-save buffer, focus violations), and endpoints can enforce rate limits.

**Why this priority**: Required by the exam-simulation service (Phase 3) and useful for rate-limiting everywhere, but no Phase 2 agent depends on it, so it follows the schema and LLM gateway.

**Independent Test**: Against the local cache container, store a session object with a time-to-live and read it back; observe it disappear after expiry; increment a rate-limit counter past its threshold and observe the limit trip.

**Acceptance Scenarios**:

1. **Given** a running cache, **When** a session object is stored with a 30-minute expiry, **Then** it is retrievable before expiry and absent after.
2. **Given** a rate limit of N operations per window, **When** N+1 operations occur inside the window, **Then** the N+1th is reported as over-limit.
3. **Given** the cache is unreachable, **When** an operation is attempted, **Then** a clear connection error is raised at call time (never at import or startup).
4. **Given** concurrent updates to the same session key, **When** both complete, **Then** the store's state reflects one of the writes without corruption.

---

### User Story 4 - Course File Storage (Priority: P4)

As a service developer, I need async file storage operations (upload, download, list, delete) for course materials, so that the ingestion pipeline can stream uploaded PDFs/slides/notes to durable object storage and retrieve them for parsing.

**Why this priority**: Needed by the ingestion pipeline (Phase 3) and parsing agent (Phase 2 feature 8); depends on credentials being configured, so it lands after the config-independent adapters.

**Independent Test**: With valid storage configuration, upload a file, list the containing prefix and see it, download it and verify contents match byte-for-byte, then delete it and see it gone; without configuration, every operation raises the existing "not configured" error at call time.

**Acceptance Scenarios**:

1. **Given** valid storage configuration, **When** a file is uploaded under a course's key prefix, **Then** it appears in a listing of that prefix and downloads with identical content.
2. **Given** a download request for a missing key, **When** the operation runs, **Then** a clear "not found" error is raised (distinct from configuration errors).
3. **Given** no storage configuration, **When** any operation is invoked, **Then** it fails with the existing "not configured" error without attempting network access.
4. **Given** a large file (≥50 MB), **When** it is uploaded, **Then** the operation completes without loading the whole file into memory at once.

---

### User Story 5 - Credential Safety (Priority: P5)

As the project operator, I need cloud credentials handled safely — validated at startup for least-privilege scope, never logged or persisted in plaintext by the application, and refreshable without restarting services — so that a leaked log or repo never exposes secrets and expired credentials do not silently break the system mid-operation.

**Why this priority**: Cross-cutting hardening of the other adapters; it modifies how credentials flow but delivers no standalone user-facing capability, so it lands last.

**Independent Test**: Provide credentials and run the validation check — it reports which required permissions are present/missing; rotate the credential source and observe subsequent operations use the new values without a restart; inspect logs and confirm no secret material ever appears.

**Acceptance Scenarios**:

1. **Given** configured credentials, **When** the validation check runs, **Then** it reports each required permission as present or missing without performing any mutating cloud operation.
2. **Given** credentials rotated at the source, **When** the next storage or LLM operation runs after refresh, **Then** it succeeds using the new credentials without a process restart.
3. **Given** any log output from the system, **When** inspected, **Then** no secret value (key, token, password) appears in any log line or error message.
4. **Given** expired credentials, **When** an operation fails authentication, **Then** the error clearly states the credential problem (distinct from "not configured" and from network errors).

---

### Edge Cases

- Embedding dimension mismatch: a stored vector column has fixed dimensions — inserting an embedding of the wrong size must fail loudly at write time, not corrupt queries later.
- Migration on a non-empty database: running migrations against a database that already has data must preserve existing rows.
- LLM provider returns a permanent error (invalid model, auth failure): must NOT be retried; surfaced immediately with the provider's reason.
- Retry storms: retries must be bounded (attempts and total time) so a dead provider cannot hang an agent indefinitely.
- Cache eviction under memory pressure: session loss must be detectable by callers (absent key ≠ crash).
- Concurrent upload of the same storage key: last-writer-wins is acceptable, but partial/corrupt objects are not.
- Clock skew on expiring entries: expiry is enforced by the store, not by client-side timestamps.
- Credential validation when the cloud account lacks the permission-inspection ability itself: validation degrades to a clear "cannot verify" result, not a false pass/fail.
- All existing scaffold behavior must be preserved: services still boot with zero configuration; only invoked operations fail.

## Requirements *(mandatory)*

### Functional Requirements

**Schema & Migrations**

- **FR-001**: System MUST provide versioned, reversible migrations that create the core domain entities: users, courses, past papers, exam blueprints, exam sessions, and results.
- **FR-002**: The schema MUST support storing text chunks with vector embeddings and querying them by similarity. The project standardizes on Amazon Titan Text Embeddings V2 (1024 dimensions); vector columns are fixed at 1024 dimensions and wrong-size writes must fail loudly.
- **FR-003**: Each entity MUST carry creation and last-update timestamps; entities referenced by others MUST enforce referential integrity.
- **FR-004**: Migrations MUST be runnable per service against that service's own database, consistent with the existing one-database-per-service topology. Entity ownership: **course_core** owns users, courses, exam blueprints, and results; **ingestion** owns past papers and document chunks (including embedding vectors); **exam_sim** owns exam sessions. Cross-database references are by identifier only (no cross-database foreign keys).
- **FR-005**: Past papers MUST record their source file reference, course, academic term, and processing status with states `pending → processing → completed / failed` (linear lifecycle; `failed` is terminal until reprocessing is re-triggered); exam blueprints MUST record their structure (sections, question types, marks distribution, topic weights) in a queryable form.
- **FR-006**: Exam sessions MUST record start/end times, status (active, submitted, locked-out, expired), and link to their generated exam and user; results MUST record per-question scores, feedback, and aggregate outcome.

**LLM Gateway**

- **FR-007**: System MUST expose async completion and embedding operations whose provider and model are selected entirely by configuration, with no provider-specific logic in calling code. AWS Bedrock is the primary configured provider (account and model access confirmed available); automated tests still simulate the provider per FR-022.
- **FR-008**: The gateway MUST retry transient failures (rate limits, timeouts, server-side errors) with exponential backoff, bounded by a configurable attempt count and total deadline; permanent errors MUST NOT be retried.
- **FR-009**: Every call MUST record prompt tokens, completion tokens, and model identifier; cumulative usage MUST be inspectable at runtime and included in structured logs. Usage is tracked in-memory only (process lifetime) — no usage table is created by this feature's migrations.
- **FR-010**: With no LLM configuration, operations MUST fail at call time with the existing "not configured" error semantics (no import-time or startup failures).

**Session Store**

- **FR-011**: System MUST provide async operations to set, get, and delete structured session values with per-entry time-to-live, and the store MUST enforce expiry itself.
- **FR-012**: System MUST provide an atomic counter suitable for fixed-window rate limiting (increment-and-check against a configurable threshold and window).
- **FR-013**: Connections MUST be created lazily; an unreachable store MUST surface a clear connection error at call time only.

**File Storage**

- **FR-014**: System MUST provide async upload, download, list-by-prefix, and delete operations for course files, streaming file content rather than buffering whole files in memory.
- **FR-015**: Missing-object, permission, and not-configured failures MUST be distinguishable error types.
- **FR-016**: With no storage configuration, operations MUST fail at call time with the existing "not configured" error semantics.

**Credential Management**

- **FR-017**: System MUST provide a read-only validation check that reports which required cloud permissions are present or missing for the configured credentials.
- **FR-018**: Credentials MUST be re-readable from their source at runtime so rotation does not require a process restart.
- **FR-019**: No secret value may ever appear in logs, error messages, or exception details; violation of this is a defect regardless of log level.
- **FR-020**: Credentials MUST NOT be persisted by the application anywhere in the repository or container image; the only accepted sources are environment configuration and local untracked files already excluded from version control.

**Cross-cutting**

- **FR-021**: All adapters MUST replace the existing deferred-error stubs in the shared library without changing the public contract relied upon by existing tests (import never fails; construction never fails; unconfigured operations raise the existing "not configured" error).
- **FR-022**: All new code MUST meet the existing quality gates: strict typing, lint/format hooks, and the 80% coverage floor, with tests that do not require live cloud accounts (external providers simulated).

### Key Entities

- **User**: A student using the platform; identity, display name, contact identifier; owns courses, sessions, and results.
- **Course**: A unit of study owned by a user; title, code, instructor identity; parent of past papers, blueprints, and materials.
- **Past Paper**: A historical exam document for a course; source file reference, term/year, processing status (`pending`/`processing`/`completed`/`failed`); input to blueprint extraction.
- **Exam Blueprint**: Extracted or generated exam structure for a course; sections, question types, marks distribution, topic weight matrix; versioned per course.
- **Exam Session**: One timed exam attempt by a user; generated exam content reference, start/end, status, focus-violation count.
- **Result**: Outcome of a completed session; per-question scores and feedback, aggregate score, weak-topic index contribution.
- **Document Chunk**: A parsed fragment of course material or past paper; text, position/hierarchy metadata, embedding vector; the unit of semantic retrieval.
- **Usage Record**: Token consumption of one LLM call; model, prompt/completion token counts, timestamp; held in-memory (process lifetime) and emitted to structured logs — not a database entity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer on a fresh checkout can bring up the local stack and apply all migrations in under 5 minutes, ending with every core entity queryable.
- **SC-002**: A similarity query over at least 1,000 stored chunks returns ranked results in under 1 second locally.
- **SC-003**: With provider configuration present, an agent completes an LLM round-trip (request → response with token counts) on the first attempt in at least 95% of calls, and transient failures recover automatically without caller involvement.
- **SC-004**: Token usage for any given call and cumulative usage per model are retrievable at runtime with zero manual bookkeeping by callers.
- **SC-005**: Session values expire within 5 seconds of their nominal time-to-live, and rate limits trip at exactly the configured threshold in a controlled test.
- **SC-006**: A 100 MB file uploads and downloads successfully with process memory growth under 25% of the file size during the transfer.
- **SC-007**: Credential validation completes in under 10 seconds and its report matches the actual permission state in a controlled test; zero secret values appear in any captured log output across the full test suite.
- **SC-008**: All existing scaffold tests continue to pass unchanged, and overall coverage remains at or above 80%.

## Assumptions

- The one-database-per-service topology from feature 001 is retained; this feature adds tables, not databases.
- "Encrypted local cred store" is interpreted as: secrets live only in environment variables / untracked local env files (already gitignored), with OS-level protections; the application itself does not implement a custom encryption vault. If a hardware/OS keychain integration is wanted, that is future scope.
- Rate limiting uses fixed-window counting (simplest correct approach); sliding-window precision is future scope if needed.
- Token cost-to-currency conversion is out of scope; the system records token counts and model identifiers, which is sufficient for cost monitoring.
- Redis-backed session state is authoritative for in-flight exam sessions; completed sessions are persisted to the relational store by later features (exam-simulation service), not by this one.
- No user-facing API endpoints are added by this feature; it delivers shared-library capability and schema consumed by later features.
- LiteLLM's provider-agnostic interface satisfies the constitution's LLM-abstraction principle; swapping providers (e.g., Bedrock ↔ local models) remains a configuration change.
