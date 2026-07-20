# Implementation Plan: Phase 2 Agents

**Branch**: `003-phase2-agents` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-phase2-agents/spec.md`

## Summary

Deliver five OpenAI Agents SDK agents — multi-format parsing, instructor alignment, blueprint extraction, exam generation, and TA evaluation — as one installable library (`exambrain-agents`) under `backend/agents/`. Orchestration is code-driven: three typed pipeline entry points (ingest course file, generate exam, evaluate submission) sequence the agents, validate their Pydantic outputs, and persist through repositories. The single LLM-driven interaction is blueprint-extraction invoking alignment as a tool for instructor-name sightings. Deterministic machinery (pypdfium2/pytesseract/python-pptx extraction, rapidfuzz name matching, pgvector similarity search) is exposed to agents as read-only tools; chunking + Titan-V2 embedding of parsed content is owned here via the existing `LLMClient` gateway and `document_chunks` schema. New persistence: `instructors`, `instructor_resolutions` (course-core), `generated_exams` (exam-sim), and parsing-confidence/needs-review columns on `past_papers` (ingestion).

## Technical Context

**Language/Version**: Python 3.12+ (async throughout)
**Primary Dependencies**: `openai-agents[litellm]` ≥0.2 (agent framework, LiteLLM model path → Bedrock), `exambrain-shared` (settings, LLMClient, S3Adapter, db, errors, logging), `pypdfium2` (PDF text + rasterization), `pytesseract` (OCR; tesseract binary in dev/CI image), `python-pptx`, `rapidfuzz`, `pgvector`/SQLAlchemy (existing)
**Storage**: PostgreSQL + pgvector via existing per-service DBs — course-core (`instructors`, `instructor_resolutions`, `exam_blueprints`, `results`), ingestion (`past_papers`, `document_chunks` 1024-dim HNSW), exam-sim (`generated_exams`); S3 for source files; identifier-only cross-DB references
**Testing**: pytest (asyncio auto mode), scripted `FakeModel` at the SDK `Model` seam (no network), existing `FakeS3Client`/fakeredis patterns, `migration` marker for Alembic tests, new `live_llm` opt-in marker for provider tests; ≥80% coverage on `agents/`
**Target Platform**: Linux (WSL2 dev, K3s on OCI prod); library only — no service endpoints this phase
**Project Type**: Backend library within existing uv workspace (new member `agents`)
**Performance Goals**: 10-page paper ingested end-to-end (parse → chunk → embed → blueprint) in <5 min (SC-001); per-agent `max_turns` budget (default 10) so no run loops indefinitely
**Constraints**: Zero-cost infra (~2.4GB RAM total — no torch-class deps; local tesseract, no cloud OCR); all LLM traffic via LiteLLM (Constitution V); no raw prompt/response/document/answer text in logs, tracing export disabled (FR-022); tools read-only, persistence only in pipeline code post-validation (FR-019); no partial writes on failure (FR-023)
**Scale/Scope**: 5 agents, 3 pipeline entry points, 3 Alembic migrations (one per service DB), ~8 read-only tools, single-user-scale workloads this phase

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Spec-Driven Development | PASS | Spec clarified (4 sessions Q&A); this plan precedes tasks; PHR recorded; ADR candidates flagged below |
| II | Zero-Cost Infrastructure | PASS | All deps free/local (tesseract via apt); no new infra; embeddings/LLM through existing Bedrock free-tier-budgeted gateway |
| III | Agent Isolation & Contract-First | PASS (deviation noted) | Each agent: own subpackage, versioned prompt constants, typed Pydantic output, testable with FakeModel. **Deviation**: spec mandates code-driven pipelines + one agent-as-tool handoff, not Redis pub/sub — see Complexity Tracking |
| IV | Async-First | PASS | Agents SDK is async (`Runner.run`); repositories on asyncpg; S3 via aioboto3; OCR/extraction CPU work off-loaded with `asyncio.to_thread` |
| V | LLM Provider Abstraction | PASS | Agents use `LitellmModel` from settings; embeddings via existing `LLMClient.embed()`; per-agent overrides are env-config only, defaulting to `LLM_MODEL` |
| VI | TDD on Critical Paths | PASS | Blueprint extraction merge/versioning, exam assembly/validation, and grading arithmetic developed red-green-refactor; ≥80% coverage on `agents/` |
| VII | Repository Pattern & Data Integrity | PASS | New `exambrain_agents.repositories` layer; all schema changes via Alembic migrations 002_* per service |
| VIII | Code Quality | PASS | mypy strict + ruff + black extended to `agents/`; minimal diffs to existing services (only migrations + settings fields) |
| IX | Security by Default | PASS | No endpoints this phase; S3 via existing signed adapter; Pydantic validation at every agent output boundary |
| X | Observability | PASS | Structured logging of agent runs: agent name, model, latency, token usage, turn count — never content; tracing export disabled |

**Post-Phase-1 re-check**: PASS — design artifacts introduce no new violations; the Principle III transport deviation is justified in Complexity Tracking and is an ADR candidate.

## Project Structure

### Documentation (this feature)

```text
specs/003-phase2-agents/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── agent-outputs.md     # Typed output schemas for all five agents
│   ├── pipelines.md         # Library entry-point contracts
│   └── tools.md             # Read-only tool contracts
└── tasks.md             # Phase 2 output (/sp.tasks — NOT created by /sp.plan)
```

### Source Code (repository root)

```text
backend/
├── agents/                          # NEW uv workspace member: exambrain-agents
│   ├── pyproject.toml               # deps: exambrain-shared, openai-agents[litellm],
│   │                                #       pypdfium2, pytesseract, python-pptx, rapidfuzz
│   └── src/exambrain_agents/
│       ├── __init__.py              # set_tracing_disabled(True); public API re-exports
│       ├── config.py                # model_for(agent), thresholds, max_turns (reads Settings)
│       ├── errors.py                # AgentTurnLimitError, AgentOutputError, ParsingFailedError,
│       │                            #   ContentRequiredError (extend shared hierarchy)
│       ├── runner.py                # run_agent(): Runner.run wrapper — error translation,
│       │                            #   usage/latency logging, one corrective retry helper
│       ├── testing.py               # FakeModel (scripted Model impl) — exported for all tests
│       ├── schemas/                 # Pydantic output types (contract-first)
│       │   ├── parsing.py           # ParsedDocument, ParsedSection, ParsedQuestion, ParsedSlide
│       │   ├── alignment.py         # InstructorResolution, Candidate
│       │   ├── blueprint.py         # BlueprintStructure, TopicWeight, PaperEvidence, Sighting
│       │   ├── generation.py        # GeneratedExam, ExamQuestion, Rubric, RubricEntry
│       │   └── evaluation.py        # EvaluationOutput, QuestionScore
│       ├── tools/                   # Read-only function tools (FR-019)
│       │   ├── extraction.py        # extract_pdf_text, ocr_pdf_pages, extract_pptx_text
│       │   ├── matching.py          # normalize_name, score_name_candidates (rapidfuzz)
│       │   └── retrieval.py         # search_course_content (pgvector cosine, read-only)
│       ├── parsing/                 # agent.py (Agent def + prompt), each agent subpackage
│       ├── alignment/               #   follows the same shape: prompt.py + agent.py
│       ├── blueprint/               # exposes alignment agent as tool (FR-008)
│       ├── generator/
│       ├── evaluation/
│       ├── chunking.py              # hierarchy-aware deterministic chunker
│       ├── repositories/            # persistence layer (Constitution VII)
│       │   ├── ingestion.py         # papers lifecycle, chunk replace-on-rerun, embeddings
│       │   ├── course_core.py       # instructors, resolutions, blueprint versions (advisory lock)
│       │   └── exam_sim.py          # generated_exams, results
│       └── pipelines/               # typed entry points (FR-020)
│           ├── ingest.py            # ingest_course_file(...)
│           ├── generate.py          # generate_exam(...)
│           └── evaluate.py          # evaluate_submission(...)
│   └── tests/                       # library test suite (registered in root pytest testpaths)
│       ├── conftest.py              # FakeModel fixtures, fake session factories, fixture docs
│       ├── fixtures/                # tiny sample PDFs / scanned pages / PPTX
│       ├── test_tools_*.py          # deterministic tool tests (no model)
│       ├── test_agent_*.py          # per-agent tests via FakeModel
│       ├── test_pipeline_*.py       # end-to-end pipeline tests, fakes throughout
│       └── test_live_llm.py         # @pytest.mark.live_llm opt-in provider smoke tests
├── shared/src/exambrain_shared/
│   └── config.py                    # MODIFIED: per-agent model fields, alignment thresholds,
│                                    #           agent_max_turns
├── services/
│   ├── course-core/alembic/versions/
│   │   └── 20260720_002_instructors.py      # NEW: instructors, instructor_resolutions,
│   │                                        #      courses.instructor_id FK
│   ├── ingestion-pipeline/alembic/versions/
│   │   └── 20260720_002_parsing_state.py    # NEW: past_papers.parsing_confidence,
│   │                                        #      past_papers.needs_review
│   └── exam-simulation/alembic/versions/
│       └── 20260720_002_generated_exams.py  # NEW: generated_exams table
├── infra/docker/                    # MODIFIED: tesseract-ocr in dev/CI image
└── pyproject.toml                   # MODIFIED: workspace member "agents"; ruff src, mypy_path,
                                     #           pytest testpaths + live_llm marker
