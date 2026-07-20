# Data Model: Phase 2 Agents

**Feature**: 003-phase2-agents | **Date**: 2026-07-20

Two layers: **persisted entities** (Alembic-migrated tables across the three per-service DBs) and **agent output schemas** (Pydantic, validated at pipeline boundaries — see contracts/agent-outputs.md for field-level contracts).

## Persisted entities

### instructors — NEW (course-core DB, migration `002_course_core`)

Unique professor identity (spec: Professor/Instructor).

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, `gen_random_uuid()` |
| normalized_name | TEXT | NOT NULL, **UNIQUE** |
| display_name | TEXT | NOT NULL |
| created_at / updated_at | TIMESTAMPTZ | server defaults (TimestampMixin) |

Rules:
- `normalized_name` is produced only by the shared normalization function (FR-005); never stored un-normalized.
- Exact-name tie with conflicting course context does NOT auto-merge — it lands in `instructor_resolutions` as needs-review (edge case).

### courses — MODIFIED (course-core DB, same migration)

| Change | Detail |
|---|---|
| `instructor_id` | UUID NULL, FK → instructors(id) ON DELETE SET NULL, indexed |

Existing `instructor_name` (raw user-entered text) is retained as alignment input. Each course links to **at most one** instructor (FR-006).

### instructor_resolutions — NEW (course-core DB, same migration)

Outcome of one alignment run (spec: Instructor Resolution).

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| course_id | UUID | NOT NULL, FK → courses CASCADE, indexed |
| raw_name | TEXT | NOT NULL |
| normalized_name | TEXT | NOT NULL |
| instructor_id | UUID | NULL, FK → instructors SET NULL (set when matched or created) |
| outcome | TEXT | NOT NULL, CHECK IN ('matched','created','needs_review') |
| confidence | NUMERIC(4,3) | NOT NULL (best-candidate similarity; 1.0 for created-new) |
| candidates | JSONB | NOT NULL DEFAULT `[]` — `[{instructor_id, normalized_name, score}]`, populated when needs_review |
| needs_review | BOOLEAN | NOT NULL DEFAULT false |
| created_at / updated_at | TIMESTAMPTZ | |

State rules (FR-007, clarified bands, thresholds configurable):
- score ≥ 0.90 → `matched`, course.instructor_id set.
- 0.70 ≤ score < 0.90 → `needs_review`, candidates recorded, **course.instructor_id NOT set** by this run.
- all scores < 0.70 → `created` (new instructor row), course.instructor_id set.
- Banding is enforced in pipeline code regardless of agent output.

### past_papers — MODIFIED (ingestion DB, migration `002_ingestion`)

| Change | Detail |
|---|---|
| `parsing_confidence` | NUMERIC(4,3) NULL — set on completed parse (FR-002) |
| `needs_review` | BOOLEAN NOT NULL DEFAULT false, indexed — low-confidence flag |

Lifecycle (existing `processing_status`, FR-004): `pending → processing → completed | failed(failure_reason)`.
- `needs_review=true` papers are **excluded** from blueprint extraction until cleared; a later extraction run incorporates them (clarified).
- Re-processing is idempotent: chunks for the paper are replaced in one transaction; no duplicate blueprint version unless the effective paper set changed.

### document_chunks — EXISTING (ingestion DB) — populated by this feature

No schema change. Written fields: `course_id`, `past_paper_id` (NULL for course material), `source_s3_key`, `content`, `position`, `hierarchy` (JSONB — `{kind, section, question_no, page|slide, marks}`), `embedding` Vector(1024) via `LLMClient.embed()`.

### exam_blueprints — EXISTING (course-core DB) — written by this feature

No schema change. Semantics under FR-009/FR-010:
- `structure` JSONB holds the serialized `BlueprintStructure` (sections, question types, marks distribution, topic-weight matrix, phrasing style, per-paper evidence, overall confidence).
- `source_past_paper_ids` = the paper set the version was extracted from.
- `version` computed as `max(version)+1` **inside** `pg_advisory_xact_lock('blueprint:'||course_id)`; versions immutable; unique (course_id, version) as backstop.

### generated_exams — NEW (exam-sim DB, migration `002_exam_sim`)

Spec: Generated Exam + Rubric (rubric stored with its exam).

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| course_id | UUID | NOT NULL, indexed (identifier-only, course-core ref) |
| blueprint_id | UUID | NOT NULL (identifier-only, course-core ref) |
| blueprint_version | INTEGER | NOT NULL |
| content | JSONB | NOT NULL — serialized `GeneratedExam` (sections → questions → marks, source-chunk refs) |
| rubric | JSONB | NOT NULL — per-question expected points, mark allocation, source refs (FR-013) |
| status | TEXT | NOT NULL, CHECK IN ('ready','needs_review'), indexed |
| needs_review_reasons | JSONB | NOT NULL DEFAULT `[]` — validation failures / ungroundable topics |
| created_at / updated_at | TIMESTAMPTZ | |

Rules: `needs_review` exams remain fully usable — takeable and gradable (clarified); flag persists for later review tooling (FR-015).

### results — EXISTING (course-core DB) — written by this feature

No schema change. Written under FR-016/FR-017: `question_scores` JSONB (per-question score + point-by-point feedback), `aggregate_score`, `max_score`, `weak_topics` JSONB. Exactly one per session via existing UNIQUE `exam_session_id` (pipeline upserts). Needs-review marker carried inside `question_scores` payload envelope (`{"needs_review": true, "reasons": [...]}` wrapper) — no schema change this phase, minimal diff.

## Agent output schemas (Pydantic, `exambrain_agents.schemas`)

| Schema | Produced by | Key fields |
|---|---|---|
| `ParsedDocument` | Parsing agent | `kind` (past_paper \| course_material), `document_type` (pdf_digital \| pdf_scanned \| pptx), `sections[]` (title, questions[] {number, text, marks, page} \| slides[] {index, text}), `confidence` [0,1] |
| `InstructorResolution` | Alignment agent | `raw_name`, `normalized_name`, `outcome`, `matched_instructor_id?`, `confidence`, `candidates[]` {instructor_id, normalized_name, score} |
| `BlueprintStructure` | Blueprint agent | `sections[]` {name, question_type, question_count, marks_each, total_marks}, `marks_distribution`, `topic_weights[]` {topic, weight}, `phrasing_style` (free-text characteristics), `evidence[]` {past_paper_id, observations}, `instructor_sightings[]` (resolved via alignment tool), `confidence` [0,1] |
| `GeneratedExam` | Generator agent | `sections[]` → `questions[]` {number, text, marks, topic, source_chunk_ids[]}, `total_marks`, `rubric` {entries[] {question_number, expected_points[], marks, source_chunk_ids[]}}, `ungrounded_topics[]` |
| `EvaluationOutput` | Evaluation agent | `question_scores[]` {question_number, score, max_marks, credited_points[], missing_points[], feedback}, `aggregate_score`, `max_score`, `weak_topics[]` |

Validation invariants (enforced in pipeline code, not just schema):
- GeneratedExam: section layout/types/counts/marks match blueprint; `total_marks` = Σ question marks = blueprint total; every question has ≥1 `source_chunk_ids` that exist for the course; rubric covers every question (FR-014, SC-004/005).
- EvaluationOutput: each score ∈ [0, max_marks]; `aggregate_score` = Σ scores; `max_score` = Σ max_marks; unanswered → 0 with "not attempted" feedback (FR-017).
- Any invariant failure → one corrective retry with the failure list appended → persist `needs_review` on second failure.
