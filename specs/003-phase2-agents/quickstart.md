# Quickstart: Phase 2 Agents

**Feature**: 003-phase2-agents | Library: `exambrain-agents`

## Install (uv workspace)

```bash
cd backend
uv sync                      # picks up new workspace member "agents"
sudo apt-get install -y tesseract-ocr   # OCR binary (dev/CI image installs this)
```

## Configure

All config via environment (`.env`); everything falls back to platform defaults:

```bash
# Platform-wide (existing)
LLM_PROVIDER=bedrock
LLM_MODEL=bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0
LLM_EMBEDDING_MODEL=bedrock/amazon.titan-embed-text-v2:0
DATABASE_URL=postgresql+asyncpg://exambrain:exambrain@localhost:5432/exambrain

# Per-agent overrides (new, all optional — default to LLM_MODEL)
AGENT_PARSING_MODEL=...
AGENT_ALIGNMENT_MODEL=...
AGENT_BLUEPRINT_MODEL=...
AGENT_GENERATOR_MODEL=...
AGENT_EVALUATION_MODEL=...

# Agent behavior (new, defaults shown)
AGENT_MAX_TURNS=10
ALIGNMENT_AUTO_MATCH_THRESHOLD=0.90
ALIGNMENT_REVIEW_THRESHOLD=0.70
PARSING_REVIEW_CONFIDENCE_THRESHOLD=0.60
```

## Migrate

```bash
cd backend/services/course-core        && uv run alembic upgrade head   # instructors, resolutions
cd ../ingestion-pipeline               && uv run alembic upgrade head   # parsing_confidence, needs_review
cd ../exam-simulation                  && uv run alembic upgrade head   # generated_exams
```

## Use the pipelines (library-only, SC-008)

```python
from exambrain_agents import ingest_course_file, generate_exam, evaluate_submission

# 1. Ingest a past paper already in S3
result = await ingest_course_file(
    course_id=course_id,
    s3_key="courses/{course_id}/papers/midterm-2024.pdf",
    kind="past_paper",
    past_paper_id=paper_id,
)
assert result.status == "completed"
print(result.blueprint_version)        # e.g. 1

# 2. Ingest lecture slides (no blueprint step)
await ingest_course_file(course_id, "courses/.../week1.pptx", kind="course_material")

# 3. Generate a blueprint-faithful mock exam
record = await generate_exam(course_id)
print(record.status)                   # "ready" | "needs_review" (still usable)

# 4. Grade a completed session
evaluation = await evaluate_submission(
    exam_session_id=session_id,
    generated_exam_id=record.id,
    answers=[{"question_number": "1", "text": "..."}],
)
print(evaluation.aggregate_score, evaluation.weak_topics)
```

## Test (no network, no credentials — SC-007)

```bash
cd backend
uv run pytest agents/tests            # FakeModel-scripted agent + pipeline tests
uv run pytest -m live_llm             # opt-in live provider smoke tests (needs creds)
uv run pytest -m migration            # needs local Postgres (docker compose up)
```

Scripting an agent in tests:

```python
from exambrain_agents.testing import FakeModel

model = FakeModel(outputs=[
    ToolCall("score_name_candidates", {...}),
    FinalOutput(InstructorResolution(outcome="matched", ...)),
])
resolution = await run_alignment(raw_name="Dr. A. Rahman", model=model)
```

## Verify quality gates

```bash
cd backend
uv run ruff check . && uv run black --check . && uv run mypy && uv run pytest --cov
```
