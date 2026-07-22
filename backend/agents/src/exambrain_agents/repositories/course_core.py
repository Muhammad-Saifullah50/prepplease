"""Course-core-DB repository: blueprints (US1) + instructors/results (US2/US4).

Blueprint versions are written inside a per-course
``pg_advisory_xact_lock`` so extraction runs are serialized and version
numbers computed race-free (FR-010, research R6).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from exambrain_shared.db import get_session_factory
from exambrain_shared.errors import ObjectNotFoundError
from exambrain_shared.models.course_core import (
    Course,
    ExamBlueprint,
    Instructor,
    InstructorResolution,
    Result,
    User,
)


class CourseCoreRepository:
    """Async repository over the course-core database."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        database_url: str | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory(database_url)

    async def list_courses(
        self, user_id: uuid.UUID, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            query = select(Course).where(Course.user_id == user_id)
            if not include_archived:
                query = query.where(Course.archived_at.is_(None))
            query = query.order_by(Course.created_at.desc())
            rows = await session.scalars(query)
            return [
                {
                    "id": c.id,
                    "title": c.title,
                    "code": c.code,
                    "instructor_name": c.instructor_name,
                    "paper_count": c.paper_count,
                    "archived_at": c.archived_at.isoformat() if c.archived_at else None,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in rows
            ]

    async def get_course(self, course_id: uuid.UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            course = await session.get(Course, course_id)
            if course is None:
                raise ObjectNotFoundError(str(course_id))
            return {
                "id": course.id,
                "user_id": course.user_id,
                "title": course.title,
                "code": course.code,
                "instructor_name": course.instructor_name,
                "instructor_id": getattr(course, "instructor_id", None),
                "archived_at": (
                    course.archived_at.isoformat() if course.archived_at else None
                ),
                "paper_count": course.paper_count,
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
                time_limit_minutes=structure.get("time_limit_minutes"),
            )
            session.add(blueprint)
            await session.flush()
            return blueprint.id, version

    # -- users (004-foundation-services auth) -------------------------------

    async def find_user_by_clerk_id(self, clerk_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(User).where(User.clerk_id == clerk_id)
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "clerk_id": row.clerk_id,
                "email": row.email,
                "display_name": row.display_name,
                "is_active": row.is_active,
                "preferences": row.preferences,
            }

    async def create_user(
        self, clerk_id: str, email: str, display_name: str
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            user = User(
                clerk_id=clerk_id,
                email=email,
                display_name=display_name or email.split("@")[0],
                is_active=True,
                preferences={},
            )
            session.add(user)
            await session.flush()
            return {
                "id": user.id,
                "clerk_id": user.clerk_id,
                "email": user.email,
                "display_name": user.display_name,
                "is_active": user.is_active,
                "preferences": user.preferences,
            }

    async def update_user_from_webhook(
        self, clerk_id: str, email: str | None, display_name: str | None
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(User).where(User.clerk_id == clerk_id)
            )
            if row is None:
                return
            if email is not None:
                row.email = email
            if display_name is not None:
                row.display_name = display_name

    async def deactivate_user(self, clerk_id: str) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.scalar(
                select(User).where(User.clerk_id == clerk_id)
            )
            if row is not None:
                row.is_active = False

    async def list_blueprints(
        self, course_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(ExamBlueprint)
                .where(ExamBlueprint.course_id == course_id)
                .order_by(ExamBlueprint.version.desc())
            )
            return [
                {
                    "version": b.version,
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                    "confidence_score": b.structure.get("confidence_score"),
                }
                for b in rows
            ]

    async def list_results(
        self, course_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(Result)
                .where(Result.course_id == course_id)
                .order_by(Result.created_at.desc())
            )
            return [
                {
                    "id": r.id,
                    "exam_session_id": r.exam_session_id,
                    "aggregate_score": float(r.aggregate_score),
                    "max_score": float(r.max_score),
                    "weak_topics": r.weak_topics,
                    "question_scores": r.question_scores,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    async def create_course(
        self, user_id: uuid.UUID, title: str, code: str | None = None,
        instructor_name: str | None = None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            course = Course(
                user_id=user_id,
                title=title,
                code=code,
                instructor_name=instructor_name,
            )
            session.add(course)
            await session.flush()
            return {
                "id": course.id,
                "title": course.title,
                "code": course.code,
                "instructor_name": course.instructor_name,
                "instructor_id": getattr(course, "instructor_id", None),
                "paper_count": course.paper_count,
                "archived_at": None,
                "created_at": (
                    course.created_at.isoformat() if course.created_at else None
                ),
            }

    async def update_course(
        self, course_id: uuid.UUID, **kwargs: Any
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            course = await session.get(Course, course_id)
            if course is None:
                raise ObjectNotFoundError(str(course_id))
            for key, value in kwargs.items():
                if value is not None and hasattr(course, key):
                    setattr(course, key, value)
            await session.flush()
            return {
                "id": course.id,
                "user_id": course.user_id,
                "title": course.title,
                "code": course.code,
                "instructor_name": course.instructor_name,
                "instructor_id": getattr(course, "instructor_id", None),
                "archived_at": (
                    course.archived_at.isoformat() if course.archived_at else None
                ),
                "paper_count": course.paper_count,
            }

    async def soft_delete_course(self, course_id: uuid.UUID) -> None:
        async with self._session_factory() as session, session.begin():
            course = await session.get(Course, course_id)
            if course is None:
                raise ObjectNotFoundError(str(course_id))
            if course.archived_at is not None:
                raise ValueError("already_archived")
            course.archived_at = datetime.now(UTC)

    async def latest_blueprint(self, course_id: uuid.UUID) -> dict[str, Any] | None:
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
                "time_limit_minutes": blueprint.time_limit_minutes,
            }

    # -- instructors / resolutions (US2, FR-005..FR-007) -------------------

    async def list_instructors(self) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            rows = await session.scalars(select(Instructor))
            return [
                {
                    "id": row.id,
                    "normalized_name": row.normalized_name,
                    "display_name": row.display_name,
                }
                for row in rows
            ]

    async def find_instructor_by_normalized_name(
        self, normalized_name: str
    ) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(Instructor).where(Instructor.normalized_name == normalized_name)
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "normalized_name": row.normalized_name,
                "display_name": row.display_name,
            }

    async def create_instructor(
        self, normalized_name: str, display_name: str
    ) -> uuid.UUID:
        async with self._session_factory() as session, session.begin():
            instructor = Instructor(
                normalized_name=normalized_name, display_name=display_name
            )
            session.add(instructor)
            await session.flush()
            return instructor.id

    async def save_resolution(
        self, course_id: uuid.UUID, resolution: dict[str, Any]
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                InstructorResolution(
                    course_id=course_id,
                    raw_name=resolution["raw_name"],
                    normalized_name=resolution["normalized_name"],
                    instructor_id=resolution.get("instructor_id"),
                    outcome=resolution["outcome"],
                    confidence=resolution["confidence"],
                    candidates=resolution.get("candidates", []),
                    needs_review=resolution["outcome"] == "needs_review",
                )
            )

    async def link_course_instructor(
        self, course_id: uuid.UUID, instructor_id: uuid.UUID
    ) -> None:
        """Link the course to its resolved identity (matched/created only)."""
        async with self._session_factory() as session, session.begin():
            course = await session.get(Course, course_id)
            if course is None:
                raise ObjectNotFoundError(str(course_id))
            course.instructor_id = instructor_id

    # -- results (US4, FR-016) ---------------------------------------------

    async def upsert_result(
        self, exam_session_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        """Exactly one result per session: update in place or insert."""
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(Result).where(Result.exam_session_id == exam_session_id)
            )
            if existing is not None:
                existing.question_scores = payload["question_scores"]
                existing.aggregate_score = payload["aggregate_score"]
                existing.max_score = payload["max_score"]
                existing.weak_topics = payload["weak_topics"]
                return
            session.add(
                Result(
                    user_id=payload["user_id"],
                    course_id=payload["course_id"],
                    exam_session_id=exam_session_id,
                    question_scores=payload["question_scores"],
                    aggregate_score=payload["aggregate_score"],
                    max_score=payload["max_score"],
                    weak_topics=payload["weak_topics"],
                )
            )
