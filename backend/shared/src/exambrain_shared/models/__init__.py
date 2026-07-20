"""ORM models for all ExamBrain services on the shared declarative ``Base``.

Every model lives here (importable by any service or agent) but is tagged
with its owning service via ``__table_args__ = {"info": {"service": ...}}``.
Each service's Alembic ``env.py`` filters ``Base.metadata`` on that tag so
per-service migrations never touch another service's tables (FR-004,
research R4).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from exambrain_shared.db import Base

__all__ = [
    "Base",
    "TimestampMixin",
    "Course",
    "DocumentChunk",
    "ExamBlueprint",
    "ExamSession",
    "PastPaper",
    "Result",
    "User",
]


class TimestampMixin:
    """UUID primary key + created/updated timestamps shared by all tables."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


from exambrain_shared.models.course_core import (  # noqa: E402
    Course,
    ExamBlueprint,
    Result,
    User,
)
from exambrain_shared.models.exam_sim import ExamSession  # noqa: E402
from exambrain_shared.models.ingestion import DocumentChunk, PastPaper  # noqa: E402
