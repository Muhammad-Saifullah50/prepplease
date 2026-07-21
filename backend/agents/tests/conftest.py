"""Shared fixtures for the agents library test suite (research R9, FR-024).

Everything runs offline: agents are driven by
:class:`exambrain_agents.testing.FakeModel`, object storage by
:class:`FakeS3`, and persistence by in-memory fake repositories that
implement the same interfaces as ``exambrain_agents.repositories``.

Fixture files (``fixtures/``, all tiny and generated):
- ``digital_paper.pdf`` — 2-page digital PDF with section/question/marks
  text and an ``Instructor: Dr. A. Rahman`` line on page 1.
- ``scanned_paper.pdf`` — 2-page PDF with no extractable text (image-only
  stand-in; routes to the OCR path).
- ``slides.pptx`` — 2-slide lecture deck with titles and body text.
- ``corrupt.pdf`` — truncated garbage; extraction raises.
"""

import uuid
from pathlib import Path
from typing import Any

import pytest

from exambrain_shared.errors import ObjectNotFoundError

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def digital_pdf_bytes() -> bytes:
    return (FIXTURES / "digital_paper.pdf").read_bytes()


@pytest.fixture
def scanned_pdf_bytes() -> bytes:
    return (FIXTURES / "scanned_paper.pdf").read_bytes()


@pytest.fixture
def pptx_bytes() -> bytes:
    return (FIXTURES / "slides.pptx").read_bytes()


@pytest.fixture
def corrupt_pdf_bytes() -> bytes:
    return (FIXTURES / "corrupt.pdf").read_bytes()


class FakeS3:
    """In-memory stand-in for the S3Adapter surface pipelines use."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def download_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise ObjectNotFoundError(key)
        return self.objects[key]


class FakeEmbedder:
    """Deterministic embed() stand-in for LLMClient (1024-dim)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        self.calls.append(text)
        vec = [0.0] * 1024
        vec[hash(text) % 1024] = 1.0
        return vec


