"""``ingest_course_file`` pipeline (contracts/pipelines.md, US1).

Code-driven orchestration: deterministic extraction → parsing agent →
chunk + embed → (past papers) blueprint extraction over the full eligible
paper set under the per-course advisory lock. All persistence happens here
after validation (FR-019); dependencies are injectable for offline tests
(FR-024).
"""

import json
from typing import Any, Literal
from uuid import UUID

import structlog
from agents.models.interface import Model
from pydantic import BaseModel

from exambrain_agents import config
from exambrain_agents.alignment.agent import (
    alignment_input,
    build_alignment_agent,
    enforce_banding,
    score_stored_instructors,
)
from exambrain_agents.blueprint.agent import (
    blueprint_input,
    build_blueprint_agent,
    validate_blueprint,
)
from exambrain_agents.chunking import chunk_document
from exambrain_agents.errors import ParsingFailedError, UnsupportedFormatError
from exambrain_agents.parsing.agent import build_parsing_agent, parsing_input
from exambrain_agents.runner import run_agent, run_agent_with_corrective_retry
from exambrain_agents.schemas.alignment import InstructorResolution
from exambrain_agents.schemas.blueprint import BlueprintStructure
from exambrain_agents.schemas.parsing import ParsedDocument
from exambrain_agents.tools.extraction import (
    classify_pages,
    extract_pdf_text,
    extract_pptx_text,
    ocr_pdf_pages,
)
from exambrain_agents.tools.matching import normalize_name

logger = structlog.get_logger(__name__)


class IngestResult(BaseModel):
    """Outcome of one ingest run (contracts/pipelines.md)."""

    course_id: UUID
    past_paper_id: UUID | None
    status: Literal["completed", "failed"]
    parsing_confidence: float | None
    needs_review: bool
    chunks_written: int
    blueprint_version: int | None  # new version if extraction ran, else None
    failure_reason: str | None


def _default_s3() -> Any:
    from exambrain_shared.s3 import S3Adapter

    return S3Adapter()


def _default_embedder() -> Any:
    from exambrain_shared.llm import LLMClient

    return LLMClient()


def _default_ingestion_repo() -> Any:
    from exambrain_agents.repositories.ingestion import IngestionRepository

    return IngestionRepository()


def _default_course_repo() -> Any:
    from exambrain_agents.repositories.course_core import CourseCoreRepository

    return CourseCoreRepository()


