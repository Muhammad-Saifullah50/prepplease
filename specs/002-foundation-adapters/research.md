# Research: Foundation Adapters

**Feature**: 002-foundation-adapters | **Date**: 2026-07-20

All spec-level NEEDS CLARIFICATION items were resolved during `/sp.clarify` (embedding model, DB ownership, Bedrock availability, usage persistence, past-paper states). This document records the remaining technology decisions.

## R1: LLM gateway — LiteLLM async API + tenacity retries

- **Decision**: Use `litellm.acompletion` / `litellm.aembedding` directly (no `litellm.Router`), wrapped in the existing `LLMClient` class. Retries via `tenacity.AsyncRetrying` with exponential backoff + jitter, bounded by configurable attempt count and total deadline. Classify errors using LiteLLM's mapped exception types: `RateLimitError`, `Timeout`, `APIConnectionError`, `InternalServerError`/`ServiceUnavailableError` → transient (retry); `AuthenticationError`, `BadRequestError`, `NotFoundError`, `ContextWindowExceededError` → permanent (raise immediately, wrapped as `PermanentLLMError` carrying the provider reason).
- **Rationale**: Constitution V mandates LiteLLM as the single abstraction; `acompletion` is fully async (Constitution IV). Tenacity gives declarative, testable bounded retry (attempts + `stop_after_delay`) rather than hand-rolled loops. LiteLLM normalizes provider exceptions to OpenAI-style types, so classification is provider-agnostic. Disabling LiteLLM's own internal retries (`num_retries=0`) keeps a single retry authority.
- **Alternatives considered**: LiteLLM `Router` (built-in retry/fallback) — rejected: adds deployment-list config complexity for a single-provider setup and hides retry behavior from tests. Hand-rolled backoff loop — rejected: tenacity is already the ecosystem standard and gives `stop_after_attempt | stop_after_delay` composition for free.

## R2: Bedrock configuration & auth path

- **Decision**: Bedrock model IDs via existing `LLM_MODEL` env (e.g. `bedrock/eu.anthropic.claude-3-5-sonnet-20240620-v1:0`), embeddings via new `LLM_EMBEDDING_MODEL` (e.g. `bedrock/amazon.titan-embed-text-v2:0`). Credentials flow through the standard AWS env vars already in `Settings` (`aws_access_key_id`, `aws_secret_access_key`, `aws_region`), passed explicitly per call to LiteLLM — never read from global state inside the adapter. `is_configured` for the LLM adapter becomes: `llm_provider` + `llm_model` + (`llm_api_key` **or** AWS credential trio when provider is bedrock).
- **Rationale**: Titan Text Embeddings V2 is the clarified standard (1024 dims). Bedrock uses SigV4 (AWS keys), not an API key, so the configuration predicate must accept AWS credentials for the bedrock provider while preserving the existing `NotConfiguredError` semantics. Passing credentials per call (not via `os.environ` mutation) enables restart-free rotation (FR-018).
- **Alternatives considered**: Requiring `LLM_API_KEY` always — rejected: meaningless for Bedrock/SigV4. Separate `BedrockClient` — rejected: violates Constitution V single-module abstraction.

## R3: Token usage tracking — in-memory tracker + structlog

- **Decision**: A `UsageTracker` in `llm_usage.py`: per-call `UsageRecord` (model, prompt/completion tokens, timestamp) appended under an `asyncio.Lock`-free simple counter design (single-threaded event loop; plain dict of per-model cumulative counters + total). Every call emits a structlog event with model, prompt hash, latency, token counts — never raw prompt/response text (Constitution X). Exposed via `LLMClient.usage` property returning per-model and total counts.
- **Rationale**: Clarified as in-memory only (no usage table). LiteLLM responses carry `usage.prompt_tokens`/`completion_tokens` uniformly across providers.
- **Alternatives considered**: LiteLLM callbacks/`success_callback` — rejected: global mutable hooks are hard to isolate in tests; explicit tracking in the gateway is simpler and testable. DB persistence — rejected by clarification.

