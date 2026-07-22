"""Generator agent output schema (contracts/agent-outputs.md)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExamQuestion(BaseModel):
    """One generated question, grounded in course chunks (FR-012)."""

    model_config = ConfigDict(frozen=True)

    number: str
    text: str
    marks: float
    topic: str
    source_chunk_ids: list[UUID]  # ≥1 (SC-005)


class ExamSection(BaseModel):
    """One exam section mirroring the blueprint layout."""

    model_config = ConfigDict(frozen=True)

    name: str
    question_type: str
    instructions: str | None = None
    questions: list[ExamQuestion]


class RubricEntry(BaseModel):
    """Grading guidance for one question (FR-013)."""

    model_config = ConfigDict(frozen=True)

    question_number: str
    expected_points: list[str]  # ≥1
    marks: float
    source_chunk_ids: list[UUID]


class GeneratedExam(BaseModel):
    """A complete original mock exam with rubric (FR-011..FR-013)."""

    model_config = ConfigDict(frozen=True)

    sections: list[ExamSection]
    total_marks: float
    time_limit_minutes: int | None = None
    rubric: list[RubricEntry]  # exactly one per question
    ungrounded_topics: list[str] = Field(default_factory=list)
