# Data Model: Foundation Services

## Entity Changes

### User (course_core DB)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID (PK) | Existing |
| `clerk_id` | `VARCHAR` (unique, nullable) | **NEW** — Clerk user ID (`user_xxx`). Populated via webhook or lazy creation |
| `email` | `VARCHAR` (unique) | Existing — populated from Clerk user profile |
| `display_name` | `VARCHAR` | Existing |
| `is_active` | `BOOLEAN` (default true) | **NEW** — Soft-delete flag; set to false on `user.deleted` webhook |
| `preferences` | `JSONB` (default `{}`) | **NEW** — Notification preferences, theme, etc. |
| `created_at` | `TIMESTAMPTZ` | Existing (via TimestampMixin) |
| `updated_at` | `TIMESTAMPTZ` | Existing (via TimestampMixin) |

Migration: Add `clerk_id`, `is_active`, `preferences` columns via Alembic. Backfill `clerk_id` for existing users from Clerk webhook history (run once on deploy).

### Course (course_core DB)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID (PK) | Existing |
| `user_id` | UUID (FK → users.id) | Existing |
| `title` | `VARCHAR` | Existing |
| `code` | `VARCHAR` (nullable) | Existing |
| `instructor_name` | `VARCHAR` (nullable) | Existing |
| `instructor_id` | UUID (FK → instructors.id, nullable) | Existing |
| `archived_at` | `TIMESTAMPTZ` (nullable) | **NEW** — Non-null = soft-deleted/archived |
| `paper_count` | `INTEGER` (default 0) | **NEW** — Denormalized counter for dashboard (updated on upload completion) |
| `created_at` | `TIMESTAMPTZ` | Existing |
| `updated_at` | `TIMESTAMPTZ` | Existing |

### No changes to: Instructor, InstructorResolution, ExamBlueprint, Result, PastPaper, DocumentChunk

## Entity Relationships

```
User (1) ──< (N) Course
Course (1) ──< (N) PastPaper (identifier-only ref via course_id)
Course (1) ──< (N) ExamBlueprint (identifier-only ref via course_id)
Course (1) ──< (N) Result (identifier-only ref via course_id)
Course (N) ──> (1) Instructor (optional)
User (1) ──< (N) Result
```

### Local user ↔ Clerk identity bridge

```
Clerk User (external)
    │
    │ (user.created webhook / lazy creation on first API call)
    ▼
User (course_core DB)
    ├── clerk_id = "user_2abc..."  (Clerk primary key)
    ├── email = "user@example.com"
    └── display_name = "John Doe"
```

The `clerk_id` field bridges Clerk's external identity to our local user record. No session data is stored locally — Clerk handles all auth lifecycles. The local `User` record is purely for domain data (courses, results, preferences).

## Indexes

- `users.clerk_id` — unique index (for webhook and lazy creation lookup)
- `courses.user_id` — existing; used by dashboard list queries
- `courses.archived_at` — partial index `WHERE archived_at IS NULL` for active course queries
- `past_papers.course_id` — existing; used by paper listing
- `past_papers.content_hash` — new unique index for duplicate detection

## Validation Rules

| Entity | Field | Rule |
|--------|-------|------|
| User | `email` | Valid email format (pydantic `EmailStr`) |
| Course | `title` | Required, 1-200 chars |
| Course | `code` | Optional, max 20 chars |
| PastPaper | `file_type` | Must be `application/pdf` or `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| PastPaper | `file_size` | Must be < 50MB |
| User | `display_name` | Required, 1-100 chars |

## State Transitions

### User lifecycle

```
Clerk webhook "user.created" ──→ User created (active)
                                      │
Clerk webhook "user.updated" ──→ User fields updated
                                      │
Clerk webhook "user.deleted" ──→ User.is_active = false (soft-delete)
                                      │
First API call (clerk_id not found) ──→ User created lazily (active)
```

### PastPaper processing lifecycle

```
pending ──→ processing ──→ completed
                 │
                 └──→ failed
```

- `pending`: Initial state after upload + S3 storage
- `processing`: Background task running `ingest_course_file()`
- `completed`: Ingestion succeeded; blueprint created/updated
- `failed`: Ingestion failed; `failure_reason` populated

Per-course serialization: At most one paper in `processing` state per course at a time. Subsequent uploads for same course remain `pending` until the active processing completes.
