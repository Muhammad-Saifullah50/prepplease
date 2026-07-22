"""Focus violation API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from exambrain_shared.db import get_session as get_db
from exambrain_shared.redis import AttemptStateCache

from exam_simulation.dependencies import get_attempt_state_cache, get_current_user
from exam_simulation.schemas.focus import FocusViolationResponse
from exam_simulation.services.focus_tracker import FocusTracker

router = APIRouter(prefix="/api/v1/exam-attempts", tags=["focus"])


@router.post("/{attempt_id}/focus-violations")
async def report_focus_violation(
    attempt_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    cache: AttemptStateCache = Depends(get_attempt_state_cache),
) -> FocusViolationResponse:
    tracker = FocusTracker(db, cache)
    try:
        return await tracker.report_violation(attempt_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
