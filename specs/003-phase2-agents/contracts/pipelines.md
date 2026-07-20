# Contract: Pipeline Entry Points

**Feature**: 003-phase2-agents | Library: `exambrain_agents.pipelines`

No HTTP endpoints this phase (FR-020). The public API is three async typed functions, importable from `exambrain_agents`. All raise from the shared typed error hierarchy; no partial writes on failure (FR-023).

## `ingest_course_file`

```python
async def ingest_course_file(
    course_id: UUID,
    s3_key: str,
    kind: Literal["past_paper", "course_material"],
    *,
    past_paper_id: UUID | None = None,   # required when kind == "past_paper"
) -> IngestResult
```

```python
class IngestResult(BaseModel):
    course_id: UUID
    past_paper_id: UUID | None
    status: Literal["completed", "failed"]
    parsing_confidence: float | None
    needs_review: bool
    chunks_written: int
    blueprint_version: int | None      # new version if extraction ran, else None
    failure_reason: str | None
```

Behavior:
- Past paper: lifecycle pending→processing→completed/failed persisted on `past_papers` (FR-004); on success runs alignment on the course's instructor name and (if not needs_review) blueprint extraction over the course's full eligible paper set under a per-course advisory lock (FR-009/010).
- Course material: parse → chunk → embed only; `blueprint_version` is None.
- Idempotent re-run: chunks replaced atomically per source; no duplicate blueprint version unless the eligible paper set changed.

Errors:
- Unsupported format → `UnsupportedFormatError` before any processing (edge case).
- Irrecoverable extraction → returns `status="failed"` with reason persisted; raises nothing (failure is a domain outcome).
- Infra/provider failures → `TransientLLMError` / `PermanentLLMError` / `ObjectNotFoundError` / `NotConfiguredError`; record left in re-runnable state, no partial content persisted.

## `generate_exam`

```python
async def generate_exam(course_id: UUID) -> GeneratedExamRecord
```

```python
class GeneratedExamRecord(BaseModel):
    id: UUID
    course_id: UUID
    blueprint_id: UUID
    blueprint_version: int
    exam: GeneratedExam                 # full content incl. rubric (schemas/generation.py)
    status: Literal["ready", "needs_review"]
    needs_review_reasons: list[str]
```

Behavior: loads latest blueprint (FR-011, no tuning knobs); generator agent retrieves grounding chunks itself via the read-only search tool (FR-012); structural + citation + rubric validation, one corrective retry, then persist flagged `needs_review` (FR-014); persisted to `generated_exams` with blueprint reference (FR-015). Needs-review exams are fully usable.

Errors:
- No blueprint → `BlueprintRequiredError`.
- No ingested course content → `ContentRequiredError` (US3 AS-5).
- Turn budget exceeded → `AgentTurnLimitError`; nothing persisted.

## `evaluate_submission`

```python
async def evaluate_submission(
    exam_session_id: UUID,
    generated_exam_id: UUID,
    answers: list[SubmittedAnswer],      # {question_number: int, text: str | None}
) -> EvaluationRecord
```

```python
class EvaluationRecord(BaseModel):
    exam_session_id: UUID
    question_scores: list[QuestionScore]
    aggregate_score: Decimal
    max_score: Decimal
    weak_topics: list[str]
    needs_review: bool
```

Behavior: grades strictly against the stored rubric; answer text is data, never instructions (edge case); arithmetic validation, one corrective retry, then persist flagged (FR-017); exactly one result per session — repeated calls upsert the same `exam_session_id` row (FR-016). Unanswered questions score 0 with "not attempted" feedback.

Errors: unknown exam/session → `ObjectNotFoundError`; turn budget → `AgentTurnLimitError`, no write.

## Cross-cutting contract (all entry points)

- Async-only; safe to call concurrently across courses; blueprint extraction serialized per course (advisory lock).
- Per-agent model resolved from `AGENT_<NAME>_MODEL` env, falling back to `LLM_MODEL` (FR-021).
- Logging: agent name, model, latency_ms, token counts, turn count — never document/prompt/answer text; tracing export disabled (FR-022).
- Fully testable with `exambrain_agents.testing.FakeModel` — no network, no credentials (FR-024); live tests behind `@pytest.mark.live_llm`.
