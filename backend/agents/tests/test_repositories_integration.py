"""Real-repository integration + quickstart walkthrough (T057).

Marker ``migration``: needs the docker Postgres with all three service DBs
migrated to head. Exercises the real ``exambrain_agents.repositories``
layer and the full quickstart pipeline flow (ingest → generate →
evaluate) with FakeModel — zero LLM network traffic (SC-007/SC-008).
"""

import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from exambrain_agents import (
    evaluate_submission,
    generate_exam,
    ingest_course_file,
)
from exambrain_agents.repositories.course_core import CourseCoreRepository
from exambrain_agents.repositories.exam_sim import ExamSimRepository
from exambrain_agents.repositories.ingestion import IngestionRepository
from exambrain_agents.testing import FakeModel, FinalOutput
from tests.conftest import FakeEmbedder, FakeS3
from tests.test_pipeline_generate import make_exam
from tests.test_pipeline_ingest import blueprint_for, parsed_paper, parsed_slides

pytestmark = pytest.mark.migration

BACKEND = Path(__file__).resolve().parents[2]
PG_ASYNC = "postgresql+asyncpg://exambrain:exambrain@localhost:5432"
SERVICES = {
    "course_core": "course-core",
    "ingestion": "ingestion-pipeline",
    "exam_sim": "exam-simulation",
}


@pytest.fixture(scope="module", autouse=True)
def migrated_dbs() -> Any:
    """Upgrade all three DBs to head; downgrade to base afterwards."""
    for db, service in SERVICES.items():
        _alembic(service, db, "upgrade", "head")
    yield
    for db, service in SERVICES.items():
        _alembic(service, db, "downgrade", "base")


