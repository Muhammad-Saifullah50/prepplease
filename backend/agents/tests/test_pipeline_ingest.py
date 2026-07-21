"""End-to-end ingest pipeline tests with fakes throughout (T018, US1)."""

import uuid
from typing import Any

import pytest

from exambrain_agents.errors import UnsupportedFormatError
from exambrain_agents.pipelines.ingest import ingest_course_file
from exambrain_agents.schemas.blueprint import (
    BlueprintSection,
    BlueprintStructure,
    PaperEvidence,
    TopicWeight,
)
from exambrain_agents.schemas.parsing import (
    ParsedDocument,
    ParsedQuestion,
    ParsedSection,
    ParsedSlide,
)
from exambrain_agents.testing import FakeModel, FinalOutput
from tests.conftest import (
    FakeCourseCoreRepo,
    FakeEmbedder,
    FakeIngestionRepo,
    FakeS3,
)


def parsed_paper(confidence: float = 0.95) -> ParsedDocument:
    return ParsedDocument(
        kind="past_paper",
        document_type="pdf_digital",
        instructor_name_seen=None,
        sections=[
            ParsedSection(
                title="Section A",
                instructions=None,
                questions=[
                    ParsedQuestion(
                        number="1", text="Define entropy.", marks=5.0, page=1
                    ),
                    ParsedQuestion(
                        number="2", text="Derive PV=nRT.", marks=10.0, page=2
                    ),
                ],
                slides=[],
            )
        ],
        total_marks=15.0,
        confidence=confidence,
    )


def parsed_slides() -> ParsedDocument:
    return ParsedDocument(
        kind="course_material",
        document_type="pptx",
        instructor_name_seen=None,
        sections=[
            ParsedSection(
                title="Week 1",
                instructions=None,
                questions=[],
                slides=[ParsedSlide(index=1, text="Entropy basics.")],
            )
        ],
        total_marks=None,
        confidence=0.9,
    )


def blueprint_for(paper_ids: list[uuid.UUID]) -> BlueprintStructure:
    return BlueprintStructure(
        sections=[
            BlueprintSection(
                name="Section A",
                question_type="short_answer",
                question_count=2,
                marks_each=7.5,
                total_marks=15.0,
            )
        ],
        total_marks=15.0,
        marks_distribution={"short_answer": 1.0},
        topic_weights=[TopicWeight(topic="thermo", weight=1.0)],
        phrasing_style=["terse"],
        evidence=[
            PaperEvidence(past_paper_id=p, observations=["one section"])
            for p in paper_ids
        ],
        instructor_sightings=[],
        confidence=0.8,
    )


@pytest.fixture
def env(
    fake_s3: FakeS3,
    fake_embedder: FakeEmbedder,
    ingestion_repo: FakeIngestionRepo,
    course_repo: FakeCourseCoreRepo,
) -> dict[str, Any]:
    course_id = course_repo.add_course(instructor_name=None)
    return {
        "s3": fake_s3,
        "embedder": fake_embedder,
        "ingestion_repo": ingestion_repo,
        "course_repo": course_repo,
        "course_id": course_id,
    }


async def ingest_paper(
    env: dict[str, Any],
    *,
    s3_key: str = "courses/c/p1.pdf",
    pdf: bytes | None = None,
    parsing_output: ParsedDocument | None = None,
    blueprint_output: BlueprintStructure | None = None,
    paper_id: uuid.UUID | None = None,
) -> Any:
    repo: FakeIngestionRepo = env["ingestion_repo"]
    if paper_id is None:
        paper_id = repo.add_paper(env["course_id"], s3_key)
    if pdf is not None:
        env["s3"].objects[s3_key] = pdf
    parsing_model = FakeModel(outputs=[FinalOutput(parsing_output or parsed_paper())])
    blueprint_model = (
        FakeModel(outputs=[FinalOutput(blueprint_output)])
        if blueprint_output is not None
        else FakeModel(outputs=[FinalOutput(blueprint_for([paper_id]))])
    )
    result = await ingest_course_file(
        env["course_id"],
        s3_key,
        "past_paper",
        past_paper_id=paper_id,
        s3=env["s3"],
        embedder=env["embedder"],
        ingestion_repo=repo,
        course_repo=env["course_repo"],
        parsing_model=parsing_model,
        blueprint_model=blueprint_model,
    )
    return result, paper_id


