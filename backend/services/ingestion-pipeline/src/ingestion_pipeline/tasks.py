"""Background ingestion runner with per-course serialization (FR-011, FR-013)."""

import asyncio
import logging
import uuid
from collections import defaultdict

from exambrain_agents.repositories.ingestion import IngestionRepository
from exambrain_shared.s3 import S3Adapter

logger = logging.getLogger(__name__)

_course_locks: dict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)


async def run_ingestion(
    paper_id: uuid.UUID,
    course_id: uuid.UUID,
    s3_key: str,
    ingestion_repo: IngestionRepository,
) -> None:
    lock = _course_locks[course_id]
    async with lock:
        try:
            await ingestion_repo.mark_processing(paper_id)

            from exambrain_agents.pipelines.ingest import ingest_course_file

            await ingest_course_file(
                course_id=course_id,
                s3_key=s3_key,
                kind="past_paper",
                past_paper_id=paper_id,
                s3=S3Adapter(),
                ingestion_repo=ingestion_repo,
            )

            logger.info(
                "ingestion completed",
                extra={"paper_id": str(paper_id), "course_id": str(course_id)},
            )
        except Exception:
            logger.exception(
                "ingestion failed",
                extra={"paper_id": str(paper_id), "course_id": str(course_id)},
            )
            try:
                await ingestion_repo.mark_failed(
                    paper_id,
                    reason="Internal processing error",
                )
            except Exception:
                logger.exception(
                    "failed to mark paper as failed",
                    extra={"paper_id": str(paper_id)},
                )