```

**Structure Decision**: `backend/agents/` becomes the fourth uv workspace member (`exambrain-agents`, src layout mirroring `shared`), replacing the five bare scaffold dirs with subpackages of one installable library. Existing services are touched only by additive Alembic migrations; `shared` only by additive settings fields. This satisfies FR-020 (installable library, no endpoints) with minimal diffs elsewhere.

## Architecture

### Pipeline flow (code-driven orchestration)

```text
ingest_course_file(course_id, s3_key, kind)          # kind: past_paper | course_material
  1. mark past_paper processing (if past_paper)                     [repo, own txn]
  2. download file (S3Adapter) → deterministic extraction
     (pypdfium2 text; OCR fallback per low-text page; pptx walk)    [to_thread]
  3. Parsing Agent → ParsedDocument (hierarchy, confidence)         [FakeModel-testable]
  4. validate; low confidence → needs_review=True on paper
  5. chunk (deterministic) → embed (LLMClient.embed) → replace
     chunks for this source in one txn                              [idempotent]
  6. if past_paper: Alignment Agent on course.instructor_name
     → persist resolution / instructor link                         [banding re-enforced in code]
  7. if past_paper & not needs_review: run blueprint extraction:
     advisory-lock(course) → gather ALL completed, non-review
     papers → Blueprint Agent (alignment-as-tool for sightings)
     → validate → write version max+1                               [serialized, supersede]
  8. mark paper completed | failed(reason)                          [no partial writes]