async def test_completed_lifecycle_digital_pdf(
    env: dict[str, Any], digital_pdf_bytes: bytes
) -> None:
    """US1 AS1: parse → chunk+embed → blueprint v1 → completed."""
    result, paper_id = await ingest_paper(env, pdf=digital_pdf_bytes)
    assert result.status == "completed"
    assert result.blueprint_version == 1
    assert result.chunks_written == 2
    assert result.needs_review is False
    paper = await env["ingestion_repo"].get_paper(paper_id)
    assert paper["processing_status"] == "completed"
    assert paper["parsing_confidence"] == 0.95
    # Chunks persisted with embeddings.
    chunks = await env["ingestion_repo"].chunks_for_paper(paper_id)
    assert len(chunks) == 2
    assert all(c["embedding"] is not None for c in chunks)
    # Blueprint v1 written with the paper as source.
    bp = await env["course_repo"].latest_blueprint(env["course_id"])
    assert bp is not None and bp["version"] == 1
    assert str(paper_id) in bp["source_past_paper_ids"]


async def test_version_increments_on_new_paper(
    env: dict[str, Any], digital_pdf_bytes: bytes
) -> None:
    """US1 AS2: second paper → version N+1; version N untouched."""
    _, p1 = await ingest_paper(env, s3_key="courses/c/p1.pdf", pdf=digital_pdf_bytes)
    p2 = env["ingestion_repo"].add_paper(env["course_id"], "courses/c/p2.pdf")
    result, _ = await ingest_paper(
        env,
        s3_key="courses/c/p2.pdf",
        pdf=digital_pdf_bytes,
        paper_id=p2,
        blueprint_output=blueprint_for([p1, p2]),  # evidence for the full set
    )
    assert result.blueprint_version == 2
    versions = sorted(
        b["version"]
        for b in env["course_repo"].blueprints
        if b["course_id"] == env["course_id"]
    )
    assert versions == [1, 2]


async def test_scanned_pdf_path(env: dict[str, Any], scanned_pdf_bytes: bytes) -> None:
    """US1 AS3: image-only PDF routes through OCR and completes."""
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not installed")
    result, _ = await ingest_paper(env, pdf=scanned_pdf_bytes)
    assert result.status == "completed"


async def test_pptx_course_material_no_blueprint(
    env: dict[str, Any], pptx_bytes: bytes
) -> None:
    """US1 AS4: course material is chunked + embedded, no blueprint step."""
    s3_key = "courses/c/week1.pptx"
    env["s3"].objects[s3_key] = pptx_bytes
    result = await ingest_course_file(
        env["course_id"],
        s3_key,
        "course_material",
        s3=env["s3"],
        embedder=env["embedder"],
        ingestion_repo=env["ingestion_repo"],
        course_repo=env["course_repo"],
        parsing_model=FakeModel(outputs=[FinalOutput(parsed_slides())]),
    )
    assert result.status == "completed"
    assert result.blueprint_version is None
    assert result.past_paper_id is None
    assert result.chunks_written == 1
    assert await env["ingestion_repo"].course_has_content(env["course_id"])


async def test_irrecoverable_failure_marks_failed_no_partial_writes(
    env: dict[str, Any], corrupt_pdf_bytes: bytes
) -> None:
    """US1 AS5: corrupt file → failed + reason, nothing persisted."""
    result, paper_id = await ingest_paper(env, pdf=corrupt_pdf_bytes)
    assert result.status == "failed"
    assert result.failure_reason
    paper = await env["ingestion_repo"].get_paper(paper_id)
    assert paper["processing_status"] == "failed"
    assert paper["failure_reason"]
    assert env["ingestion_repo"].chunks == {}
    assert env["course_repo"].blueprints == []


