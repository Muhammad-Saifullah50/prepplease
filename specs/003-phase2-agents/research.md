# Research: Phase 2 Agents

**Feature**: 003-phase2-agents | **Date**: 2026-07-20

All Technical Context unknowns resolved below. Each entry: Decision / Rationale / Alternatives considered.

## R1. Agent framework: OpenAI Agents SDK with LiteLLM models

**Decision**: Use `openai-agents[litellm]` (≥0.2). Every agent is an `agents.Agent` whose `model` is a `LitellmModel` constructed from `Settings`, so all traffic still flows through LiteLLM → Bedrock per Constitution V. Tracing is globally disabled via `set_tracing_disabled(True)` at package init (FR-022).

**Rationale**: The SDK gives typed outputs (`output_type` with Pydantic), function tools, `max_turns` budgets, and agent composition out of the box; the `litellm` extra preserves the single-provider-abstraction rule without a custom Model adapter.

**Alternatives considered**:
- Raw `LLMClient.complete()` + hand-rolled tool loop — rejected: reimplements tool-calling, retries-on-schema, and turn budgeting the SDK already provides; spec explicitly names the Agents SDK.
- LangGraph / pydantic-ai — rejected: new framework surface, no requirement, larger dependency tree on a zero-cost RAM budget.

## R2. Blueprint→alignment handoff: agent-as-tool, not control transfer

**Decision**: Implement FR-008 with the SDK's *agent-as-tool* pattern: the alignment agent is exposed to the blueprint agent as a single callable tool (`resolve_instructor_sighting`). The blueprint agent invokes it when it encounters a printed instructor name; the alignment agent's typed `InstructorResolution` comes back as the tool result and is surfaced in the blueprint agent's output for the pipeline to persist.

**Rationale**: An SDK `handoff` transfers control and would abandon the blueprint extraction mid-run — the pipeline still needs the blueprint output. Agent-as-tool keeps the LLM-driven routing the spec asks for ("route that sighting to the alignment capability") while the surrounding code keeps a single typed result. Tools stay read-only (FR-019): the alignment tool returns a resolution; persistence happens in the pipeline.

**Alternatives considered**:
- SDK `handoffs=[...]` — rejected: control transfer loses the blueprint output; wrong shape for a sub-question.
- Pipeline-level detour (code detects sighting, calls alignment pipeline) — rejected: spec requires the *agent* to route the sighting (LLM-driven), not deterministic code.

## R3. Document parsing stack: pypdfium2 + pytesseract + python-pptx

**Decision**: Deterministic extraction tools (exposed to the parsing agent, and run before it as preprocessing):
- **Digital PDF text**: `pypdfium2` (`PdfDocument.get_page(...).get_textpage().get_text_range()`), per-page.
- **Scanned PDF OCR**: render pages to bitmaps with `pypdfium2` (no poppler system dep), OCR with `pytesseract` (Apache-2.0, local tesseract binary — added to the dev/CI Docker image). A page is routed to OCR when its extracted text is below a small character threshold.
- **PPTX**: `python-pptx`, per-slide text-frame walk.

**Rationale**: All are free, local, and pip-installable (tesseract binary is apt-installable — fits the Zero-Cost mandate; no cloud OCR spend). `pypdfium2` covers both text extraction and rasterization, minimizing dependencies. The parsing *agent* then structures raw per-page/per-slide text into hierarchy + confidence; the extraction itself is deterministic tooling per FR-018.

**Alternatives considered**:
- `pdfplumber`/`pypdf` — viable, but each covers only text; pypdfium2 also renders for OCR, so one dep does both.
- Bedrock multimodal OCR (send page images to Claude) — rejected for the default path: per-page vision calls are slow and costly against SC-001's 5-minute budget; local tesseract is free. Can be revisited if OCR quality proves insufficient.
- `unstructured` / `docling` — rejected: heavyweight (torch pulls), violates the ~2.4GB RAM footprint.

## R4. Name similarity: rapidfuzz over normalized names

**Decision**: Normalization (FR-005) is a pure function: lowercase, strip honorifics (`dr`, `prof`, `professor`, `mr`, `ms`, `mrs`, `engr`…), strip punctuation, collapse whitespace. Similarity is `rapidfuzz` `token_sort_ratio`/`WRatio` (scaled 0–1) between normalized names, computed by a read-only tool the alignment agent calls. Band thresholds come from settings: `ALIGNMENT_AUTO_MATCH_THRESHOLD=0.90`, `ALIGNMENT_REVIEW_THRESHOLD=0.70` (FR-007 defaults, configurable).

