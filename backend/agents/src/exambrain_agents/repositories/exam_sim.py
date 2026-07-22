"""Exam-sim-DB repository: generated exams + session lookups (FR-015)."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from exambrain_shared.db import get_session_factory
from exambrain_shared.errors import ObjectNotFoundError
from exambrain_shared.models.exam_sim import ExamSession, GeneratedExamRow


class ExamSimRepository:
    """Async repository over the exam-simulation database."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        database_url: str | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory(database_url)

    async def insert_generated_exam(self, record: dict[str, Any]) -> uuid.UUID:
        async with self._session_factory() as session, session.begin():
            row = GeneratedExamRow(
                course_id=record["course_id"],
                blueprint_id=record["blueprint_id"],
                blueprint_version=record["blueprint_version"],
                content=record["content"],
                rubric=record["rubric"],
                status=record["status"],
                needs_review_reasons=record["needs_review_reasons"],
                time_limit_minutes=record.get("time_limit_minutes"),
            )
            session.add(row)
            await session.flush()
            return row.id

    async def get_generated_exam(self, exam_id: uuid.UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            row = await session.get(GeneratedExamRow, exam_id)
            if row is None:
                raise ObjectNotFoundError(str(exam_id))
            return {
                "id": row.id,
                "course_id": row.course_id,
                "blueprint_id": row.blueprint_id,
                "blueprint_version": row.blueprint_version,
                "content": row.content,
                "rubric": row.rubric,
                "status": row.status,
                "needs_review_reasons": row.needs_review_reasons,
                "time_limit_minutes": row.time_limit_minutes,
            }

    async def get_session(self, session_id: uuid.UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            row = await session.get(ExamSession, session_id)
            if row is None:
                raise ObjectNotFoundError(str(session_id))
            return {
                "id": row.id,
                "user_id": row.user_id,
                "course_id": row.course_id,
            }