async def test_unsupported_format_rejected_up_front(env: dict[str, Any]) -> None:
    repo: FakeIngestionRepo = env["ingestion_repo"]
    paper_id = repo.add_paper(env["course_id"], "courses/c/grades.xlsx")
    env["s3"].objects["courses/c/grades.xlsx"] = b"binary"
    with pytest.raises(UnsupportedFormatError):
        await ingest_course_file(
            env["course_id"],
            "courses/c/grades.xlsx",
            "past_paper",
            past_paper_id=paper_id,
            s3=env["s3"],
            embedder=env["embedder"],
            ingestion_repo=repo,
            course_repo=env["course_repo"],
            parsing_model=FakeModel(outputs=[]),
        )
    # Rejected before any processing: status untouched, nothing written.
    paper = await repo.get_paper(paper_id)
    assert paper["processing_status"] == "pending"
    assert repo.chunks == {}


async def test_low_confidence_flags_needs_review_and_skips_blueprint(
    env: dict[str, Any], digital_pdf_bytes: bytes
) -> None:
    """FR-002 + clarified rule: needs-review paper excluded from extraction."""
    result, paper_id = await ingest_paper(
        env, pdf=digital_pdf_bytes, parsing_output=parsed_paper(confidence=0.2)
    )
    assert result.status == "completed"
    assert result.needs_review is True
    assert result.blueprint_version is None  # excluded from extraction
    assert env["course_repo"].blueprints == []
    paper = await env["ingestion_repo"].get_paper(paper_id)
    assert paper["needs_review"] is True


async def test_idempotent_rerun_no_duplicate_chunks_or_version(
    env: dict[str, Any], digital_pdf_bytes: bytes
) -> None:
    """Edge case: re-running a completed paper replaces, never duplicates."""
    result1, paper_id = await ingest_paper(env, pdf=digital_pdf_bytes)
    result2, _ = await ingest_paper(env, pdf=digital_pdf_bytes, paper_id=paper_id)
    assert result2.status == "completed"
    chunks = await env["ingestion_repo"].chunks_for_paper(paper_id)
    assert len(chunks) == 2  # replaced, not appended
    # Paper set unchanged → no duplicate version.
    versions = [
        b["version"]
        for b in env["course_repo"].blueprints
        if b["course_id"] == env["course_id"]
    ]
    assert versions == [1]
    assert result2.blueprint_version is None


async def test_blueprint_runs_over_full_eligible_paper_set(
    env: dict[str, Any], digital_pdf_bytes: bytes
) -> None:
    """FR-009: extraction gathers ALL completed, non-review papers."""
    _, p1 = await ingest_paper(env, s3_key="courses/c/p1.pdf", pdf=digital_pdf_bytes)
    # Second paper: the blueprint model receives both papers' content.
    repo: FakeIngestionRepo = env["ingestion_repo"]
    p2 = repo.add_paper(env["course_id"], "courses/c/p2.pdf")
    env["s3"].objects["courses/c/p2.pdf"] = digital_pdf_bytes
    blueprint_model = FakeModel(outputs=[FinalOutput(blueprint_for([p1, p2]))])
    result = await ingest_course_file(
        env["course_id"],
        "courses/c/p2.pdf",
        "past_paper",
        past_paper_id=p2,
        s3=env["s3"],
        embedder=env["embedder"],
        ingestion_repo=repo,
        course_repo=env["course_repo"],
        parsing_model=FakeModel(outputs=[FinalOutput(parsed_paper())]),
        blueprint_model=blueprint_model,
    )
    assert result.blueprint_version == 2
    bp = await env["course_repo"].latest_blueprint(env["course_id"])
    assert set(bp["source_past_paper_ids"]) == {str(p1), str(p2)}


async def test_blueprint_serialized_via_course_lock(
    env: dict[str, Any], digital_pdf_bytes: bytes
) -> None:
    """R6: version write happens under the per-course advisory lock."""
    await ingest_paper(env, pdf=digital_pdf_bytes)
    assert env["course_repo"].lock_acquisitions == [env["course_id"]]


