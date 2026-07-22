"""Processing status polling endpoint (FR-012, FR-023)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from exambrain_agents.repositories.ingestion import IngestionRepository
from exambrain_shared.db import get_session_factory
from exambrain_shared.errors import ObjectNotFoundError
from ingestion_pipeline.auth import require_auth

router = APIRouter(prefix="/v1", tags=["status"])


@router.get("/papers/{paper_id}/status")
async def get_paper_status(
    paper_id: uuid.UUID,
    user: Annotated[dict[str, Any], Depends(require_auth)],
) -> dict[str, Any]:
    session_factory = get_session_factory()
    ingestion_repo = IngestionRepository(session_factory=session_factory)

    try:
        paper = await ingestion_repo.get_paper(paper_id)
    except ObjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "reason": "Paper not found"},
        ) from None

    elapsed = None
    created = paper.get("created_at")
    if created is not None:
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        elapsed = int((datetime.now(UTC) - created).total_seconds())

    return {
        "paper_id": str(paper_id),
        "status": paper["processing_status"],
        "elapsed_seconds": elapsed,
        "failure_reason": paper.get("failure_reason"),
    }
