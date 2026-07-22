# Research: Exam Simulation Service

## Decisions

### 1. Deadline Enforcement Mechanism

**Decision**: In-process asyncio background task checking every 10s.

**Rationale**: No new dependencies (APScheduler/celery beat). The task scans for attempts where `deadline < now() AND status = 'active'`, finishes them, and queues grading. On service restart, a startup scan catches any missed deadlines. The 10s granularity satisfies SC-003 ("within seconds of expiry").

**Alternatives considered**:
- **APScheduler**: Adds a dependency for what is essentially a simple loop.
- **Client-side enforcement**: Not trustworthy — the server is the authority per FR-003.
- **PostgreSQL pg_cron**: Not available; managed PG.

### 2. Finish Idempotency (FR-009)

**Decision**: PostgreSQL row-level locking with optimistic check.

**Rationale**: In the finish transaction, `SELECT ... FOR UPDATE` on the attempt row, then check `ended_at IS NOT NULL`. If already finished, return the existing finished state without error. If not, update and trigger grading once. This guarantees exactly-one-finish without distributed locking.

**Alternatives considered**:
- **Redis distributed lock**: Unnecessary — all finish requests hit the same PG row.
- **Application-level mutex**: Works only within one process; breaks with multiple replicas.

### 3. Redis for Live Attempt State

**Decision**: PG as source of truth; Redis as read cache for polling.

**Rationale**: On answer save, write to PG + set/update Redis hash with TTL = remaining time. On poll (FR-004), read from Redis (cache hit) or PG (cache miss, repopulate). On finish/lockout, delete Redis key. This keeps polling fast (SC-005: <2s submit, implies fast reads) while PG remains authoritative for durability.

**Alternatives considered**:
- **PG-only**: Simpler but higher latency for polling (every ~5s read from PG).
- **Redis-only with async PG writes**: Risk of data loss on Redis failure.

### 4. Debounced Answer Saving (FR-005)

**Decision**: API accepts a partial list of `{question_number, answer_text}` pairs with upsert semantics per question. Client handles debouncing.

**Rationale**: The spec explicitly says "client saving each answer a short debounce interval after the student stops editing it" — the server is stateless with respect to debouncing. Upsert per question means the client can send only changed answers (small payloads). Stored as JSONB in the attempt row.

**Alternatives considered**:
- **Atomic full-replacement**: Client sends all answers every time. Wastes bandwidth.
- **Append-only log of answer deltas**: Over-engineered for this use case.

### 5. Time-Limit Extraction Format Normalization (FR-017)

**Decision**: LLM-based extraction via the parsing agent, with the schema storing `time_limit_minutes: int | None`.

**Rationale**: The LLM (Claude 3.5 Sonnet / GPT-4o) handles varied formats robustly ("3 hours", "90 min", "1.5 hours", "Time: 2hrs") with minimal prompt engineering. Instruct the parsing prompt to extract and normalize to minutes. If confidence is low, return None (FR-018 — no wrong guess).

**Alternatives considered**:
- **Regex-based extraction**: Brittle for varied natural language formats.
- **Hybrid regex + LLM**: More complex; LLM alone is sufficient for this bounded task.

### 6. Blueprint Duration Merging (FR-019)

**Decision**: Add `time_limit_minutes: int | None` to `BlueprintStructure` and instruct the blueprint prompt to use the **longest** stated duration from source papers.

**Rationale**: FR-019 explicitly requires the longest duration (conservative: never shorter than any real exam). The blueprint agent already merges data from multiple past papers; adding duration merging follows the same pattern.

### 7. Default Time Limit (FR-021)

**Decision**: 120 minutes, configurable via `Settings.exam_attempt_default_timeout_minutes`.

**Rationale**: Confirmed in spec clarifications. Hardcoding is acceptable but pydantic-settings makes it trivially configurable.
