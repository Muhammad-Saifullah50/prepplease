# Quickstart: Exam Simulation Service

## Prerequisites

- Running PostgreSQL (exam_sim, course_core, ingestion DBs)
- Running Redis 7
- Generated mock exam (via generator agent, status: 'ready')
- Course blueprint (may or may not have time_limit)

## Development

```bash
# Start the service
cd backend/services/exam-simulation
uv run uvicorn exam_simulation.main:app --reload --port 8003

# Run tests
uv run pytest tests/ -v --cov=exam_simulation
```

## API Flow

1. **Start attempt** → `POST /api/v1/exam-attempts`
2. **Poll state** → `GET /api/v1/exam-attempts/{id}/state` (every ~5s)
3. **Save answers** → `PUT /api/v1/exam-attempts/{id}/answers` (debounced by client)
4. **Report focus loss** → `POST /api/v1/exam-attempts/{id}/focus-violations`
5. **Submit early** → `POST /api/v1/exam-attempts/{id}/finish`

Deadline auto-finish: runs in background every 10s.

## Migrations

```bash
cd backend/services/exam-simulation
alembic upgrade head
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EXAM_ATTEMPT_DEFAULT_TIMEOUT_MINUTES` | 120 | Default time limit when exam has none |
| `EXAM_FOCUS_VIOLATION_LIMIT` | 3 | Max focus violations before lockout |
| `EXAM_DEADLINE_POLL_INTERVAL_SECONDS` | 10 | Background task poll interval |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection string |
