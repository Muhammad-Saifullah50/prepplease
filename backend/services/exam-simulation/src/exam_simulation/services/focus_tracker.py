"""Focus violation tracking and lockout service."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exambrain_shared.config import get_settings
from exambrain_shared.models.exam_sim import ExamSession
from exambrain_shared.redis import AttemptStateCache

from exam_simulation.schemas.focus import FocusViolationResponse


class FocusTracker:
    def __init__(self, db: AsyncSession, cache: AttemptStateCache) -> None:
        self._db = db
        self._cache = cache
        self._settings = get_settings()

    async def report_violation(
        self, attempt_id: uuid.UUID, user_id: uuid.UUID
    ) -> FocusViolationResponse:
        result = await self._db.execute(
            select(ExamSession).where(
                ExamSession.id == attempt_id,
                ExamSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError("Attempt not found")
        if session.status != "active":
            raise ValueError("Attempt is not active")

        limit = self._settings.exam_focus_violation_limit
        session.focus_violations += 1

        if session.focus_violations >= limit:
            now = datetime.now(timezone.utc)
            session.status = "locked_out"
            session.finished_by = "lockout"
            session.ended_at = now
            await self._db.commit()
            await self._cache.invalidate(str(attempt_id))
            return FocusViolationResponse(
                focus_violations=session.focus_violations,
                focus_violations_limit=limit,
                violations_remaining=0,
                status="locked_out",
                finished_by="lockout",
                ended_at=now,
            )

        await self._db.commit()
        remaining = max(0, limit - session.focus_violations)
        return FocusViolationResponse(
            focus_violations=session.focus_violations,
            focus_violations_limit=limit,
            violations_remaining=remaining,
            status="active",
        )