**Rationale**: Deterministic, fast, dependency-light, and testable without a model. The agent decides *using* the scores; banding itself is enforced again in pipeline validation so an LLM can never silently merge a band-b match (FR-007 hard rule enforced in code, not prompt).

**Alternatives considered**:
- Embedding-similarity on names — rejected: overkill, non-deterministic across model versions, costs tokens.
- `difflib.SequenceMatcher` — workable but weaker on token reordering ("Rahman, Abdul"); rapidfuzz is the standard tool.

## R5. Chunking + embedding: owned here, via existing gateway and schema

**Decision**: Chunking is deterministic pipeline code (not agent work): hierarchy-aware splitting of parsed sections/questions/slides into ~500-token target chunks with hierarchy metadata (`{kind, section, question_no, page/slide, marks}`) written to the existing `document_chunks` table. Embeddings via `LLMClient.embed()` (Titan V2, 1024 dims — `EMBEDDING_DIMENSIONS` already fixed). Idempotency (FR-004): chunks for a source are deleted-and-rewritten inside one transaction keyed by `past_paper_id`/`source_s3_key`, so re-runs never duplicate.

**Rationale**: The table, pgvector HNSW index, and embed call already exist from 002; this feature only populates them. Deterministic chunking keeps agent token spend on structuring, not splitting.

**Alternatives considered**:
- Agent-driven chunking — rejected: non-deterministic, expensive, no quality benefit for splitting.
- New embedding gateway — rejected: `LLMClient.embed()` exists and matches Constitution V.

## R6. Per-course serialization of blueprint extraction: Postgres advisory lock

**Decision**: Blueprint extraction acquires `pg_advisory_xact_lock(hashtextextended('blueprint:' || course_id, 0))` on the course-core connection for the duration of the extraction-persist transaction. A second concurrent run blocks, then re-extracts over the full current paper set when it acquires the lock (supersede semantics from the clarification). Version number is computed inside the lock (`max(version)+1`), making concurrent version writes impossible.

**Rationale**: No new infrastructure, transactional (lock cannot leak on crash — it is xact-scoped), and gives exactly the "serialized per course, later run supersedes" semantics. Redis SETNX locks need TTL/renewal logic and can expire mid-run.

**Alternatives considered**:
- Redis lock via existing `redis.py` — rejected: lease-expiry edge cases; extraction can exceed a safe TTL.
- Unique-constraint retry on `(course_id, version)` — prevents corruption but not wasted duplicate LLM runs; kept as a backstop (constraint already exists).

## R7. New tables and ownership

**Decision**:
- `instructors` → **course-core** DB (migration `002_course_core`): unique professor identities; `courses` gains nullable `instructor_id` (FK) alongside the existing raw `instructor_name`. `instructor_resolutions` (same migration) records each alignment outcome with needs-review flag and candidate list (JSONB).
- `generated_exams` → **exam-simulation** DB (migration `002_exam_sim`): exam content + rubric JSONB, status `ready|needs_review`, identifier-only `course_id`/`blueprint_id` + `blueprint_version`. `exam_sessions` untouched (minimal diff); Phase 3 wires sessions to exams.
- `past_papers` (ingestion DB) gains `parsing_confidence` and `needs_review` columns (migration `002_ingestion`) to satisfy FR-002 and the needs-review exclusion rule.

**Rationale**: Follows 002's ownership model (instructor identity lives with courses; exam artifacts live with the exam-sim service; parsing state lives with ingestion) and identifier-only cross-DB references.

**Alternatives considered**: Single "agents" DB — rejected: breaks the per-service DB partitioning established in 002; agents is a library, not a service, and owns no database.

## R8. Repository layer for agents library

**Decision**: The library ships its own repository classes (Constitution VII) under `exambrain_agents.repositories`, one per aggregate (papers/chunks, instructors/resolutions, blueprints, generated exams, results), built on `exambrain_shared.db.get_session_factory()` with explicit `database_url` per service DB. All persistence happens here, post-validation, never in tools (FR-019).

