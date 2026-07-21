"""ORM model owned by the exam-simulation service (``exam_sim`` database)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from exambrain_shared.models import Base, TimestampMixin

SERVICE = "exam_sim"


class ExamSession(TimestampMixin, Base):
    """Durable record of one exam attempt (live state lives in Redis)."""

    __tablename__ = "exam_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'submitted', 'locked_out', 'expired')",
            name="ck_exam_sessions_status",
        ),
        Index("ix_exam_sessions_user_id", "user_id"),
        Index("ix_exam_sessions_status", "status"),
        {"info": {"service": SERVICE}},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # identifier-only ref (course_core DB)
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # identifier-only ref
    )
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # identifier-only ref
    )
    exam_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, server_default=text("'active'"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    focus_violations: Mapped[int] = mapped_column(
        nullable=False, server_default=text("0")
    )


class GeneratedExamRow(TimestampMixin, Base):
    """A stored original mock exam with its rubric (Phase 2 agents)."""

    __tablename__ = "generated_exams"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'needs_review')",
            name="ck_generated_exams_status",
        ),
        Index("ix_generated_exams_course_id", "course_id"),
        Index("ix_generated_exams_status", "status"),
        {"info": {"service": SERVICE}},
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # identifier-only ref (course_core DB)
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # identifier-only ref
    )
    blueprint_version: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rubric: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, server_default=text("'ready'"))
    needs_review_reasons: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
