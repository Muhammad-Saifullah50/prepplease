"""ORM models owned by the ingestion-pipeline service (``ingestion`` database)."""

import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from exambrain_shared.models import Base, TimestampMixin

SERVICE = "ingestion"

EMBEDDING_DIMENSIONS = 1024  # Titan Text Embeddings V2 (research R2/R5)


class PastPaper(TimestampMixin, Base):
    """An uploaded past exam paper and its processing lifecycle."""

    __tablename__ = "past_papers"
    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_past_papers_processing_status",
        ),
        Index("ix_past_papers_course_id", "course_id"),
        Index("ix_past_papers_processing_status", "processing_status"),
        {"info": {"service": SERVICE}},
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False  # identifier-only ref (course_core DB)
    )
    s3_key: Mapped[str] = mapped_column(nullable=False)
    academic_term: Mapped[str | None] = mapped_column(nullable=True)
    year: Mapped[int | None] = mapped_column(nullable=True)
    processing_status: Mapped[str] = mapped_column(
        nullable=False, server_default=text("'pending'")
    )
    failure_reason: Mapped[str | None] = mapped_column(nullable=True)


class DocumentChunk(TimestampMixin, Base):
    """A chunk of course material or past-paper text with its embedding."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_course_id", "course_id"),
        Index("ix_document_chunks_past_paper_id", "past_paper_id"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"info": {"service": SERVICE}},
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False  # identifier-only ref
    )
    past_paper_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("past_papers.id", ondelete="CASCADE"),
        nullable=True,  # NULL for course-material chunks
    )
    source_s3_key: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    hierarchy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    embedding: Mapped[Any | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True  # NULL until embedded
    )
