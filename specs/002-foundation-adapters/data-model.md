# Data Model: Foundation Adapters

**Feature**: 002-foundation-adapters | **Date**: 2026-07-20

All tables carry `id UUID PK (default gen_random_uuid())`, `created_at timestamptz NOT NULL default now()`, `updated_at timestamptz NOT NULL default now()` (onupdate). Cross-database references are identifier-only (`UUID`, no FK). Within a database, FKs are enforced.

## Database: `course_core` (course-core service)

### users

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| email | text | NOT NULL, UNIQUE |
| display_name | text | NOT NULL |
| created_at / updated_at | timestamptz | NOT NULL |

### courses

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | NOT NULL, FK → users.id ON DELETE CASCADE |
| title | text | NOT NULL |
| code | text | NULL (e.g. "CS-301") |
| instructor_name | text | NULL |
| created_at / updated_at | timestamptz | NOT NULL |

Index: `(user_id)`.

### exam_blueprints

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| course_id | UUID | NOT NULL, FK → courses.id ON DELETE CASCADE |
| version | integer | NOT NULL, default 1 |
| structure | JSONB | NOT NULL — sections, question types, marks distribution, topic weights (queryable, FR-005) |
| source_past_paper_ids | JSONB | NOT NULL default `[]` — identifier-only refs into ingestion DB |
| created_at / updated_at | timestamptz | NOT NULL |

Constraint: UNIQUE `(course_id, version)` — versioned per course.

### results

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | NOT NULL, FK → users.id ON DELETE CASCADE |
| course_id | UUID | NOT NULL, FK → courses.id ON DELETE CASCADE |
| exam_session_id | UUID | NOT NULL, UNIQUE — identifier-only ref into exam_sim DB |
| question_scores | JSONB | NOT NULL — per-question scores + feedback |
| aggregate_score | numeric(6,2) | NOT NULL |
| max_score | numeric(6,2) | NOT NULL |
| weak_topics | JSONB | NOT NULL default `[]` — weak-topic index contribution |
| created_at / updated_at | timestamptz | NOT NULL |

Indexes: `(user_id)`, `(course_id)`.

## Database: `ingestion` (ingestion-pipeline service)

### past_papers

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| course_id | UUID | NOT NULL — identifier-only ref into course_core DB |
| s3_key | text | NOT NULL — source file reference |
| academic_term | text | NULL (e.g. "Fall 2025") |
| year | integer | NULL |
| processing_status | text | NOT NULL, CHECK IN ('pending','processing','completed','failed'), default 'pending' |
| failure_reason | text | NULL — populated only when status='failed' |
| created_at / updated_at | timestamptz | NOT NULL |

Index: `(course_id)`, `(processing_status)`.

**State transitions** (linear; `failed` terminal until reprocessing re-triggers → `pending`):

```text
pending → processing → completed
                     → failed  → (re-trigger) → pending
```

### document_chunks

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| course_id | UUID | NOT NULL — identifier-only ref |
| past_paper_id | UUID | NULL, FK → past_papers.id ON DELETE CASCADE (NULL for course-material chunks) |
| source_s3_key | text | NOT NULL |
| content | text | NOT NULL |
| position | integer | NOT NULL — ordering within source |
| hierarchy | JSONB | NOT NULL default `{}` — section/heading metadata |
| embedding | vector(1024) | NULL until embedded — Titan V2, dimension-enforced at write |
| created_at / updated_at | timestamptz | NOT NULL |

Indexes: `(course_id)`, `(past_paper_id)`, HNSW on `embedding` with `vector_cosine_ops`.
Migration prerequisite: `CREATE EXTENSION IF NOT EXISTS vector` (idempotent).

## Database: `exam_sim` (exam-simulation service)

### exam_sessions

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | NOT NULL — identifier-only ref |
| course_id | UUID | NOT NULL — identifier-only ref |
| blueprint_id | UUID | NULL — identifier-only ref |
| exam_content | JSONB | NOT NULL — generated exam paper reference/content |
| status | text | NOT NULL, CHECK IN ('active','submitted','locked_out','expired'), default 'active' |
| started_at | timestamptz | NOT NULL |
| ended_at | timestamptz | NULL |
| focus_violations | integer | NOT NULL default 0 |
| created_at / updated_at | timestamptz | NOT NULL |

Indexes: `(user_id)`, `(status)`.

Note: in-flight session real-time state (timer, auto-save buffer) is authoritative in Redis (see contracts/session-store.md); this table is the durable record.

## Non-database structures

### UsageRecord (in-memory only — FR-009, no table)

| Field | Type |
|---|---|
| model | str |
| prompt_tokens | int |
| completion_tokens | int |
| timestamp | float (monotonic/epoch) |

Aggregated by `UsageTracker` into per-model cumulative counters `{model: {prompt_tokens, completion_tokens, calls}}`; emitted per call to structured logs.

### Redis key conventions

| Pattern | Value | TTL |
|---|---|---|
| `session:{session_id}` | JSON session state | caller-supplied (e.g. 30 min) |
| `ratelimit:{scope}:{window_start}` | integer counter | window length |

## ORM ↔ service mapping (FR-004)

| Model module | Tables | Alembic tree | Database |
|---|---|---|---|
| `exambrain_shared.models.course_core` | users, courses, exam_blueprints, results | `services/course-core/alembic` | course_core |
| `exambrain_shared.models.ingestion` | past_papers, document_chunks | `services/ingestion-pipeline/alembic` | ingestion |
| `exambrain_shared.models.exam_sim` | exam_sessions | `services/exam-simulation/alembic` | exam_sim |

Each `env.py` filters `Base.metadata` with `include_object` on the table's `info={"service": ...}` tag so per-service migrations never touch another service's tables.