async def ingest_course_file(
    course_id: UUID,
    s3_key: str,
    kind: Literal["past_paper", "course_material"],
    *,
    past_paper_id: UUID | None = None,  # required when kind == "past_paper"
    s3: Any = None,
    embedder: Any = None,
    ingestion_repo: Any = None,
    course_repo: Any = None,
    parsing_model: Model | None = None,
    blueprint_model: Model | None = None,
    alignment_model: Model | None = None,
) -> IngestResult:
    """Ingest one stored course file end-to-end (FR-001..FR-004, FR-009/010)."""
    if kind == "past_paper" and past_paper_id is None:
        raise ValueError("past_paper_id is required when kind == 'past_paper'")

    # Format gate before any processing (edge case).
    suffix = s3_key.rsplit(".", 1)[-1].lower() if "." in s3_key else ""
    if suffix not in ("pdf", "pptx"):
        raise UnsupportedFormatError(s3_key)

    s3 = s3 or _default_s3()
    embedder = embedder or _default_embedder()
    ingestion_repo = ingestion_repo or _default_ingestion_repo()
    course_repo = course_repo or _default_course_repo()

    if kind == "past_paper":
        await ingestion_repo.mark_processing(past_paper_id)

    try:
        data = await s3.download_bytes(s3_key)
        document = await _parse(data, suffix, kind, parsing_model)
    except ParsingFailedError as exc:
        # Irrecoverable extraction is a domain outcome, not an exception
        # to the caller (contracts): mark failed, persist nothing else.
        if kind == "past_paper":
            await ingestion_repo.mark_failed(past_paper_id, exc.reason)
        return IngestResult(
            course_id=course_id,
            past_paper_id=past_paper_id,
            status="failed",
            parsing_confidence=None,
            needs_review=False,
            chunks_written=0,
            blueprint_version=None,
            failure_reason=exc.reason,
        )

    needs_review = document.confidence < config.parsing_review_confidence_threshold()

    # Chunk + embed + persist atomically per source (FR-003, idempotent).
    chunks = chunk_document(document)
    for chunk in chunks:
        chunk["embedding"] = await embedder.embed(chunk["content"])
    chunks_written = await ingestion_repo.replace_chunks(
        course_id=course_id,
        source_s3_key=s3_key,
        past_paper_id=past_paper_id,
        chunks=chunks,
    )

    blueprint_version: int | None = None
    if kind == "past_paper":
        await ingestion_repo.mark_completed(
            past_paper_id,
            parsing_confidence=document.confidence,
            needs_review=needs_review,
            time_limit_minutes=document.time_limit_minutes,
        )
        # US2: resolve the course's recorded instructor name (FR-005..007).
        await _align_course_instructor(course_id, course_repo, alignment_model)
        if not needs_review:
            blueprint_version = await _extract_blueprint(
                course_id,
                ingestion_repo,
                course_repo,
                blueprint_model,
                alignment_model,
                trigger_paper_id=past_paper_id,
            )

    return IngestResult(
        course_id=course_id,
        past_paper_id=past_paper_id,
        status="completed",
        parsing_confidence=document.confidence,
        needs_review=needs_review,
        chunks_written=chunks_written,
        blueprint_version=blueprint_version,
        failure_reason=None,
    )


async def _parse(
    data: bytes,
    suffix: str,
    kind: str,
    parsing_model: Model | None,
) -> ParsedDocument:
    """Deterministic extraction preprocessing + parsing agent (FR-001)."""
    if suffix == "pdf":
        pages = extract_pdf_text(data)
        document_type, ocr_page_numbers = classify_pages(pages)
        if ocr_page_numbers:
            ocr_results = {
                p.page: p for p in await ocr_pdf_pages(data, ocr_page_numbers)
            }
            pages = [ocr_results.get(p.page, p) for p in pages]
        agent = build_parsing_agent(pdf_bytes=data)
        agent_input = parsing_input(kind, document_type, pages=pages)
    else:
        slides = extract_pptx_text(data)
        if not slides:
            raise ParsingFailedError("PPTX has no slides")
        agent = build_parsing_agent(pptx_bytes=data)
        agent_input = parsing_input(kind, "pptx", slides=slides)
    result: ParsedDocument = await run_agent(agent, agent_input, model=parsing_model)
    return result


async def _extract_blueprint(
    course_id: UUID,
    ingestion_repo: Any,
    course_repo: Any,
    blueprint_model: Model | None,
    alignment_model: Model | None,
    *,
    trigger_paper_id: UUID | None,
) -> int | None:
    """Run blueprint extraction over the full eligible paper set (FR-009).

    Skips (returns None) when the eligible set is unchanged from the
    latest version — idempotent re-runs create no duplicate versions.
    """
    papers = await ingestion_repo.eligible_papers(course_id)
    if not papers:
        return None

    paper_ids = sorted(p["id"] for p in papers)
    latest = await course_repo.latest_blueprint(course_id)
    if latest is not None and sorted(latest["source_past_paper_ids"]) == sorted(
        str(p) for p in paper_ids
    ):
        return None  # paper set unchanged → no duplicate version

    paper_texts: list[tuple[UUID, str]] = []
    for paper in papers:
        chunks = await ingestion_repo.chunks_for_paper(paper["id"])
        body = "\n".join(
            f"[{json.dumps(c['hierarchy'])}] {c['content']}" for c in chunks
        )
        paper_time = paper.get("time_limit_minutes")
        time_note = (
            f"\n[time_limit_minutes: {paper_time}]"
            if paper_time is not None
            else "\n[time_limit_minutes: not stated]"
        )
        body += time_note
        paper_texts.append((paper["id"], body))

    agent = build_blueprint_agent(
        alignment_tool=_alignment_tool(alignment_model, course_repo)
    )
    structure: BlueprintStructure
    structure, failures = await run_agent_with_corrective_retry(
        agent,
        blueprint_input(paper_texts),
        lambda s: validate_blueprint(s, [p["id"] for p in papers]),
        model=blueprint_model,
    )
    if failures:
        logger.info(
            "blueprint_validation_failed",
            course_id=str(course_id),
            failure_count=len(failures),
        )

    # Persist instructor sightings with banding re-enforced (FR-007/008).
    for sighting in structure.instructor_sightings:
        await _persist_resolution(course_id, sighting, course_repo, link_course=False)

    _, version = await course_repo.write_blueprint_version(
        course_id,
        structure.model_dump(mode="json"),
        [p["id"] for p in papers],
    )
    return int(version)


