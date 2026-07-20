"""Generate-exam pipeline tests (T031 — TDD critical path, US3)."""

import uuid
from typing import Any

import pytest

from exambrain_agents.errors import (
    AgentTurnLimitError,
    BlueprintRequiredError,
    ContentRequiredError,
)
from exambrain_agents.pipelines.generate import generate_exam
from exambrain_agents.schemas.blueprint import (
    BlueprintSection,
    BlueprintStructure,
    PaperEvidence,
    TopicWeight,
)
from exambrain_agents.schemas.generation import (
    ExamQuestion,
    ExamSection,
    GeneratedExam,
    RubricEntry,
)
from exambrain_agents.testing import FakeModel, FinalOutput, ToolCall
from tests.conftest import FakeCourseCoreRepo, FakeEmbedder, FakeIngestionRepo


def blueprint_structure() -> BlueprintStructure:
    return BlueprintStructure(
        sections=[
            BlueprintSection(
                name="Section A",
                question_type="short_answer",
                question_count=2,
                marks_each=5.0,
                total_marks=10.0,
            )
        ],
        total_marks=10.0,
        marks_distribution={"short_answer": 1.0},
        topic_weights=[TopicWeight(topic="thermo", weight=1.0)],
        phrasing_style=["terse"],
        evidence=[
            PaperEvidence(past_paper_id=uuid.uuid4(), observations=["obs"])
        ],
        instructor_sightings=[],
        confidence=0.8,
    )


def make_exam(chunk_ids: list[uuid.UUID], **overrides: Any) -> GeneratedExam:
    questions = [
        ExamQuestion(
            number="1",
            text="Define entropy.",
            marks=5.0,
            topic="thermo",
            source_chunk_ids=[chunk_ids[0]],
        ),
        ExamQuestion(
            number="2",
            text="State the second law.",
            marks=5.0,
            topic="thermo",
            source_chunk_ids=[chunk_ids[-1]],
        ),
    ]
    defaults: dict[str, Any] = {
        "sections": [
            ExamSection(
                name="Section A",
                question_type="short_answer",
                instructions=None,
                questions=questions,
            )
        ],
        "total_marks": 10.0,
        "rubric": [
            RubricEntry(
                question_number="1",
                expected_points=["defines entropy"],
                marks=5.0,
                source_chunk_ids=[chunk_ids[0]],
            ),
            RubricEntry(
                question_number="2",
                expected_points=["states second law"],
                marks=5.0,
                source_chunk_ids=[chunk_ids[-1]],
            ),
        ],
        "ungrounded_topics": [],
    }
    defaults.update(overrides)
    return GeneratedExam(**defaults)


@pytest.fixture
async def env(
    fake_embedder: FakeEmbedder,
    ingestion_repo: FakeIngestionRepo,
    course_repo: FakeCourseCoreRepo,
    exam_sim_repo: Any,
) -> dict[str, Any]:
    course_id = course_repo.add_course()
    await course_repo.write_blueprint_version(
        course_id, blueprint_structure().model_dump(mode="json"), [uuid.uuid4()]
    )
    emb = await fake_embedder.embed("entropy content")
    await ingestion_repo.replace_chunks(
        course_id=course_id,
        source_s3_key="courses/c/w1.pptx",
        past_paper_id=None,
        chunks=[
            {
                "content": "entropy content",
                "position": 0,
                "hierarchy": {"kind": "course_material", "slide": 1},
                "embedding": emb,
            }
        ],
    )
    chunk_ids = list(ingestion_repo.chunks)
    return {
        "course_id": course_id,
        "embedder": fake_embedder,
        "ingestion_repo": ingestion_repo,
        "course_repo": course_repo,
        "exam_sim_repo": exam_sim_repo,
        "chunk_ids": chunk_ids,
    }


async def run(env: dict[str, Any], model: FakeModel) -> Any:
    return await generate_exam(
        env["course_id"],
        embedder=env["embedder"],
        ingestion_repo=env["ingestion_repo"],
        course_repo=env["course_repo"],
        exam_sim_repo=env["exam_sim_repo"],
        generator_model=model,
    )


async def test_valid_exam_persisted_ready(env: dict[str, Any]) -> None:
    """US3 AS1-AS3: structure matches, citations exist, rubric complete."""
    model = FakeModel(
        outputs=[
            ToolCall("search_course_content", {"query": "thermo"}),
            FinalOutput(make_exam(env["chunk_ids"])),
        ]
    )
    record = await run(env, model)
    assert record.status == "ready"
    assert record.needs_review_reasons == []
    assert record.blueprint_version == 1
    stored = env["exam_sim_repo"].generated_exams[record.id]
    assert stored["status"] == "ready"
    assert stored["blueprint_version"] == 1


