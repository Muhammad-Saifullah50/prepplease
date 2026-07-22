"""Request/response schemas for exam attempt lifecycle."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StartAttemptRequest(BaseModel):
    generated_exam_id: uuid.UUID
    course_id: uuid.UUID


class Question(BaseModel):
    number: int
    text: str
    marks: float


class AttemptStateResponse(BaseModel):
    id: uuid.UUID
    status: str
    started_at: datetime
    deadline: datetime | None = None
    time_limit_minutes: int | None = None
    questions: list[Question] = []
    answers: dict[str, str] = {}
    remaining_seconds: int = 0
    focus_violations: int = 0
    focus_violations_limit: int = 3


class SaveAnswersRequest(BaseModel):
    answers: dict[str, str]


class SaveAnswersResponse(BaseModel):
    status: str
    saved_at: datetime


class FinishResponse(BaseModel):
    status: str
    finished_by: str
    ended_at: datetime
    grading_status: str = "queued"


class ErrorResponse(BaseModel):
    detail: str
    existing_attempt_id: uuid.UUID | None = None
