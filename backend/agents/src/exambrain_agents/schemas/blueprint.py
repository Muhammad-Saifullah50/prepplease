"""Blueprint agent output schema (contracts/agent-outputs.md).

Embeds :class:`InstructorResolution` for instructor sightings resolved via
the alignment agent-as-tool (FR-008).
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from exambrain_agents.schemas.alignment import InstructorResolution


class BlueprintSection(BaseModel):
    """One structural section of the professor's exam fingerprint."""

    model_config = ConfigDict(frozen=True)

    name: str
    question_type: str  # "mcq", "short_answer", "long_answer", "numerical", ...
    question_count: int
    marks_each: float | None = None
    total_marks: float


class TopicWeight(BaseModel):
    """Relative topic emphasis; weights sum ≈ 1.0 across the blueprint."""

    model_config = ConfigDict(frozen=True)

    topic: str
    weight: float = Field(ge=0.0, le=1.0)


class PaperEvidence(BaseModel):
    """Per-source-paper observations backing the merged blueprint (FR-009)."""

    model_config = ConfigDict(frozen=True)

    past_paper_id: UUID
    observations: list[str]


class BlueprintStructure(BaseModel):
    """Merged structural fingerprint of how a professor writes exams."""

    model_config = ConfigDict(frozen=True)

    sections: list[BlueprintSection]
    total_marks: float
    marks_distribution: dict[str, float]  # question_type → share
    topic_weights: list[TopicWeight]
    phrasing_style: list[str]  # style characteristics
    evidence: list[PaperEvidence]  # one per source paper
    instructor_sightings: list[InstructorResolution] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)  # lower on thin/contradictory evidence
