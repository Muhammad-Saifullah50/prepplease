"""ORM models owned by the course-core service (``course_core`` database)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from exambrain_shared.models import Base, TimestampMixin

SERVICE = "course_core"


class User(TimestampMixin, Base):
    """A registered ExamBrain user."""

    __tablename__ = "users"
    __table_args__ = {"info": {"service": SERVICE}}

    clerk_id: Mapped[str | None] = mapped_column(nullable=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class Instructor(TimestampMixin, Base):
    """A unique professor identity keyed by normalized name (FR-006)."""

    __tablename__ = "instructors"
    __table_args__ = {"info": {"service": SERVICE}}

    normalized_name: Mapped[str] = mapped_column(unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(nullable=False)


class Course(TimestampMixin, Base):
    """A course owned by a user."""

    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_user_id", "user_id"),
        Index("ix_courses_instructor_id", "instructor_id"),
        {"info": {"service": SERVICE}},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(nullable=False)
    code: Mapped[str | None] = mapped_column(nullable=True)
    instructor_name: Mapped[str | None] = mapped_column(nullable=True)
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instructors.id", ondelete="SET NULL"),
        nullable=True,  # at most one resolved identity per course (FR-006)
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paper_count: Mapped[int] = mapped_column(
        nullable=False, server_default=text("0")
    )


class InstructorResolution(TimestampMixin, Base):
    """Outcome of one alignment run for a course (FR-007)."""

    __tablename__ = "instructor_resolutions"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('matched', 'created', 'needs_review')",
            name="ck_instructor_resolutions_outcome",
        ),
        Index("ix_instructor_resolutions_course_id", "course_id"),
        {"info": {"service": SERVICE}},
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_name: Mapped[str] = mapped_column(nullable=False)
    normalized_name: Mapped[str] = mapped_column(nullable=False)
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instructors.id", ondelete="SET NULL"),
        nullable=True,  # set when matched or created
    )
    outcome: Mapped[str] = mapped_column(nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    candidates: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    needs_review: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )


class ExamBlueprint(TimestampMixin, Base):
    """A versioned exam structure derived from past papers (FR-005)."""

    __tablename__ = "exam_blueprints"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "version", name="uq_exam_blueprints_course_version"
        ),
        {"info": {"service": SERVICE}},
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    structure: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_past_paper_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )


class Result(TimestampMixin, Base):
    """Evaluation outcome for one exam session (identifier-only session ref)."""

    __tablename__ = "results"
    __table_args__ = (
        Index("ix_results_user_id", "user_id"),
        Index("ix_results_course_id", "course_id"),
        {"info": {"service": SERVICE}},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    question_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    aggregate_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    weak_topics: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