class FakeIngestionRepo:
    """In-memory ingestion-DB repository (papers + chunks)."""

    def __init__(self) -> None:
        self.papers: dict[uuid.UUID, dict[str, Any]] = {}
        self.chunks: dict[uuid.UUID, dict[str, Any]] = {}

    def add_paper(self, course_id: uuid.UUID, s3_key: str, **extra: Any) -> uuid.UUID:
        paper_id = uuid.uuid4()
        self.papers[paper_id] = {
            "id": paper_id,
            "course_id": course_id,
            "s3_key": s3_key,
            "processing_status": "pending",
            "failure_reason": None,
            "parsing_confidence": None,
            "needs_review": False,
            **extra,
        }
        return paper_id

    async def get_paper(self, paper_id: uuid.UUID) -> dict[str, Any]:
        if paper_id not in self.papers:
            raise ObjectNotFoundError(str(paper_id))
        return dict(self.papers[paper_id])

    async def mark_processing(self, paper_id: uuid.UUID) -> None:
        self.papers[paper_id]["processing_status"] = "processing"

    async def mark_completed(
        self, paper_id: uuid.UUID, *, parsing_confidence: float, needs_review: bool
    ) -> None:
        self.papers[paper_id].update(
            processing_status="completed",
            failure_reason=None,
            parsing_confidence=parsing_confidence,
            needs_review=needs_review,
        )

    async def mark_failed(self, paper_id: uuid.UUID, reason: str) -> None:
        self.papers[paper_id].update(processing_status="failed", failure_reason=reason)

    async def replace_chunks(
        self,
        *,
        course_id: uuid.UUID,
        source_s3_key: str,
        past_paper_id: uuid.UUID | None,
        chunks: list[dict[str, Any]],
    ) -> int:
        """Atomic delete-and-rewrite of one source's chunks (FR-004)."""
        stale = [
            cid for cid, c in self.chunks.items() if c["source_s3_key"] == source_s3_key
        ]
        for cid in stale:
            del self.chunks[cid]
        for chunk in chunks:
            cid = uuid.uuid4()
            self.chunks[cid] = {
                "id": cid,
                "course_id": course_id,
                "past_paper_id": past_paper_id,
                "source_s3_key": source_s3_key,
                **chunk,
            }
        return len(chunks)

    async def eligible_papers(self, course_id: uuid.UUID) -> list[dict[str, Any]]:
        """Completed, non-needs-review past papers for blueprinting (FR-009)."""
        return [
            dict(p)
            for p in self.papers.values()
            if p["course_id"] == course_id
            and p["processing_status"] == "completed"
            and not p["needs_review"]
        ]

    async def chunks_for_paper(self, paper_id: uuid.UUID) -> list[dict[str, Any]]:
        return sorted(
            (dict(c) for c in self.chunks.values() if c["past_paper_id"] == paper_id),
            key=lambda c: c["position"],
        )

    async def course_has_content(self, course_id: uuid.UUID) -> bool:
        return any(c["course_id"] == course_id for c in self.chunks.values())

    async def existing_chunk_ids(
        self, course_id: uuid.UUID, chunk_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        return {
            cid
            for cid in chunk_ids
            if cid in self.chunks and self.chunks[cid]["course_id"] == course_id
        }

    async def search_chunks(
        self, course_id: uuid.UUID, embedding: list[float], limit: int = 8
    ) -> list[dict[str, Any]]:
        """Cosine ranking over the in-memory chunks (unit-ish vectors)."""

        def dot(a: list[float], b: list[float]) -> float:
            return sum(x * y for x, y in zip(a, b, strict=True))

        rows = [
            c
            for c in self.chunks.values()
            if c["course_id"] == course_id and c.get("embedding") is not None
        ]
        rows.sort(key=lambda c: -dot(c["embedding"], embedding))
        return [
            {
                "chunk_id": c["id"],
                "content": c["content"],
                "hierarchy": c["hierarchy"],
                "similarity": dot(c["embedding"], embedding),
            }
            for c in rows[:limit]
        ]


class FakeCourseCoreRepo:
    """In-memory course-core repository (courses, blueprints, instructors, results)."""

    def __init__(self) -> None:
        self.courses: dict[uuid.UUID, dict[str, Any]] = {}
        self.blueprints: list[dict[str, Any]] = []
        self.instructors: dict[uuid.UUID, dict[str, Any]] = {}
        self.resolutions: list[dict[str, Any]] = []
        self.results: dict[uuid.UUID, dict[str, Any]] = {}
        self.lock_acquisitions: list[uuid.UUID] = []

    def add_course(self, instructor_name: str | None = None) -> uuid.UUID:
        course_id = uuid.uuid4()
        self.courses[course_id] = {
            "id": course_id,
            "instructor_name": instructor_name,
            "instructor_id": None,
        }
        return course_id

    def add_instructor(self, normalized_name: str, display_name: str) -> uuid.UUID:
        instructor_id = uuid.uuid4()
        self.instructors[instructor_id] = {
            "id": instructor_id,
            "normalized_name": normalized_name,
            "display_name": display_name,
        }
        return instructor_id

    async def get_course(self, course_id: uuid.UUID) -> dict[str, Any]:
        if course_id not in self.courses:
            raise ObjectNotFoundError(str(course_id))
        return dict(self.courses[course_id])

    async def write_blueprint_version(
        self,
        course_id: uuid.UUID,
        structure: dict[str, Any],
        source_past_paper_ids: list[uuid.UUID],
    ) -> tuple[uuid.UUID, int]:
        """Version max+1 'inside the advisory lock' (in-memory: recorded)."""
        self.lock_acquisitions.append(course_id)
        versions = [
            b["version"] for b in self.blueprints if b["course_id"] == course_id
        ]
        version = max(versions, default=0) + 1
        blueprint_id = uuid.uuid4()
        self.blueprints.append(
            {
                "id": blueprint_id,
                "course_id": course_id,
                "version": version,
                "structure": structure,
                "source_past_paper_ids": [str(p) for p in source_past_paper_ids],
            }
        )
        return blueprint_id, version

    async def latest_blueprint(self, course_id: uuid.UUID) -> dict[str, Any] | None:
        mine = [b for b in self.blueprints if b["course_id"] == course_id]
        return dict(max(mine, key=lambda b: b["version"])) if mine else None

    async def list_instructors(self) -> list[dict[str, Any]]:
        return [dict(i) for i in self.instructors.values()]

    async def find_instructor_by_normalized_name(
        self, normalized_name: str
    ) -> dict[str, Any] | None:
        for i in self.instructors.values():
            if i["normalized_name"] == normalized_name:
                return dict(i)
        return None

    async def create_instructor(
        self, normalized_name: str, display_name: str
    ) -> uuid.UUID:
        return self.add_instructor(normalized_name, display_name)

    async def save_resolution(
        self, course_id: uuid.UUID, resolution: dict[str, Any]
    ) -> None:
        self.resolutions.append({"course_id": course_id, **resolution})

    async def link_course_instructor(
        self, course_id: uuid.UUID, instructor_id: uuid.UUID
    ) -> None:
        self.courses[course_id]["instructor_id"] = instructor_id

    async def upsert_result(
        self, exam_session_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        """Exactly one result per session (FR-016)."""
        self.results[exam_session_id] = dict(payload)


class FakeExamSimRepo:
    """In-memory exam-sim repository (generated_exams + session lookups)."""

    def __init__(self) -> None:
        self.generated_exams: dict[uuid.UUID, dict[str, Any]] = {}
        self.sessions: dict[uuid.UUID, dict[str, Any]] = {}

    def add_session(self, course_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
        session_id = uuid.uuid4()
        self.sessions[session_id] = {
            "id": session_id,
            "course_id": course_id,
            "user_id": user_id,
        }
        return session_id

    async def insert_generated_exam(self, record: dict[str, Any]) -> uuid.UUID:
        exam_id = uuid.uuid4()
        self.generated_exams[exam_id] = {"id": exam_id, **record}
        return exam_id

    async def get_generated_exam(self, exam_id: uuid.UUID) -> dict[str, Any]:
        if exam_id not in self.generated_exams:
            raise ObjectNotFoundError(str(exam_id))
        return dict(self.generated_exams[exam_id])

    async def get_session(self, session_id: uuid.UUID) -> dict[str, Any]:
        if session_id not in self.sessions:
            raise ObjectNotFoundError(str(session_id))
        return dict(self.sessions[session_id])


@pytest.fixture
def fake_s3() -> FakeS3:
    return FakeS3()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def ingestion_repo() -> FakeIngestionRepo:
    return FakeIngestionRepo()


@pytest.fixture
def course_repo() -> FakeCourseCoreRepo:
    return FakeCourseCoreRepo()


@pytest.fixture
def exam_sim_repo() -> FakeExamSimRepo:
    return FakeExamSimRepo()
