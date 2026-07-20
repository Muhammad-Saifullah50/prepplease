"""Evaluation agent output schema (contracts/agent-outputs.md)."""

from pydantic import BaseModel, ConfigDict, Field


class QuestionScore(BaseModel):
    """One graded question with point-by-point feedback (FR-016)."""

    model_config = ConfigDict(frozen=True)

    question_number: str
    score: float = Field(ge=0.0)  # ≤ max_marks enforced in pipeline (FR-017)
    max_marks: float
    credited_points: list[str]
    missing_points: list[str]
    feedback: str


class EvaluationOutput(BaseModel):
    """Complete grading of one exam session (FR-016/FR-017)."""

    model_config = ConfigDict(frozen=True)

    question_scores: list[QuestionScore]  # one per exam question
    aggregate_score: float
    max_score: float
    weak_topics: list[str]