def _alembic(service: str, db: str, *args: str) -> None:
    result = subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=BACKEND / "services" / service,
        env={
            "DATABASE_URL": f"{PG_ASYNC}/{db}",
            "PATH": os.environ["PATH"],
            "HOME": os.environ.get("HOME", "/tmp"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic {args} failed:\n{result.stderr}"


@pytest.fixture
async def repos() -> Any:
    """Real repositories, each on its own service DB engine."""
    engines = {db: create_async_engine(f"{PG_ASYNC}/{db}") for db in SERVICES}
    factories = {
        db: async_sessionmaker(engine, expire_on_commit=False)
        for db, engine in engines.items()
    }
    yield {
        "ingestion": IngestionRepository(factories["ingestion"]),
        "course": CourseCoreRepository(factories["course_core"]),
        "exam_sim": ExamSimRepository(factories["exam_sim"]),
        "factories": factories,
    }
    for engine in engines.values():
        await engine.dispose()


async def _seed_course(
    factories: dict[str, Any], instructor_name: str | None = None
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a user + course into course_core; return (user_id, course_id)."""
    async with factories["course_core"]() as session, session.begin():
        user_id = (
            await session.execute(
                text(
                    "INSERT INTO users (email, display_name)"
                    " VALUES (:email, 'U') RETURNING id"
                ),
                {"email": f"{uuid.uuid4()}@x.y"},
            )
        ).scalar_one()
        course_id = (
            await session.execute(
                text(
                    "INSERT INTO courses (user_id, title, instructor_name)"
                    " VALUES (:uid, 'Thermo', :iname) RETURNING id"
                ),
                {"uid": user_id, "iname": instructor_name},
            )
        ).scalar_one()
    return user_id, course_id


async def _seed_paper(
    factories: dict[str, Any], course_id: uuid.UUID, s3_key: str
) -> uuid.UUID:
    async with factories["ingestion"]() as session, session.begin():
        return (
            await session.execute(
                text(
                    "INSERT INTO past_papers (course_id, s3_key)"
                    " VALUES (:cid, :key) RETURNING id"
                ),
                {"cid": course_id, "key": s3_key},
            )
        ).scalar_one()


async def test_quickstart_walkthrough_end_to_end(
    repos: dict[str, Any],
    digital_pdf_bytes: bytes,
    pptx_bytes: bytes,
) -> None:
    """Quickstart steps 1-4 against real DBs, FakeModel throughout."""
    factories = repos["factories"]
    user_id, course_id = await _seed_course(factories, "Dr. Abdul Rahman")
    paper_id = await _seed_paper(factories, course_id, "courses/c/mid.pdf")

    s3 = FakeS3()
    s3.objects["courses/c/mid.pdf"] = digital_pdf_bytes
    s3.objects["courses/c/w1.pptx"] = pptx_bytes
    embedder = FakeEmbedder()

    from exambrain_agents.schemas.alignment import InstructorResolution

    # 1. Ingest the past paper → completed, blueprint v1, instructor created.
    result = await ingest_course_file(
        course_id,
        "courses/c/mid.pdf",
        "past_paper",
        past_paper_id=paper_id,
        s3=s3,
        embedder=embedder,
        ingestion_repo=repos["ingestion"],
        course_repo=repos["course"],
        parsing_model=FakeModel(outputs=[FinalOutput(parsed_paper())]),
        blueprint_model=FakeModel(outputs=[FinalOutput(blueprint_for([paper_id]))]),
        alignment_model=FakeModel(
            outputs=[
                FinalOutput(
                    InstructorResolution(
                        raw_name="Dr. Abdul Rahman",
                        normalized_name="abdul rahman",
                        outcome="created",
                        matched_instructor_id=None,
                        confidence=1.0,
                        candidates=[],
                    )
                )
            ]
        ),
    )
    assert result.status == "completed"
    assert result.blueprint_version == 1
    assert result.chunks_written == 2
    paper = await repos["ingestion"].get_paper(paper_id)
    assert paper["processing_status"] == "completed"
    course = await repos["course"].get_course(course_id)
    assert course["instructor_id"] is not None  # created + linked
    instructor = await repos["course"].find_instructor_by_normalized_name(
        "abdul rahman"
    )
    assert instructor is not None

    # Idempotent re-run: chunks replaced, no duplicate blueprint version.
    rerun = await ingest_course_file(
        course_id,
        "courses/c/mid.pdf",
        "past_paper",
        past_paper_id=paper_id,
        s3=s3,
        embedder=embedder,
        ingestion_repo=repos["ingestion"],
        course_repo=repos["course"],
        parsing_model=FakeModel(outputs=[FinalOutput(parsed_paper())]),
        blueprint_model=FakeModel(outputs=[FinalOutput(blueprint_for([paper_id]))]),
        alignment_model=FakeModel(
            outputs=[
                FinalOutput(
                    InstructorResolution(
                        raw_name="Dr. Abdul Rahman",
                        normalized_name="abdul rahman",
                        outcome="matched",
                        matched_instructor_id=instructor["id"],
                        confidence=1.0,
                        candidates=[],
                    )
                )
            ]
        ),
    )
    assert rerun.blueprint_version is None  # paper set unchanged
    assert len(await repos["ingestion"].chunks_for_paper(paper_id)) == 2

    # 2. Ingest lecture slides (course material, no blueprint step).
    slides_result = await ingest_course_file(
        course_id,
        "courses/c/w1.pptx",
        "course_material",
        s3=s3,
        embedder=embedder,
        ingestion_repo=repos["ingestion"],
        course_repo=repos["course"],
        parsing_model=FakeModel(outputs=[FinalOutput(parsed_slides())]),
    )
    assert slides_result.status == "completed"
    assert slides_result.blueprint_version is None

    # 3. Generate a mock exam grounded in the stored chunks.
    async with factories["ingestion"]() as session:
        chunk_ids = [
            row[0]
            for row in await session.execute(
                text("SELECT id FROM document_chunks WHERE course_id = :cid"),
                {"cid": course_id},
            )
        ]
    # The generator FakeModel emits an exam matching blueprint_for's
    # 1-section / 2-question / 15-mark shape, citing real chunk ids.
    exam_output = make_exam(chunk_ids)
    exam_output = exam_output.model_copy(
        update={
            "sections": [
                exam_output.sections[0].model_copy(
                    update={
                        "questions": [
                            q.model_copy(update={"marks": 7.5})
                            for q in exam_output.sections[0].questions
                        ]
                    }
                )
            ],
            "total_marks": 15.0,
            "rubric": [e.model_copy(update={"marks": 7.5}) for e in exam_output.rubric],
        }
    )
    record = await generate_exam(
        course_id,
        embedder=embedder,
        ingestion_repo=repos["ingestion"],
        course_repo=repos["course"],
        exam_sim_repo=repos["exam_sim"],
        generator_model=FakeModel(outputs=[FinalOutput(exam_output)]),
    )
    assert record.status == "ready"
    assert record.blueprint_version == 1
    stored_exam = await repos["exam_sim"].get_generated_exam(record.id)
    assert stored_exam["status"] == "ready"

    # 4. Grade a completed session for that exam.
    async with factories["exam_sim"]() as session, session.begin():
        session_id = (
            await session.execute(
                text(
                    "INSERT INTO exam_sessions (user_id, course_id,"
                    " exam_content, started_at, status) VALUES"
                    " (:uid, :cid, '{}', now(), 'submitted') RETURNING id"
                ),
                {"uid": user_id, "cid": course_id},
            )
        ).scalar_one()

    from exambrain_agents.schemas.evaluation import EvaluationOutput, QuestionScore

    evaluation_output = EvaluationOutput(
        question_scores=[
            QuestionScore(
                question_number="1",
                score=6.0,
                max_marks=7.5,
                credited_points=["defines entropy"],
                missing_points=[],
                feedback="Good.",
            ),
            QuestionScore(
                question_number="2",
                score=0.0,
                max_marks=7.5,
                credited_points=[],
                missing_points=["states second law"],
                feedback="Not attempted.",
            ),
        ],
        aggregate_score=6.0,
        max_score=15.0,
        weak_topics=["second law"],
    )
    evaluation = await evaluate_submission(
        session_id,
        record.id,
        [
            {"question_number": "1", "text": "Entropy measures disorder."},
            {"question_number": "2", "text": None},
        ],
        course_repo=repos["course"],
        exam_sim_repo=repos["exam_sim"],
        evaluation_model=FakeModel(outputs=[FinalOutput(evaluation_output)]),
    )
    assert evaluation.needs_review is False
    assert float(evaluation.aggregate_score) == 6.0

    # Exactly one result per session; repeat call upserts, not duplicates.
    await evaluate_submission(
        session_id,
        record.id,
        [{"question_number": "1", "text": "x"}, {"question_number": "2", "text": None}],
        course_repo=repos["course"],
        exam_sim_repo=repos["exam_sim"],
        evaluation_model=FakeModel(outputs=[FinalOutput(evaluation_output)]),
    )
    async with factories["course_core"]() as session:
        count = (
            await session.execute(
                text("SELECT count(*) FROM results WHERE exam_session_id = :sid"),
                {"sid": session_id},
            )
        ).scalar_one()
    assert count == 1


async def test_pgvector_search_and_eligibility(repos: dict[str, Any]) -> None:
    """Repository-level: cosine search ordering + eligible-paper filter."""
    factories = repos["factories"]
    _, course_id = await _seed_course(factories)
    paper_id = await _seed_paper(factories, course_id, "courses/c/p.pdf")

    def unit(axis: int) -> list[float]:
        vec = [0.0] * 1024
        vec[axis] = 1.0
        return vec

    await repos["ingestion"].replace_chunks(
        course_id=course_id,
        source_s3_key="courses/c/p.pdf",
        past_paper_id=paper_id,
        chunks=[
            {
                "content": f"chunk {i}",
                "position": i,
                "hierarchy": {"kind": "past_paper"},
                "embedding": unit(i),
            }
            for i in range(3)
        ],
    )
    results = await repos["ingestion"].search_chunks(course_id, unit(1), limit=2)
    assert results[0]["content"] == "chunk 1"
    assert results[0]["similarity"] > results[1]["similarity"]
    assert await repos["ingestion"].course_has_content(course_id)

    ids = [r["chunk_id"] for r in results]
    existing = await repos["ingestion"].existing_chunk_ids(
        course_id, [*ids, uuid.uuid4()]
    )
    assert existing == set(ids)

    # Paper not completed yet → not eligible; then completed → eligible;
    # needs_review → excluded again (FR-009).
    assert await repos["ingestion"].eligible_papers(course_id) == []
    await repos["ingestion"].mark_processing(paper_id)
    await repos["ingestion"].mark_completed(
        paper_id, parsing_confidence=0.9, needs_review=False
    )
    assert [p["id"] for p in await repos["ingestion"].eligible_papers(course_id)] == [
        paper_id
    ]
    await repos["ingestion"].mark_completed(
        paper_id, parsing_confidence=0.3, needs_review=True
    )
    assert await repos["ingestion"].eligible_papers(course_id) == []
    await repos["ingestion"].mark_failed(paper_id, "irrecoverable")
    paper = await repos["ingestion"].get_paper(paper_id)
    assert paper["processing_status"] == "failed"
    assert paper["failure_reason"] == "irrecoverable"


async def test_blueprint_versions_are_immutable_and_serialized(
    repos: dict[str, Any],
) -> None:
    """FR-010: version max+1 under the advisory lock; priors readable."""
    factories = repos["factories"]
    _, course_id = await _seed_course(factories)
    p1, p2 = uuid.uuid4(), uuid.uuid4()

    _, v1 = await repos["course"].write_blueprint_version(course_id, {"v": 1}, [p1])
    _, v2 = await repos["course"].write_blueprint_version(course_id, {"v": 2}, [p1, p2])
    assert (v1, v2) == (1, 2)
    latest = await repos["course"].latest_blueprint(course_id)
    assert latest["version"] == 2
    assert set(latest["source_past_paper_ids"]) == {str(p1), str(p2)}

    # Version 1 remains readable and untouched.
    async with factories["course_core"]() as session:
        v1_structure = (
            await session.execute(
                text(
                    "SELECT structure FROM exam_blueprints"
                    " WHERE course_id = :cid AND version = 1"
                ),
                {"cid": course_id},
            )
        ).scalar_one()
    assert v1_structure == {"v": 1}
