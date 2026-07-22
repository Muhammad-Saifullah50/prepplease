"""Attempt lifecycle API endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exambrain_shared.db import get_session as get_db
from exambrain_shared.models.exam_sim import ExamSession
from exambrain_shared.redis import AttemptStateCache

from exam_simulation.dependencies import get_attempt_state_cache, get_current_user
from exam_simulation.schemas.attempts import (
    AttemptStateResponse,
    ErrorResponse,
    FinishResponse,
    Question,
    SaveAnswersRequest,
    SaveAnswersResponse,
    StartAttemptRequest,
)
from exam_simulation.services.attempt_lifecycle import AttemptLifecycle

router = APIRouter(prefix="/api/v1/exam-attempts", tags=["attempts"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_attempt(
    body: StartAttemptRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    cache: AttemptStateCache = Depends(get_attempt_state_cache),
) -> AttemptStateResponse:
    lifecycle = AttemptLifecycle(db, cache)
    try:
        session = await lifecycle.start(
            user_id=user_id,
            generated_exam_id=body.generated_exam_id,
            course_id=body.course_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    questions = _extract_questions(session.exam_content)
    return _to_state_response(session, questions)


@router.get("/{attempt_id}/state")
async def poll_state(
    attempt_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    cache: AttemptStateCache = Depends(get_attempt_state_cache),
) -> AttemptStateResponse:
    cached = await cache.get_state(str(attempt_id))
    if cached is not None:
        questions = _extract_questions({})
        return AttemptStateResponse(
            id=attempt_id,
            status=cached.get("status", "active"),
            started_at=datetime.now(timezone.utc),
            questions=questions,
            answers={},
            remaining_seconds=int(cached.get("remaining_seconds", 0)),
            focus_violations=int(cached.get("focus_violations", 0)),
        )
    result = await db.execute(
        select(ExamSession).where(
            ExamSession.id == attempt_id,
            ExamSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    questions = _extract_questions(session.exam_content)
    remaining = _compute_remaining(session)
    if session.status == "active":
        await cache.set_state(
            str(attempt_id),
            status=session.status,
            remaining_seconds=remaining,
            focus_violations=session.focus_violations,
            answers=session.answers,
            deadline=session.deadline.isoformat() if session.deadline else "",
            ttl_seconds=remaining,
        )
    return AttemptStateResponse(
        id=session.id,
        status=session.status,
        started_at=session.started_at,
        deadline=session.deadline,
        time_limit_minutes=session.time_limit_minutes,
        questions=questions,
        answers=session.answers if session.status == "active" else {},
        remaining_seconds=remaining if session.status == "active" else 0,
        focus_violations=session.focus_violations,
    )


@router.put("/{attempt_id}/answers")
async def save_answers(
    attempt_id: uuid.UUID,
    body: SaveAnswersRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    cache: AttemptStateCache = Depends(get_attempt_state_cache),
) -> SaveAnswersResponse:
    lifecycle = AttemptLifecycle(db, cache)
    try:
        await lifecycle.save_answers(attempt_id, user_id, body.answers)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return SaveAnswersResponse(status="saved", saved_at=datetime.now(timezone.utc))


@router.post("/{attempt_id}/finish")
async def finish_attempt(
    attempt_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    cache: AttemptStateCache = Depends(get_attempt_state_cache),
) -> FinishResponse:
    lifecycle = AttemptLifecycle(db, cache)
    try:
        session = await lifecycle.finish(attempt_id, user_id, finished_by="manual")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return FinishResponse(
        status=session.status,
        finished_by=session.finished_by or "manual",
        ended_at=session.ended_at or datetime.now(timezone.utc),
    )


def _extract_questions(content: dict) -> list[Question]:
    questions = content.get("questions", content.get("sections", []))
    if isinstance(questions, list) and questions and isinstance(questions[0], dict):
        if "questions" in questions[0]:
            result = []
            for section in questions:
                for q in section.get("questions", []):
                    result.append(Question(
                        number=q.get("number", 0),
                        text=q.get("text", q.get("question", "")),
                        marks=float(q.get("marks", 0)),
                    ))
            return result

    return []


def _compute_remaining(session: ExamSession) -> int:
    if session.deadline is None:
        return 0
    remaining = int((session.deadline - datetime.now(timezone.utc)).total_seconds())
    return max(remaining, 0)


def _to_state_response(
    session: ExamSession, questions: list[Question]
) -> AttemptStateResponse:
    remaining = _compute_remaining(session)
    return AttemptStateResponse(
        id=session.id,
        status=session.status,
        started_at=session.started_at,
        deadline=session.deadline,
        time_limit_minutes=session.time_limit_minutes,
        questions=questions,
        answers=(session.answers or {}) if session.status == "active" else {},
        remaining_seconds=remaining if session.status == "active" else 0,
        focus_violations=session.focus_violations or 0,
    )
