"""Request/response schemas for focus violation tracking."""

from datetime import datetime

from pydantic import BaseModel


class FocusViolationResponse(BaseModel):
    focus_violations: int
    focus_violations_limit: int
    violations_remaining: int
    status: str
    finished_by: str | None = None
    ended_at: datetime | None = None