**Rationale**: No shared base repository exists yet; a thin per-aggregate async repository is the smallest compliant shape. Cross-DB writes are sequenced by pipelines (no distributed transactions; each step is atomic within its own DB, with status fields making partial progress visible and re-runnable).

**Alternatives considered**: Direct session usage in pipelines — rejected: Constitution VII. Two-phase commit across DBs — rejected: needless complexity; idempotent re-runs + status lifecycle cover failure recovery.

## R9. Testing without network: scripted FakeModel

**Decision**: Implement `FakeModel(Model)` — the SDK's model interface — returning a scripted sequence of `ModelResponse`s (tool calls and final typed outputs). Tests inject it via each agent's `model=` parameter. Live-provider tests carry a `live_llm` pytest marker (opt-in, skipped by default), mirroring the existing `migration` marker pattern. Deterministic tools (OCR, fuzzy match, similarity search) are tested directly with fixture files and fakes (`FakeS3Client`, fake session factories) per 002 conventions.

**Rationale**: FR-024/SC-007 require CI with no credentials or network. Scripting at the Model boundary exercises the real SDK tool-loop, schema validation, and max_turns logic — higher fidelity than mocking agents wholesale.

**Alternatives considered**: monkeypatching `litellm.acompletion` (002 style) — kept for `LLMClient.embed` tests, but for agents the SDK `Model` seam is cleaner and doesn't depend on LiteLLM internals.

## R10. Per-agent model configuration

**Decision**: Extend `Settings` with optional `AGENT_PARSING_MODEL`, `AGENT_ALIGNMENT_MODEL`, `AGENT_BLUEPRINT_MODEL`, `AGENT_GENERATOR_MODEL`, `AGENT_EVALUATION_MODEL`, plus `AGENT_MAX_TURNS` (default 10) and the two alignment thresholds (R4). A resolver `model_for(agent_name)` falls back to the platform-wide `LLM_MODEL` (FR-021).

**Rationale**: Keeps configuration in the single settings module (Constitution V), env-driven, zero behavior change for deployments that set only `LLM_MODEL`.

**Alternatives considered**: Per-agent config files / prompt-template YAML — rejected this phase: env vars satisfy FR-021 with less machinery; versioned prompt templates remain plain Python constants per agent package.

## R11. Failure mapping and needs_review semantics

**Decision**: Pipelines wrap `Runner.run(...)` in a single translation layer: SDK `MaxTurnsExceeded` → `AgentTurnLimitError`, output-schema mismatch → `AgentOutputError`, provider errors pass through as existing `TransientLLMError`/`PermanentLLMError` — all new errors join `exambrain_shared.errors` as `RuntimeError` subclasses. Validation failures (blueprint mismatch, arithmetic errors) trigger exactly one corrective retry (validation errors appended to the agent input), then persist with `needs_review=True` (FR-014/FR-017). Records flagged needs_review remain fully usable (clarified); needs-review *papers* are excluded from blueprint extraction until cleared (clarified).

**Rationale**: Matches FR-023 (typed errors at pipeline boundaries, no partial writes — each persist is one transaction) and the four clarification answers, with retry logic in deterministic code rather than agent loops.

**Alternatives considered**: SDK guardrails for validation — rejected: guardrail tripwires raise mid-run and complicate the retry-once-then-flag flow; explicit pipeline validation is simpler and testable.

## R12. Package layout: uv workspace member `exambrain-agents`

**Decision**: Promote `backend/agents/` to an installable src-layout package: `backend/agents/pyproject.toml` (name `exambrain-agents`, depends on `exambrain-shared`, `openai-agents[litellm]`, `pypdfium2`, `pytesseract`, `python-pptx`, `rapidfuzz`), code under `backend/agents/src/exambrain_agents/`. The five bare scaffold dirs (`agents/parsing` etc.) move under the package as subpackages. Root workspace `members` gains `"agents"`; ruff `src`, mypy `mypy_path`, and pytest `testpaths` are extended accordingly.

**Rationale**: FR-020 (installable library, typed entry points, no services) and consistency with the existing src-layout of `shared`. Coverage config already anticipates `agents`.

**Alternatives considered**: Leaving flat scaffold dirs as namespace packages — rejected: not installable as one library, breaks `import exambrain_agents` entry-point story.
