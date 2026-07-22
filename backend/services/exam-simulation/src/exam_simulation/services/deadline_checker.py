"""Background task that enforces attempt deadlines."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from exambrain_shared.config import get_settings
from exambrain_shared.models.exam_sim import ExamSession

logger = logging.getLogger(__name__)


class DeadlineChecker:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._settings = get_settings()
        self._running = False

    async def start(self) -> None:
        self._running = True
        await self._catch_up_missed_deadlines()
        asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False

    async def _catch_up_missed_deadlines(self) -> None:
        async with self._session_factory() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(ExamSession).where(
                    ExamSession.status == "active",
                    ExamSession.deadline < now,
                )
            )
            expired = result.scalars().all()
            for session in expired:
                session.status = "expired"
                session.finished_by = "deadline"
                session.ended_at = now
            await db.commit()
            if expired:
                logger.info("DeadlineChecker caught up %d expired attempts", len(expired))

    async def _poll_loop(self) -> None:
        interval = self._settings.exam_deadline_poll_interval_seconds
        while self._running:
            try:
                await self._check_and_finish_expired()
            except Exception:
                logger.exception("DeadlineChecker poll iteration failed")
            await asyncio.sleep(interval)

    async def _check_and_finish_expired(self) -> None:
        async with self._session_factory() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(ExamSession).where(
                    ExamSession.status == "active",
                    ExamSession.deadline < now,
                )
            )
            expired = result.scalars().all()
            for session in expired:
                session.status = "expired"
                session.finished_by = "deadline"
                session.ended_at = now
            if expired:
                await db.commit()
                logger.info("DeadlineChecker auto-finished %d attempts", len(expired))
