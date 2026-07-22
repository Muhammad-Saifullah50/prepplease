# Quickstart: Foundation Services

## Prerequisites

- Python 3.12+ (`.python-version` at repo root)
- PostgreSQL 17 + pgvector (Docker Compose)
- Redis 7 (Docker Compose)
- Clerk account (free tier: https://clerk.com)

## Setup

### 1. Start infrastructure

```bash
cd backend
docker compose up -d postgres redis
```

### 2. Install dependencies

```bash
uv sync --frozen
```

### 3. Run migrations

```bash
# course-core database
uv run alembic -c services/course-core/alembic.ini upgrade head

# ingestion-pipeline database
uv run alembic -c services/ingestion-pipeline/alembic.ini upgrade head

# exam-simulation database (already migrated)
uv run alembic -c services/exam-simulation/alembic.ini upgrade head
```

### 4. Environment variables

Copy `.env.example` from each service and fill in:

```bash
cp services/course-core/.env.example services/course-core/.env
cp services/ingestion-pipeline/.env.example services/ingestion-pipeline/.env
```

Required additions to `.env`:

```env
# Clerk (from Clerk Dashboard: https://dashboard.clerk.com)
CLERK_SECRET_KEY=sk_test_...
CLERK_JWT_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
CLERK_WEBHOOK_SIGNING_SECRET=whsec_...
CLERK_AUTHORIZED_PARTIES=http://localhost:5173

# S3 (AWS free tier)
S3_BUCKET=exambrain-uploads
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

> **Getting CLERK_JWT_KEY**: In Clerk Dashboard → "Sessions" → "Manual JWT Verification" → download PEM. This enables networkless JWT verification.

### 5. Run services

```bash
# Terminal 1: course-core (port 8001)
uv run uvicorn course_core.main:app --reload --port 8001

# Terminal 2: ingestion-pipeline (port 8002)
uv run uvicorn ingestion_pipeline.main:app --reload --port 8002
```

Or via Docker Compose:

```bash
docker compose up -d course-core ingestion-pipeline
```

### 6. Verify

```bash
curl http://localhost:8001/health
# → {"status":"ok","service":"course-core","version":"0.1.0"}

curl http://localhost:8002/health
# → {"status":"ok","service":"ingestion-pipeline","version":"0.1.0"}
```

## Testing

```bash
# All tests
uv run pytest

# Service-specific
uv run pytest services/course-core/tests/
uv run pytest services/ingestion-pipeline/tests/

# With coverage
uv run pytest --cov=course_core --cov=ingestion_pipeline
```

## Clerk Webhook Setup

1. In Clerk Dashboard → "Webhooks" → "Add Endpoint"
2. Endpoint URL: `https://your-domain.com/v1/webhooks/clerk` (or use ngrok for local: `ngrok http 8001`)
3. Events: Select `user.created`, `user.updated`, `user.deleted`
4. Copy the signing secret into `CLERK_WEBHOOK_SIGNING_SECRET`
5. Verify: `curl -X POST http://localhost:8001/v1/webhooks/clerk -H 'svix-id: test' -H 'svix-timestamp: ...' -H 'svix-signature: ...'`

## API Flow (end-to-end)

```bash
# 1. Get session token from Clerk frontend (or test token from Clerk Dashboard)
TOKEN="your_clerk_session_token"

# 2. Get profile (lazy creates User if new)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/v1/users/me

# 3. Create a course
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"CS301 - Data Structures","code":"CS301"}' \
  http://localhost:8001/v1/courses

# 4. Upload a past paper (to ingestion-pipeline)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@midterm-2025.pdf" \
  http://localhost:8002/v1/courses/{course_id}/upload

# 5. Poll status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/v1/papers/{paper_id}/status

# 6. Check dashboard
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/v1/dashboard/summary
```
