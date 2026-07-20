# Contract: Agent Tools

**Feature**: 003-phase2-agents | Module: `exambrain_agents.tools`

All tools are **read-only** with respect to system state (FR-019): they extract, compute, or query — they never insert, update, or delete. Persistence happens exclusively in pipeline code after output validation. Deterministic tools are plain functions, individually testable without any model (FR-018/FR-024).

## Extraction tools (parsing agent)

### `extract_pdf_text(pdf_bytes) -> list[PageText]`
pypdfium2 per-page text extraction. `PageText = {page: int, text: str, char_count: int}`. Raises `ParsingFailedError` on encrypted/corrupt/zero-page documents (edge case → paper marked failed by the pipeline).

### `ocr_pdf_pages(pdf_bytes, pages) -> list[PageText]`
Renders the given pages via pypdfium2 and OCRs with pytesseract (runs in `asyncio.to_thread`). Returns per-page text plus mean OCR confidence. Routing rule (pipeline preprocessing): a page whose extracted `char_count` falls below the digital-text threshold is sent to OCR; a document where most pages need OCR is classified `pdf_scanned`.

### `extract_pptx_text(pptx_bytes) -> list[SlideText]`
python-pptx walk of slides → `{slide: int, title: str | None, text: str}`.

Note: the pipeline runs extraction as preprocessing and hands raw page/slide text to the parsing agent as input; the same functions are also registered as tools so the agent can re-extract specific pages when structuring is ambiguous. Either path is read-only.

## Matching tools (alignment agent)

### `normalize_name(raw: str) -> str`
Pure function: lowercase, strip honorifics/titles, strip punctuation, collapse whitespace (FR-005). Shared by tools, pipeline, and repositories — single definition.

### `list_known_instructors(course_context: UUID | None = None) -> list[KnownInstructor]`
Read-only repository query: `{instructor_id, normalized_name, display_name}` for candidate scoring.

### `score_name_candidates(name: str, candidates: list[str]) -> list[ScoredCandidate]`
rapidfuzz similarity of the normalized name against each candidate, `{candidate, score ∈ [0,1]}` sorted desc. Deterministic; the banding decision (FR-007) uses these scores and is re-enforced in pipeline validation.

## Retrieval tools (generator agent)

### `search_course_content(course_id: UUID, query: str, limit: int = 8) -> list[ContentChunk]`
Embeds `query` via `LLMClient.embed()` and runs pgvector cosine search over `document_chunks` scoped to the course (HNSW index). Returns `{chunk_id, content, hierarchy, similarity}`. The generator agent calls this per topic to ground questions (FR-012); returned `chunk_id`s become the questions' `source_chunk_ids`.

## Agent-as-tool (blueprint agent)

### `resolve_instructor_sighting(raw_name: str) -> InstructorResolution`
The alignment agent wrapped via `Agent.as_tool(...)` (FR-008). From the blueprint agent's perspective it is an ordinary tool; internally it runs the full alignment agent (with its own tools above) and returns its typed output. Read-only: the resolution is only persisted later by the pipeline, with banding re-enforced.

## Tool registration matrix

| Tool | Parsing | Alignment | Blueprint | Generator | Evaluation |
|---|---|---|---|---|---|
| extract_pdf_text / ocr_pdf_pages / extract_pptx_text | ✅ | | | | |
| normalize_name / list_known_instructors / score_name_candidates | | ✅ | | | |
| resolve_instructor_sighting (alignment-as-tool) | | | ✅ | | |
| search_course_content | | | | ✅ | |
| *(none — inputs passed directly)* | | | | | ✅ |