## R4: Schema topology — shared ORM models, per-service Alembic filtering

- **Decision**: All ORM models live in `exambrain_shared.models` on the existing shared `Base`, tagged with their owning service via `__table_args__ = {"info": {"service": "<name>"}}` (or a per-model registry dict). Each service's `alembic/env.py` gains an `include_object` filter selecting only its service's tables, so autogenerate and upgrade per service touch only that service's database. Cross-database references (e.g. `past_papers.course_id`, `exam_sessions.user_id`) are plain `UUID` columns — no cross-DB FKs (per clarification). Within a database, real FKs with `ON DELETE` behavior enforce integrity (FR-003).
- **Rationale**: One shared `Base` keeps models importable by any service (agents need chunk/blueprint types) while `include_object` preserves the one-DB-per-service topology (FR-004). This mirrors the existing scaffold: shared `Base` in `db.py`, per-service alembic trees already exist with empty `versions/`.
- **Alternatives considered**: Three separate `Base` classes / metadata objects — viable but forces awkward imports and triple engine plumbing in `db.py`; `include_object` filtering is the standard Alembic multi-DB pattern. Models inside each service package — rejected: agents (outside services) must import chunk/blueprint models; shared library is the sanctioned home.

## R5: pgvector integration & similarity index

- **Decision**: Use the `pgvector` Python package's SQLAlchemy support: `Vector(1024)` column on `document_chunks.embedding`. Migration for the ingestion DB runs `CREATE EXTENSION IF NOT EXISTS vector` (idempotent; docker init already creates it) then creates an **HNSW** index with `vector_cosine_ops`. Wrong-dimension inserts fail loudly — pgvector enforces declared dimensions at write time (FR-002 edge case satisfied natively).
- **Rationale**: Titan V2 → 1024 dims fixed. HNSW beats IVFFlat for quality without needing a populated table at index-build time, and 1k–100k chunks is well within HNSW memory budget on the free-tier VM. Cosine ops match normalized-embedding similarity semantics.
- **Alternatives considered**: IVFFlat — rejected: requires data-dependent `lists` tuning and degrades on empty-table creation. No index (exact scan) — meets SC-002 at 1k chunks but not as corpus grows; HNSW now avoids a follow-up migration.

## R6: Redis session store — redis-py asyncio, lazy client, fixed-window limiter

- **Decision**: Use `redis.asyncio` (redis-py ≥5) with a lazily created client (`Redis.from_url`) on first operation — no connection at import/construct (FR-013). `SessionStore`: `set_session(key, value: dict, ttl)` → `SET key json EX ttl`; `get_session` → JSON decode or `None`; `delete_session`. Expiry is server-side via `EX` (clock-skew edge case). `RateLimiter`: fixed-window via atomic `INCR` + `EXPIRE NX` (single pipeline / Lua-free: `INCR` then set expiry only when count==1), returning allowed/denied against threshold.
- **Rationale**: redis-py's asyncio API is the maintained successor to aioredis (aioredis was archived into redis-py). Fixed-window is the clarified/assumed approach. `INCR` is atomic, so concurrent increments are safe; JSON values keep sessions structured (FR-011). Absent key returns `None` (eviction edge case: detectable, not a crash).
- **Alternatives considered**: aioredis — deprecated/merged. Sliding-window (sorted-set) limiter — explicitly future scope per spec assumptions. Redis hashes per session — rejected: JSON blob + TTL is simpler and matches "structured session values with per-entry TTL".

## R7: S3 adapter — aioboto3 streaming