async def _align_course_instructor(
    course_id: UUID, course_repo: Any, alignment_model: Model | None
) -> None:
    """Resolve the course's recorded instructor name (US2, FR-005..FR-007).

    Alignment failures never fail the ingest — the paper is already
    completed; the resolution can re-run on the next ingest.
    """
    course = await course_repo.get_course(course_id)
    raw_name = course.get("instructor_name")
    if not raw_name:
        return
    try:
        agent = build_alignment_agent(repo=course_repo)
        resolution: InstructorResolution = await run_agent(
            agent, alignment_input(raw_name), model=alignment_model
        )
        await _persist_resolution(course_id, resolution, course_repo, link_course=True)
    except Exception:
        logger.warning("instructor_alignment_failed", course_id=str(course_id))


async def _persist_resolution(
    course_id: UUID,
    resolution: InstructorResolution,
    course_repo: Any,
    *,
    link_course: bool,
) -> None:
    """Persist one resolution with banding re-enforced in code (FR-007).

    Band b never merges; the course link is set only on matched/created
    (FR-006) and only for the course's own instructor resolution.
    """
    instructors = await course_repo.list_instructors()
    scored = score_stored_instructors(resolution.raw_name, instructors)
    final = enforce_banding(resolution, scored)

    instructor_id: UUID | None = None
    if final.outcome == "matched":
        instructor_id = final.matched_instructor_id
    elif final.outcome == "created":
        normalized = normalize_name(final.raw_name)
        existing = await course_repo.find_instructor_by_normalized_name(normalized)
        instructor_id = (
            existing["id"]
            if existing
            else await course_repo.create_instructor(normalized, final.raw_name.strip())
        )

    await course_repo.save_resolution(
        course_id,
        {
            "raw_name": final.raw_name,
            "normalized_name": normalize_name(final.raw_name),
            "instructor_id": instructor_id,
            "outcome": final.outcome,
            "confidence": final.confidence,
            "candidates": [c.model_dump(mode="json") for c in final.candidates],
        },
    )
    if link_course and instructor_id is not None:
        await course_repo.link_course_instructor(course_id, instructor_id)


def _alignment_tool(alignment_model: Model | None, course_repo: Any) -> Any:
    """Alignment agent wrapped as ``resolve_instructor_sighting`` (FR-008).

    ``Agent.as_tool`` runs the full alignment agent inside the blueprint
    agent's run; the typed resolution surfaces in the blueprint output for
    the pipeline to persist (read-only here — R2).
    """
    agent = build_alignment_agent(repo=course_repo)
    if alignment_model is not None:
        agent = agent.clone(model=alignment_model)
    return agent.as_tool(
        tool_name="resolve_instructor_sighting",
        tool_description=(
            "Resolve a printed instructor name that differs from the "
            "course's recorded instructor. Input: the raw name as printed. "
            "Returns the typed resolution."
        ),
    )
