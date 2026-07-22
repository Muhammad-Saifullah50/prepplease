# Data Model: Exam Simulation Service

## Entity: ExamAttempt (replaces/extends ExamSession)

The existing `exam_sessions` table lacks deadline, answers, and finished-by discriminator. We add fields and keep backward compatibility via migration.

### Fields

| Field | Type | Nullable | Default | Description |
|-------|------|----------|---------|-------------|
| id | UUID (PK) | No | gen_random_uuid() | |
| user_id | UUID | No | — | Identifier-only ref to course_core.users |
| course_id | UUID | No | — | Identifier-only ref to course_core.courses |
| blueprint_id | UUID | Yes | — | Identifier-only ref to course_core.exam_blueprints |
| generated_exam_id | UUID | No | — | Identifier-only ref to exam_sim.generated_exams |
| status | Enum | No | 'active' | One of: active, submitted, expired, locked_out |
| started_at | Timestamptz | No | now() | When the attempt began |
| deadline | Timestamptz | Yes | — | Calculated: started_at + time_limit |
| ended_at | Timestamptz | Yes | — | When the attempt finished (any status) |
| finished_by | Enum | Yes | — | One of: manual, deadline, lockout. Null while active. |
| time_limit_minutes | Int | No | — | The authoritative time limit for this attempt |
| answers | JSONB | No | '{}' | Map of question_number → answer_text |
| focus_violations | Int | No | 0 | Running count of focus-loss events |
| created_at | Timestamptz | No | now() | From TimestampMixin |
| updated_at | Timestamptz | No | now() | From TimestampMixin |

### Status Transitions

```
                  ┌─────────┐
                  │  active  │
                  └────┬────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    manual submit  deadline hit  lockout
         │             │             │
         ▼             ▼             ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ submitted │ │ expired  │ │ locked   │
   └──────────┘ └──────────┘ └─────out──┘
         │             │             │
         └─────────────┼─────────────┘
                       │
                 trigger grading
```

- All terminal states are final and immutable.
- No transition from any terminal state back to active.
- Concurrent finish requests: first writer wins (FOR UPDATE lock).

### Validation Rules

1. `deadline` must be `started_at + time_limit_minutes` (set on creation, immutable afterwards).
2. `finished_by` must be null when `status = 'active'`, non-null otherwise.
3. `ended_at` must be null when `status = 'active'`, non-null otherwise.
4. `answers` is a JSON object of `string → string` (question_number → answer_text).
5. `focus_violations` ≥ 0; lockout threshold from settings (default 3).

---

## Entity: ExamBlueprint (modified)

Add field to existing model in `course_core` service.

| Field | Type | Nullable | Default | Description |
|-------|------|----------|---------|-------------|
| time_limit_minutes | Int | Yes | — | Longest stated time limit from source papers |

- Null means "unknown" — fall back to default 120 min on attempt start.

---

## Entity: PastPaper (modified)

Add field to existing model in `ingestion` service.

| Field | Type | Nullable | Default | Description |
|-------|------|----------|---------|-------------|
| time_limit_minutes | Int | Yes | — | Extracted time limit from the paper, normalized to minutes |

- Null means "no confidently recognizable time limit" (FR-018).

---

## Entity: GeneratedExamRow (modified)

Add field to existing model in `exam_sim` service.

| Field | Type | Nullable | Default | Description |
|-------|------|----------|---------|-------------|
| time_limit_minutes | Int | Yes | — | Time limit from the source blueprint |

- Null means "unknown" — a new attempt gets the default 120 min.

---

## Redis Cache Schema

For live attempt state polling:

**Key**: `attempt:{id}:state`
**Type**: Redis Hash
**TTL**: Remaining attempt time (seconds from now to deadline)
**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| status | String | Current status |
| remaining_seconds | Int | Computed at cache write |
| focus_violations | Int | Running count |
| answers | JSON | Current answers object |
| deadline | ISO8601 | Server-side deadline |

**Cache Strategy**:
- **Write-through**: On answer save, update PG + refresh cache.
- **Read-through**: On poll, read cache; on miss, read PG and repopulate cache.
- **Invalidate**: On finish/lockout/expiry, delete cache key.