async def test_ingest_resolves_course_instructor(
    fake_s3: FakeS3,
    fake_embedder: FakeEmbedder,
    ingestion_repo: FakeIngestionRepo,
    course_repo: FakeCourseCoreRepo,
    digital_pdf_bytes: bytes,
) -> None:
    """US2 integration: after paper completion, the course's instructor
    name is aligned — banding enforced in code — and the course linked."""
    from exambrain_agents.schemas.alignment import InstructorResolution

    course_id = course_repo.add_course(instructor_name="Dr. Abdul Rahman")
    existing = course_repo.add_instructor("abdul rahman", "Abdul Rahman")
    paper_id = ingestion_repo.add_paper(course_id, "courses/c/p.pdf")
    fake_s3.objects["courses/c/p.pdf"] = digital_pdf_bytes

    # Misbehaving alignment agent claims "created" — code re-bands to
    # matched because the deterministic score vs "abdul rahman" is 1.0.
    bad_resolution = InstructorResolution(
        raw_name="Dr. Abdul Rahman",
        normalized_name="abdul rahman",
        outcome="created",
        matched_instructor_id=None,
        confidence=1.0,
        candidates=[],
    )
    result = await ingest_course_file(
        course_id,
        "courses/c/p.pdf",
        "past_paper",
        past_paper_id=paper_id,
        s3=fake_s3,
        embedder=fake_embedder,
        ingestion_repo=ingestion_repo,
        course_repo=course_repo,
        parsing_model=FakeModel(outputs=[FinalOutput(parsed_paper())]),
        blueprint_model=FakeModel(outputs=[FinalOutput(blueprint_for([paper_id]))]),
        alignment_model=FakeModel(outputs=[FinalOutput(bad_resolution)]),
    )
    assert result.status == "completed"
    [resolution] = course_repo.resolutions
    assert resolution["outcome"] == "matched"  # banding overrode the agent
    assert resolution["instructor_id"] == existing
    assert course_repo.courses[course_id]["instructor_id"] == existing


async def test_ingest_gray_zone_never_links_course(
    fake_s3: FakeS3,
    fake_embedder: FakeEmbedder,
    ingestion_repo: FakeIngestionRepo,
    course_repo: FakeCourseCoreRepo,
    digital_pdf_bytes: bytes,
) -> None:
    """FR-007 band b: needs_review persisted with candidates, no link."""
    from exambrain_agents.schemas.alignment import Candidate, InstructorResolution

    course_id = course_repo.add_course(instructor_name="Dr. A. Raheem Khan")
    near_miss = course_repo.add_instructor(
        "abdul raheem khanzada", "Abdul Raheem Khanzada"
    )
    paper_id = ingestion_repo.add_paper(course_id, "courses/c/p.pdf")
    fake_s3.objects["courses/c/p.pdf"] = digital_pdf_bytes

    agent_resolution = InstructorResolution(
        raw_name="Dr. A. Raheem Khan",
        normalized_name="a raheem khan",
        outcome="needs_review",
        matched_instructor_id=None,
        confidence=0.8,
        candidates=[
            Candidate(
                instructor_id=near_miss,
                normalized_name="abdul raheem khanzada",
                score=0.8,
            )
        ],
    )
    await ingest_course_file(
        course_id,
        "courses/c/p.pdf",
        "past_paper",
        past_paper_id=paper_id,
        s3=fake_s3,
        embedder=fake_embedder,
        ingestion_repo=ingestion_repo,
        course_repo=course_repo,
        parsing_model=FakeModel(outputs=[FinalOutput(parsed_paper())]),
        blueprint_model=FakeModel(outputs=[FinalOutput(blueprint_for([paper_id]))]),
        alignment_model=FakeModel(outputs=[FinalOutput(agent_resolution)]),
    )
    [resolution] = course_repo.resolutions
    assert resolution["outcome"] == "needs_review"
    assert resolution["candidates"]  # candidate list persisted
    assert resolution["instructor_id"] is None
    assert course_repo.courses[course_id]["instructor_id"] is None  # never merged
