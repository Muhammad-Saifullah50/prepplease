"""Ingestion-DB repository: past-paper lifecycle + chunk persistence.

All persistence for the ingestion database lives here (Constitution VII,
FR-019 — never in tools). Chunk replacement is atomic per source so
re-processing is idempotent (FR-004).
"""

import uuid
from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from exambrain_shared.db import get_session_factory
from exambrain_shared.errors import ObjectNotFoundError
from exambrain_shared.models.ingestion import DocumentChunk, PastPaper


class Embedder(Protocol):
    """The LLMClient.embed surface the repository depends on."""

    async def embed(self, text: str, **kwargs: Any) -> list[float]: ...


class IngestionRepository:
    """Async repository over ``past_papers`` and ``document_chunks``."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        database_url: str | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory(database_url)

    async def get_paper(self, paper_id: uuid.UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            paper = await session.get(PastPaper, paper_id)
            if paper is None:
                raise ObjectNotFoundError(str(paper_id))
            return _paper_dict(paper)

    async def mark_processing(self, paper_id: uuid.UUID) -> None:
        async with self._session_factory() as session, session.begin():
            paper = await session.get(PastPaper, paper_id)
            if paper is None:
                raise ObjectNotFoundError(str(paper_id))
            paper.processing_status = "processing"

    async def mark_completed(
        self,
        paper_id: uuid.UUID,
        *,
        parsing_confidence: float,
        needs_review: bool,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            paper = await session.get(PastPaper, paper_id)
            if paper is None:
                raise ObjectNotFoundError(str(paper_id))
            paper.processing_status = "completed"
            paper.failure_reason = None
            paper.parsing_confidence = parsing_confidence  # type: ignore[assignment]
            paper.needs_review = needs_review

    async def mark_failed(self, paper_id: uuid.UUID, reason: str) -> None:
        async with self._session_factory() as session, session.begin():
            paper = await session.get(PastPaper, paper_id)
            if paper is None:
                raise ObjectNotFoundError(str(paper_id))
            paper.processing_status = "failed"
            paper.failure_reason = reason

    async def replace_chunks(
        self,
        *,
        course_id: uuid.UUID,
        source_s3_key: str,
        past_paper_id: uuid.UUID | None,
        chunks: list[dict[str, Any]],
    ) -> int:
        """Delete-and-rewrite one source's chunks in one txn (FR-003/004)."""
        async with self._session_factory() as session, session.begin():
            await session.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.source_s3_key == source_s3_key
                )
            )
            for chunk in chunks:
                session.add(
                    DocumentChunk(
                        course_id=course_id,
                        past_paper_id=past_paper_id,
                        source_s3_key=source_s3_key,
                        content=chunk["content"],
                        position=chunk["position"],
                        hierarchy=chunk["hierarchy"],
                        embedding=chunk.get("embedding"),
                    )
                )
        return len(chunks)

    async def eligible_papers(self, course_id: uuid.UUID) -> list[dict[str, Any]]:
        """Completed, non-needs-review papers for blueprinting (FR-009)."""
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(PastPaper).where(
                    PastPaper.course_id == course_id,
                    PastPaper.processing_status == "completed",
                    PastPaper.needs_review.is_(False),
                )
            )
            return [_paper_dict(p) for p in rows]

    async def chunks_for_paper(self, paper_id: uuid.UUID) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.past_paper_id == paper_id)
                .order_by(DocumentChunk.position)
            )
            return [_chunk_dict(c) for c in rows]

    async def course_has_content(self, course_id: uuid.UUID) -> bool:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(DocumentChunk.id)
                .where(DocumentChunk.course_id == course_id)
                .limit(1)
            )
            return row is not None

    async def existing_chunk_ids(
        self, course_id: uuid.UUID, chunk_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Which of ``chunk_ids`` exist for this course (citation check)."""
        if not chunk_ids:
            return set()
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(DocumentChunk.id).where(
                    DocumentChunk.course_id == course_id,
                    DocumentChunk.id.in_(chunk_ids),
                )
            )
            return set(rows)

    async def search_chunks(
        self,
        course_id: uuid.UUID,
        embedding: list[float],
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Course-scoped pgvector cosine search (read-only, FR-012)."""
        async with self._session_factory() as session:
            distance = DocumentChunk.embedding.cosine_distance(embedding)
            rows = (
                await session.execute(
                    select(DocumentChunk, distance.label("distance"))
                    .where(
                        DocumentChunk.course_id == course_id,
                        DocumentChunk.embedding.is_not(None),
                    )
                    .order_by(distance)
                    .limit(limit)
                )
            ).all()
            return [
                {
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "hierarchy": chunk.hierarchy,
                    "similarity": 1.0 - float(dist),
                }
                for chunk, dist in rows
            ]


def _paper_dict(paper: PastPaper) -> dict[str, Any]:
    return {
        "id": paper.id,
        "course_id": paper.course_id,
        "s3_key": paper.s3_key,
        "processing_status": paper.processing_status,
        "failure_reason": paper.failure_reason,
        "parsing_confidence": (
            float(paper.parsing_confidence)
            if paper.parsing_confidence is not None
            else None
        ),
        "needs_review": paper.needs_review,
    }


def _chunk_dict(chunk: DocumentChunk) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "course_id": chunk.course_id,
        "past_paper_id": chunk.past_paper_id,
        "source_s3_key": chunk.source_s3_key,
        "content": chunk.content,
        "position": chunk.position,
        "hierarchy": chunk.hierarchy,
        "embedding": chunk.embedding,
    }
