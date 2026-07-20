"""Course-core-DB repository: blueprints (US1) + instructors/results (US2/US4).

Blueprint versions are written inside a per-course
``pg_advisory_xact_lock`` so extraction runs are serialized and version
numbers computed race-free (FR-010, research R6).
"""

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from exambrain_shared.db import get_session_factory
from exambrain_shared.errors import ObjectNotFoundError
from exambrain_shared.models.course_core import Course, ExamBlueprint


class CourseCoreRepository:
    """Async repository over the course-core database."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        database_url: str | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory(database_url)

    async def get_course(self, course_id: uuid.UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            course = await session.get(Course, course_id)
            if course is None:
                raise ObjectNotFoundError(str(course_id))
            return {
                "id": course.id,
                "instructor_name": course.instructor_name,
                "instructor_id": getattr(course, "instructor_id", None),
            }

    async def write_blueprint_version(
        self,
        course_id: uuid.UUID,
        structure: dict[str, Any],
        source_past_paper_ids: list[uuid.UUID],
    ) -> tuple[uuid.UUID, int]:
        """Write immutable version max+1 under the course advisory lock."""
        async with self._session_factory() as session, session.begin():
            # xact-scoped: released automatically at commit/rollback (R6).
            await session.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtextextended('blueprint:' || :course_id, 0))"
                ),
                {"course_id": str(course_id)},
            )
            current = await session.scalar(
                select(ExamBlueprint.version)
                .where(ExamBlueprint.course_id == course_id)
                .order_by(ExamBlueprint.version.desc())
                .limit(1)
            )
            version = (current or 0) + 1
            blueprint = ExamBlueprint(
                course_id=course_id,
                version=version,
                structure=structure,
                source_past_paper_ids=[str(p) for p in source_past_paper_ids],
            )
            session.add(blueprint)
            await session.flush()
            return blueprint.id, version

    async def latest_blueprint(
        self, course_id: uuid.UUID
    ) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            blueprint = await session.scalar(
                select(ExamBlueprint)
                .where(ExamBlueprint.course_id == course_id)
                .order_by(ExamBlueprint.version.desc())
                .limit(1)
            )
            if blueprint is None:
                return None
            return {
                "id": blueprint.id,
                "course_id": blueprint.course_id,
                "version": blueprint.version,
                "structure": blueprint.structure,
                "source_past_paper_ids": blueprint.source_past_paper_ids,
            }
