# Course Core API — OpenAPI Contracts

Base URL: `http://localhost:8001`
Auth: Bearer JWT (Clerk session token) via `Authorization` header

## Users

### `GET /v1/users/me` — Get current user profile

Auth: Required

Response `200`:
```json
{
  "id": "uuid",
  "clerk_id": "user_2abc123",
  "email": "user@example.com",
  "display_name": "John Doe",
  "preferences": {
    "notifications": true
  }
}
```

### `PATCH /v1/users/me` — Update current user profile

Auth: Required

Request:
```json
{
  "display_name": "Jane Doe",
  "preferences": {
    "notifications": false
  }
}
```

Response `200` — same shape as GET.

Errors: `401` (unauthorized), `422` (validation).

## Courses

### `POST /v1/courses` — Create a course

Auth: Required

Request:
```json
{
  "title": "CS301 - Data Structures",
  "code": "CS301",
  "instructor_name": "Dr. Smith"
}
```

Response `201`:
```json
{
  "id": "uuid",
  "title": "CS301 - Data Structures",
  "code": "CS301",
  "instructor_name": "Dr. Smith",
  "instructor_id": null,
  "paper_count": 0,
  "archived_at": null,
  "created_at": "2026-07-21T00:00:00Z"
}
```

### `GET /v1/courses` — List user's active courses

Auth: Required

Query: `?include_archived=false` (default: excludes archived)

Response `200`:
```json
{
  "courses": [
    {
      "id": "uuid",
      "title": "CS301 - Data Structures",
      "code": "CS301",
      "paper_count": 5,
      "latest_blueprint_version": 3,
      "has_blueprint": true,
      "created_at": "2026-07-21T00:00:00Z"
    }
  ]
}
```

### `GET /v1/courses/{course_id}` — Get course details

Auth: Required (must own course)

Response `200` — full course object with `blueprint_summary`, `paper_count`, `exam_count`.

### `PATCH /v1/courses/{course_id}` — Update course

Auth: Required (must own course)

Request:
```json
{
  "title": "CS301 - Advanced Data Structures",
  "instructor_name": "Prof. Smith"
}
```

### `DELETE /v1/courses/{course_id}` — Archive (soft-delete) a course

Auth: Required (must own course)

Response `204` — sets `archived_at` to current timestamp. Data preserved.

Errors: `401`, `403` (not owner), `404` (not found), `409` (already archived).

### `GET /v1/courses/{course_id}/blueprint` — Get latest blueprint

Auth: Required (must own course)

Response `200`:
```json
{
  "version": 3,
  "sections": [
    {
      "name": "Section A",
      "question_type": "multiple_choice",
      "marks": 20,
      "count": 10
    }
  ],
  "topic_weights": {
    "Arrays": 0.3,
    "Linked Lists": 0.25,
    "Trees": 0.25,
    "Sorting": 0.2
  },
  "confidence_score": 0.85,
  "created_at": "2026-07-21T00:00:00Z"
}
```

### `GET /v1/courses/{course_id}/blueprints` — Blueprint history

Auth: Required (must own course)

Response `200`:
```json
{
  "blueprints": [
    {"version": 3, "created_at": "...", "confidence_score": 0.85},
    {"version": 2, "created_at": "...", "confidence_score": 0.72},
    {"version": 1, "created_at": "...", "confidence_score": 0.60}
  ]
}
```

### `GET /v1/courses/{course_id}/papers` — List past papers

Auth: Required (must own course)

Response `200`:
```json
{
  "papers": [
    {
      "id": "uuid",
      "status": "completed",
      "file_type": "application/pdf",
      "file_name": "midterm-2025.pdf",
      "created_at": "2026-07-21T00:00:00Z",
      "processing_completed_at": "2026-07-21T00:05:00Z"
    }
  ]
}
```

## Dashboard

### `GET /v1/dashboard/summary` — Dashboard overview

Auth: Required

Response `200`:
```json
{
  "courses": [
    {
      "course_id": "uuid",
      "title": "CS301 - Data Structures",
      "paper_count": 5,
      "blueprint_version": 3,
      "has_blueprint": true,
      "completed_exams": 3,
      "average_score": 78.5
    }
  ]
}
```

Goal: < 2s for 10 courses / 100 results (FR-022).

### `GET /v1/courses/{course_id}/performance` — Per-course performance

Auth: Required (must own course)

Response `200`:
```json
{
  "aggregate_score": 78.5,
  "max_score": 100,
  "exam_count": 3,
  "topic_breakdown": [
    {"topic": "Arrays", "score": 85.0, "max": 100, "strength": "strong"},
    {"topic": "Trees", "score": 60.0, "max": 100, "strength": "weak"}
  ],
  "recent_exams": [
    {"id": "uuid", "score": 82.0, "date": "2026-07-20T00:00:00Z"}
  ]
}
```

## Webhooks (no auth — Svix-signed)

### `POST /v1/webhooks/clerk` — Clerk user sync webhook

Auth: Svix signature verification (no Bearer token)

Request (signed by Clerk):
```json
{
  "type": "user.created",
  "data": {
    "id": "user_2abc123",
    "email_addresses": [{"id": "email_1", "email_address": "user@example.com"}],
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

- `user.created` → upsert local User record
- `user.updated` → update local User record fields
- `user.deleted` → set `is_active = false` (soft-delete)

Response `200`:
```json
{"status": "ok"}
```

Errors: `401` (invalid Svix signature), `422` (unknown event type).

## Health & Metrics

### `GET /health` — Already exists. Returns:
```json
{"status": "ok", "service": "course-core", "version": "0.1.0"}
```

### `GET /metrics` — Already exists. Prometheus text format.

---

## Common Errors

All errors use this shape:
```json
{
  "error": "unauthorized",
  "reason": "SESSION_TOKEN_MISSING"
}
```

| HTTP | `error` | Common `reason` values |
|------|---------|------------------------|
| 401 | `unauthorized` | `SESSION_TOKEN_MISSING`, `TOKEN_EXPIRED`, `TOKEN_INVALID_SIGNATURE`, `TOKEN_INVALID_AUTHORIZED_PARTIES` |
| 403 | `forbidden` | `not_course_owner` |
| 404 | `not_found` | entity ID not found |
| 409 | `conflict` | `already_archived` |
| 422 | `validation_error` | pydantic validation failure |
| 413 | `file_too_large` | upload > 50MB |
| 415 | `unsupported_file_type` | not PDF or PPTX |
