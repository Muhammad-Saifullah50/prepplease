# Quickstart: Foundation Adapters

**Feature**: 002-foundation-adapters

## Prerequisites

- Docker + docker-compose, `uv`, Python 3.12+
- Optional (for live cloud): AWS credentials with Bedrock + S3 access in `.env` (gitignored)

## 1. Bring up the local stack

```bash
cd backend
uv sync
docker compose -f infra/docker/docker-compose.yml up -d postgres redis
```

Postgres starts with the three per-service databases (`course_core`, `ingestion`, `exam_sim`) and the pgvector extension pre-enabled.

## 2. Run migrations (per service — FR-004)

```bash
cd services/course-core       && uv run alembic upgrade head && cd ../..
cd services/ingestion-pipeline && uv run alembic upgrade head && cd ../..
cd services/exam-simulation   && uv run alembic upgrade head && cd ../..
```

Each service's Alembic tree targets its own database (via `DATABASE_URL` or the localhost default in its `env.py`) and only creates its own tables. Rollback: `uv run alembic downgrade base`.

## 3. Verify the schema (SC-001, SC-002)

```bash
docker exec -it $(docker ps -qf name=postgres) psql -U exambrain -d ingestion \
  -c "\d document_chunks"
# embedding column: vector(1024); HNSW index present
```

Similarity query smoke test (after inserting chunks):

```sql
SELECT id, content FROM document_chunks
ORDER BY embedding <=> '[...1024 floats...]' LIMIT 5;
```

## 4. Use the adapters

```python
from exambrain_shared.llm import LLMClient
from exambrain_shared.redis import SessionStore, RateLimiter
from exambrain_shared.s3 import S3Adapter
from exambrain_shared.iam import CredentialManager

# LLM (needs LLM_PROVIDER=bedrock, LLM_MODEL, LLM_EMBEDDING_MODEL, AWS creds)
llm = LLMClient()
result = await llm.complete("Summarize photosynthesis in one line.")
print(result.text, result.prompt_tokens, result.completion_tokens)
print(llm.usage)                      # cumulative per-model counters

vector = await llm.embed("chunk text")   # len == 1024 (Titan V2)

# Sessions & rate limits (needs REDIS_URL)
store = SessionStore()
await store.set_session("exam-123", {"timer": 1800, "violations": 0}, ttl_seconds=1800)
state = await store.get_session("exam-123")     # None once expired

limiter = RateLimiter()
verdict = await limiter.check("user-42:generate", threshold=10, window_seconds=60)

# Files (needs AWS creds + S3_BUCKET)
s3 = S3Adapter()
await s3.upload("courses/abc/paper.pdf", open("paper.pdf", "rb"))
objects = await s3.list_by_prefix("courses/abc/")

# Credential validation (read-only)
creds = CredentialManager()
report = await creds.validate_permissions()
for p in report.permissions:
    print(p.action, p.state)          # allowed / denied / cannot_verify
```

With **zero configuration**, every import and construction still succeeds; each operation above raises `NotConfiguredError` at call time (scaffold contract preserved).

## 5. Run tests

```bash
cd backend
uv run pytest                          # hermetic: providers simulated
uv run pytest -m migration             # requires the docker Postgres running
uv run pytest --cov --cov-fail-under=80
```

## New environment variables

| Variable | Purpose | Default |
|---|---|---|
| `LLM_EMBEDDING_MODEL` | e.g. `bedrock/amazon.titan-embed-text-v2:0` | unset |
| `LLM_MAX_RETRIES` | transient-retry attempt bound | 3 |
| `LLM_RETRY_DEADLINE_SECONDS` | total retry deadline | 60 |
| `S3_ENDPOINT_URL` | override for future MinIO | unset |
| `RATE_LIMIT_DEFAULT_THRESHOLD` / `RATE_LIMIT_DEFAULT_WINDOW_SECONDS` | limiter defaults | unset |