- **Decision**: `aioboto3.Session(...).client("s3")` created lazily per operation scope (async context manager). Upload: accept an async-iterable/file-like and use `upload_fileobj` (multipart under the hood — streams, satisfies FR-014/SC-006); download: `get_object` streaming body read in chunks to a provided sink / async iterator; `list_objects_v2` paginator for list-by-prefix; `delete_object`. Error mapping: `NoSuchKey`/404 → `ObjectNotFoundError`; `AccessDenied`/403 → `PermissionDeniedError`; `ExpiredToken`/`InvalidClientTokenId` → `CredentialError`; missing config → existing `NotConfiguredError` (FR-015/016).
- **Rationale**: aioboto3 is named in the feature brief; `upload_fileobj`/`download_fileobj` do managed multipart transfers without whole-file buffering. Explicit typed errors satisfy FR-015's distinguishable failures.
- **Alternatives considered**: Raw `aiobotocore` — aioboto3 wraps it with the friendlier resource/client API. Presigned-URL-only design — signed URLs are for later API surface (Constitution IX); the pipeline needs direct streaming ops.

## R8: Credential manager — env-source refresh, read-only validation

- **Decision**: `CredentialManager` in `iam.py` reads AWS credentials from a `Settings`-backed source on each `refresh()` (re-instantiating `Settings` to re-read env/.env — bypassing the `lru_cache`), so rotation at the source is picked up without restart (FR-018). Validation (FR-017) is read-only: `sts get-caller-identity` (proves credentials valid) + `iam simulate-principal-policy` over the required action list (`s3:GetObject/PutObject/DeleteObject/ListBucket`, `bedrock:InvokeModel`); if the account lacks `iam:SimulatePrincipalPolicy`, degrade to a per-permission `"cannot verify"` result (edge case). Secret redaction: credentials never appear in `__repr__`, logs, or raised errors — errors reference the credential *source name* only; a test asserts no secret substring appears in captured log output across the suite (SC-007).
- **Rationale**: The spec's clarified interpretation is env-vars/untracked-env-files as the "encrypted local cred store" — no custom vault. `simulate-principal-policy` is the only non-mutating way to check permissions ahead of use; graceful degradation is explicitly required. The existing `IAMClient` stub methods (`validate_token`, `get_caller_identity`) are preserved contract-wise while gaining real implementations (`get_caller_identity` via aioboto3 STS).
- **Alternatives considered**: Dry-run actual operations (e.g. tiny S3 put) — rejected: mutating (FR-017 forbids). OS keychain integration — future scope per spec assumptions.

## R9: Test strategy without live cloud accounts (FR-022)

- **Decision**: LLM — monkeypatch `litellm.acompletion`/`aembedding` with fakes returning canned responses and raising LiteLLM exception types for retry-path tests. Redis — `fakeredis[async]` (`FakeAsyncRedis`) injected via the store's client factory; TTL behavior driven by fakeredis time controls. S3/IAM — stub the aioboto3 client with an in-memory fake implementing the handful of used methods (avoids moto's aiobotocore-version fragility); error paths raise real `botocore.exceptions.ClientError` payloads for mapping tests. Migrations — pytest marker `migration` running upgrade → insert → similarity query → downgrade against the docker-compose Postgres; skipped automatically when the DB is unreachable so CI/unit runs stay hermetic, executed in the local stack for SC-001/SC-002.
- **Rationale**: Keeps the 80% floor achievable hermetically; migration correctness genuinely needs a real Postgres+pgvector (similarity operators can't be faked meaningfully) and the compose stack already provides it.
- **Alternatives considered**: moto for S3 — heavier dependency and async-support churn; a 50-line fake client is deterministic. Testcontainers — extra dependency; compose stack already standard for this repo.

## R10: New settings fields

- **Decision**: Extend `Settings` (all optional, preserving never-raise construction): `llm_embedding_model`, `llm_max_retries` (default 3), `llm_retry_deadline_seconds` (default 60), `rate_limit_default_threshold`, `rate_limit_default_window_seconds`, `s3_endpoint_url` (future MinIO swap). `redis_url` already exists.
- **Rationale**: FR-008 requires configurable attempt count and total deadline; `s3_endpoint_url` keeps the future MinIO path (tech-stack table) a pure config change.
- **Alternatives considered**: Hardcoded retry policy — violates FR-008.
