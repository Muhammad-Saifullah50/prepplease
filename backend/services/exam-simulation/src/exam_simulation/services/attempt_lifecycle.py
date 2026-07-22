"""Attempt lifecycle service: start, save_answers, finish with FOR UPDATE idempotency."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from exambrain_shared.models.exam_sim import ExamSession, GeneratedExamRow
from exambrain_shared.redis import AttemptStateCache
from exambrain_shared.config import get_settings


class AttemptLifecycle:
    def __init__(
        self,
        db: AsyncSession,
        cache: AttemptStateCache,
    ) -> None:
        self._db = db
        self._cache = cache
        self._settings = get_settings()

    async def start(
        self, user_id: uuid.UUID, generated_exam_id: uuid.UUID, course_id: uuid.UUID
    ) -> ExamSession:
        existing = await self._find_active(user_id, course_id)
        if existing is not None:
            return existing

        result = await self._db.execute(
            select(GeneratedExamRow).where(
                GeneratedExamRow.id == generated_exam_id,
                GeneratedExamRow.status == "ready",
            )
        )
        exam = result.scalar_one_or_none()
        if exam is None:
            raise ValueError("Generated exam not found or not available")

        time_limit = exam.time_limit_minutes or self._settings.exam_attempt_default_timeout_minutes
        now = datetime.now(timezone.utc)
        deadline = now.replace(second=0, microsecond=0)
        try:
            from dateutil.relativedelta import relativedelta
            deadline += relativedelta(minutes=time_limit)
        except ImportError:
            deadline = deadline.replace(
                hour=deadline.hour + time_limit // 60,
                minute=deadline.minute + time_limit % 60,
            )

        session = ExamSession(
            user_id=user_id,
            course_id=course_id,
            generated_exam_id=generated_exam_id,
            exam_content=exam.content,
            status="active",
            started_at=now,
            deadline=deadline,
            time_limit_minutes=time_limit,
        )
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def _find_active(
        self, user_id: uuid.UUID, course_id: uuid.UUID
    ) -> ExamSession | None:
        result = await self._db.execute(
            select(ExamSession).where(
                ExamSession.user_id == user_id,
                ExamSession.course_id == course_id,
                ExamSession.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def save_answers(
        self,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
        answers: dict[str, str],
    ) -> ExamSession:
        session = await self._get_attempt(attempt_id, user_id)
        if session.status != "active":
            raise ValueError("Attempt is not active")
        merged = {**session.answers, **answers}
        session.answers = merged
        await self._db.commit()
        await self._db.refresh(session)
        remaining = self._compute_remaining(session)
        await self._cache.set_state(
            str(attempt_id),
            status=session.status,
            remaining_seconds=remaining,
            focus_violations=session.focus_violations,
            answers=merged,
            deadline=session.deadline.isoformat() if session.deadline else "",
            ttl_seconds=remaining,
        )
        return session

    async def finish(
        self, attempt_id: uuid.UUID, user_id: uuid.UUID, finished_by: str = "manual"
    ) -> ExamSession:
        result = await self._db.execute(
            select(ExamSession).where(
                ExamSession.id == attempt_id,
                ExamSession.user_id == user_id,
            ).with_for_update()
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError("Attempt not found")
        if session.ended_at is not None:
            return session
        now = datetime.now(timezone.utc)
        session.status = "submitted" if finished_by == "manual" else finished_by
        session.finished_by = finished_by
        session.ended_at = now
        await self._db.commit()
        await self._db.refresh(session)
        await self._cache.invalidate(str(attempt_id))
        return session

    def _compute_remaining(self, session: ExamSession) -> int:
        if session.deadline is None:
            return 0
        remaining = int((session.deadline - datetime.now(timezone.utc)).total_seconds())
        return max(remaining, 0)

    async def _get_attempt(
        self, attempt_id: uuid.UUID, user_id: uuid.UUID
    ) -> ExamSession:
        result = await self._db.execute(
            select(ExamSession).where(
                ExamSession.id == attempt_id,
                ExamSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError("Attempt not found")
        return session