async def test_corrective_retry_recovers(env: dict[str, Any]) -> None:
    """US3 AS4 happy half: first output invalid, retry passes → ready."""
    bad = make_exam(env["chunk_ids"], total_marks=99.0)  # marks mismatch
    good = make_exam(env["chunk_ids"])
    model = FakeModel(outputs=[FinalOutput(bad), FinalOutput(good)])
    record = await run(env, model)
    assert record.status == "ready"


async def test_second_failure_persists_needs_review(env: dict[str, Any]) -> None:
    """US3 AS4: both attempts fail validation → stored needs_review."""
    bad = make_exam(env["chunk_ids"], total_marks=99.0)
    model = FakeModel(outputs=[FinalOutput(bad), FinalOutput(bad)])
    record = await run(env, model)
    assert record.status == "needs_review"
    assert any("total" in r.lower() for r in record.needs_review_reasons)
    stored = env["exam_sim_repo"].generated_exams[record.id]
    assert stored["status"] == "needs_review"


async def test_unknown_chunk_citation_fails_validation(env: dict[str, Any]) -> None:
    """SC-005: citations must reference chunks that exist for the course."""
    bogus = make_exam([uuid.uuid4()])  # nonexistent chunk id
    model = FakeModel(outputs=[FinalOutput(bogus), FinalOutput(bogus)])
    record = await run(env, model)
    assert record.status == "needs_review"
    assert any("chunk" in r.lower() for r in record.needs_review_reasons)


async def test_ungrounded_topics_flag_needs_review(env: dict[str, Any]) -> None:
    """Edge case: thin content → exam usable but flagged with topics."""
    exam = make_exam(env["chunk_ids"], ungrounded_topics=["quantum"])
    model = FakeModel(outputs=[FinalOutput(exam)])
    record = await run(env, model)
    assert record.status == "needs_review"
    assert any("quantum" in r for r in record.needs_review_reasons)


async def test_missing_rubric_entry_fails_validation(env: dict[str, Any]) -> None:
    """FR-013: rubric must cover every question."""
    exam = make_exam(env["chunk_ids"])
    exam = exam.model_copy(update={"rubric": exam.rubric[:1]})
    model = FakeModel(outputs=[FinalOutput(exam), FinalOutput(exam)])
    record = await run(env, model)
    assert record.status == "needs_review"
    assert any("rubric" in r.lower() for r in record.needs_review_reasons)


async def test_no_blueprint_raises(
    fake_embedder: FakeEmbedder,
    ingestion_repo: FakeIngestionRepo,
    course_repo: FakeCourseCoreRepo,
    exam_sim_repo: Any,
) -> None:
    course_id = course_repo.add_course()
    with pytest.raises(BlueprintRequiredError):
        await generate_exam(
            course_id,
            embedder=fake_embedder,
            ingestion_repo=ingestion_repo,
            course_repo=course_repo,
            exam_sim_repo=exam_sim_repo,
            generator_model=FakeModel(outputs=[]),
        )


async def test_no_content_raises(
    fake_embedder: FakeEmbedder,
    ingestion_repo: FakeIngestionRepo,
    course_repo: FakeCourseCoreRepo,
    exam_sim_repo: Any,
) -> None:
    """US3 AS5: blueprint exists but no ingested content."""
    course_id = course_repo.add_course()
    await course_repo.write_blueprint_version(
        course_id, blueprint_structure().model_dump(mode="json"), [uuid.uuid4()]
    )
    with pytest.raises(ContentRequiredError):
        await generate_exam(
            course_id,
            embedder=fake_embedder,
            ingestion_repo=ingestion_repo,
            course_repo=course_repo,
            exam_sim_repo=exam_sim_repo,
            generator_model=FakeModel(outputs=[]),
        )


async def test_turn_limit_no_write(env: dict[str, Any]) -> None:
    """Edge case: budget exceeded → typed error, nothing persisted."""
    model = FakeModel(
        outputs=[ToolCall("search_course_content", {"query": "t"})] * 30
    )
    with pytest.raises(AgentTurnLimitError):
        await run(env, model)
    assert env["exam_sim_repo"].generated_exams == {}
