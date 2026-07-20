"""Parsing agent output schema (contracts/agent-outputs.md)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ParsedQuestion(BaseModel):
    """One question as printed on a past paper."""

    model_config = ConfigDict(frozen=True)

    number: str  # "1", "2(a)", "Q3.ii"
    text: str
    marks: float | None = None
    page: int | None = None


class ParsedSlide(BaseModel):
    """One slide of course material."""

    model_config = ConfigDict(frozen=True)

    index: int
    text: str
    page: int | None = None


class ParsedSection(BaseModel):
    """A titled group of questions (past paper) or slides (material)."""

    model_config = ConfigDict(frozen=True)

    title: str  # "Section A", "Short Questions"
    instructions: str | None = None
    questions: list[ParsedQuestion] = Field(default_factory=list)
    slides: list[ParsedSlide] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    """Structured text extracted from one stored file (FR-001/FR-002).

    Low ``confidence`` never fails the parse — the pipeline flags the paper
    ``needs_review`` when it falls below the settings threshold.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["past_paper", "course_material"]
    document_type: Literal["pdf_digital", "pdf_scanned", "pptx"]
    instructor_name_seen: str | None = None  # name printed on the paper
    sections: list[ParsedSection]  # ≥1 for a completed parse
    total_marks: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
