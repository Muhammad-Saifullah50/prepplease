"""Papers list endpoint (PastPaper data owned by ingestion DB)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from exambrain_agents.repositories.ingestion import IngestionRepository
from exambrain_shared.db import get_session_factory
from ingestion_pipeline.auth import require_auth

router = APIRouter(prefix="/v1", tags=["papers"])


@router.get("/courses/{course_id}/papers")
async def list_papers(
    course_id: uuid.UUID,
    user: Annotated[dict[str, Any], Depends(require_auth)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    ingestion_repo = IngestionRepository(session_factory=session_factory)

    papers = await ingestion_repo.list_papers_for_course(course_id)

    return {
        "papers": [
            {
                "id": str(p["id"]),
                "status": p["status"],
                "file_type": p["file_type"],
                "file_name": p["file_name"],
                "created_at": p["created_at"],
                "processing_completed_at": p["processing_completed_at"],
            }
            for p in papers
        ]
    }