generate_exam(course_id) -> GeneratedExamRecord
  1. load latest blueprint; load course content presence
     (none → ContentRequiredError)                                  [FR-011, US3-AS5]
  2. Generator Agent with search_course_content tool
     (agent retrieves per-topic chunks itself)                      [FR-012]
  3. validate vs blueprint (sections, types, marks, rubric
     completeness, citations); fail → one corrective retry;
     fail again → persist status=needs_review                       [FR-014]
  4. persist generated_exams (content+rubric+blueprint ref)         [FR-015]

evaluate_submission(exam_session_id, answers) -> EvaluationRecord
  1. load exam + rubric for session
  2. Evaluation Agent (answers treated as data — rubric-strict)     [prompt-injection edge case]
  3. arithmetic validation; fail → one retry; fail → needs_review   [FR-017]
  4. persist exactly one result per session (upsert on unique
     exam_session_id)                                               [FR-016]
```

### Agent roster

| Agent | Output type | Tools | Model env override |
|---|---|---|---|
| Parsing | `ParsedDocument` | extract_pdf_text, ocr_pdf_pages, extract_pptx_text | `AGENT_PARSING_MODEL` |
| Alignment | `InstructorResolution` | normalize_name, score_name_candidates, list_known_instructors | `AGENT_ALIGNMENT_MODEL` |
| Blueprint | `BlueprintStructure` | (papers passed as input) + alignment-agent-as-tool | `AGENT_BLUEPRINT_MODEL` |
| Generator | `GeneratedExam` | search_course_content | `AGENT_GENERATOR_MODEL` |
| Evaluation | `EvaluationOutput` | — (exam, rubric, answers passed as input) | `AGENT_EVALUATION_MODEL` |

All agents: `output_type` enforced by the SDK, `max_turns` from `AGENT_MAX_TURNS`, model resolved by `config.model_for(name)` falling back to `LLM_MODEL` (FR-021). Every tool is read-only (FR-019); `list_known_instructors` and `search_course_content` read via repositories' query-only methods.

### Key decisions (from research.md)

- **R2**: FR-008 handoff = alignment **agent-as-tool** inside the blueprint agent (control never leaves; typed result returns to the pipeline).
- **R4/FR-007**: similarity bands computed deterministically (rapidfuzz) and **re-enforced in pipeline validation** — an LLM can never merge a 0.70–0.90 match.
- **R6/FR-010**: per-course serialization via `pg_advisory_xact_lock`; version computed inside the lock.
- **R11/FR-023**: single error-translation layer in `runner.py`; validation failures get exactly one corrective retry then `needs_review`.
- **R9/FR-024**: `FakeModel` implements the SDK `Model` interface — tests exercise the real tool loop with zero network.

### ADR candidates (proposed, not auto-created)

1. Code-driven pipelines + agent-as-tool handoff instead of Constitution III's event-driven (Redis pub/sub) agent communication.
2. OpenAI Agents SDK (with LitellmModel) as the agent framework atop the LiteLLM mandate.
3. Local tesseract OCR (vs. cloud/vision-model OCR) for scanned PDFs.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Constitution III prescribes event-driven agent communication (Redis pub/sub); this phase uses in-process code-driven pipelines with one agent-as-tool handoff | Spec assumption states "orchestration is code-driven"; FR-020 delivers a library with no services — there is no long-lived process to subscribe to a bus; typed in-process composition is testable offline (FR-024) | A Redis event bus between agents inside one library call adds serialization, delivery-failure, and ordering machinery with zero consumers this phase; Phase 3 services can layer eventing on top of these pipelines. Proposed as ADR #1 for user consent |
