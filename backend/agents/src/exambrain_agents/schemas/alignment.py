"""Alignment agent output schema (contracts/agent-outputs.md).

Lives in ``schemas`` (earliest-consumer rule): the blueprint agent's
output embeds :class:`InstructorResolution` for instructor sightings.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Candidate(BaseModel):
    """A scored existing-instructor candidate for an ambiguous match."""

    model_config = ConfigDict(frozen=True)

    instructor_id: UUID
    normalized_name: str
    score: float = Field(ge=0.0, le=1.0)  # rapidfuzz similarity


class InstructorResolution(BaseModel):
    """Outcome of resolving one raw instructor name (FR-005..FR-007)."""

    model_config = ConfigDict(frozen=True)

    raw_name: str
    normalized_name: str
    outcome: Literal["matched", "created", "needs_review"]
    matched_instructor_id: UUID | None = None  # set iff outcome == "matched"
    confidence: float = Field(ge=0.0, le=1.0)
    candidates: list[Candidate] = Field(
        default_factory=list  # non-empty iff needs_review
    )
