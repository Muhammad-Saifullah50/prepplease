# Contract: Agent Outputs

**Feature**: 003-phase2-agents | Module: `exambrain_agents.schemas`

Each agent declares `output_type` = its schema; the SDK enforces schema-valid final output, and pipelines re-validate domain invariants before persisting (FR-018). All schemas are frozen Pydantic v2 models.

## Parsing agent → `ParsedDocument`

```python
class ParsedQuestion(BaseModel):
    number: str                     # "1", "2(a)", "Q3.ii"
    text: str
    marks: float | None
    page: int | None

class ParsedSection(BaseModel):
    title: str                      # "Section A", "Short Questions"
    instructions: str | None
    questions: list[ParsedQuestion] # past papers
    slides: list[ParsedSlide]       # course material (index, text, page)

class ParsedDocument(BaseModel):
    kind: Literal["past_paper", "course_material"]
    document_type: Literal["pdf_digital", "pdf_scanned", "pptx"]
    instructor_name_seen: str | None   # name printed on the paper, if any
    sections: list[ParsedSection]      # ≥1
    total_marks: float | None
    confidence: float                  # [0,1]; < settings threshold ⇒ needs_review
```

Invariants: sections non-empty for `completed` status; confidence in [0,1]. Low confidence does not fail the parse — it flags the paper (FR-002).

## Alignment agent → `InstructorResolution`

```python
class Candidate(BaseModel):
    instructor_id: UUID
    normalized_name: str
    score: float                    # [0,1] rapidfuzz similarity

class InstructorResolution(BaseModel):
    raw_name: str
    normalized_name: str
    outcome: Literal["matched", "created", "needs_review"]
    matched_instructor_id: UUID | None   # set iff outcome == "matched"
    confidence: float
    candidates: list[Candidate]          # non-empty iff needs_review
```

Invariants (re-enforced in pipeline code — agent output that violates banding is corrected, never trusted, FR-007):
- `matched` requires best score ≥ auto-match threshold (default 0.90).
- best score in [0.70, 0.90) ⇒ outcome coerced to `needs_review`; never merged.
- all scores < 0.70 ⇒ `created`.

## Blueprint agent → `BlueprintStructure`

```python
class BlueprintSection(BaseModel):
    name: str
    question_type: str              # "mcq", "short_answer", "long_answer", "numerical", ...
    question_count: int
    marks_each: float | None
    total_marks: float

class TopicWeight(BaseModel):
    topic: str
    weight: float                   # weights sum ≈ 1.0 (±0.01)

class PaperEvidence(BaseModel):
    past_paper_id: UUID
    observations: list[str]

class BlueprintStructure(BaseModel):
    sections: list[BlueprintSection]
    total_marks: float
    marks_distribution: dict[str, float]     # question_type → share
    topic_weights: list[TopicWeight]
    phrasing_style: list[str]                # style characteristics
    evidence: list[PaperEvidence]            # one per source paper (FR-009)
    instructor_sightings: list[InstructorResolution]  # resolved via alignment tool (FR-008)
    confidence: float                        # lower on thin/contradictory evidence
```

Invariants: `total_marks` = Σ section totals; every source paper appears in `evidence`; topic weights sum ≈ 1.0. Recent papers weighted over older on contradiction (edge case); confidence reflects agreement.

Tool contract (FR-008): the alignment agent is attached as tool `resolve_instructor_sighting(raw_name: str) -> InstructorResolution` — the blueprint agent MUST call it for any instructor name differing from the course's recorded instructor, never resolve names itself.

## Generator agent → `GeneratedExam`

```python
class ExamQuestion(BaseModel):
    number: str
    text: str
    marks: float
    topic: str
    source_chunk_ids: list[UUID]    # ≥1 (FR-012, SC-005)

class ExamSection(BaseModel):
    name: str
    question_type: str
    instructions: str | None
    questions: list[ExamQuestion]

class RubricEntry(BaseModel):
    question_number: str
    expected_points: list[str]      # ≥1
    marks: float
    source_chunk_ids: list[UUID]

class GeneratedExam(BaseModel):
    sections: list[ExamSection]
    total_marks: float
    rubric: list[RubricEntry]       # exactly one per question (FR-013)
    ungrounded_topics: list[str]    # topics lacking course content (edge case)
```

Pipeline validation (FR-014): section layout/question types/counts/marks match the blueprint version; total marks equal; every question cites ≥1 chunk id that exists for the course; rubric covers every question. Non-empty `ungrounded_topics` ⇒ persist `needs_review` with reasons.

## Evaluation agent → `EvaluationOutput`

```python
class QuestionScore(BaseModel):
    question_number: str
    score: float                    # 0 ≤ score ≤ max_marks
    max_marks: float
    credited_points: list[str]
    missing_points: list[str]
    feedback: str

class EvaluationOutput(BaseModel):
    question_scores: list[QuestionScore]   # one per exam question
    aggregate_score: float
    max_score: float
    weak_topics: list[str]
```

Pipeline validation (FR-017): every exam question present; each score within allocation; `aggregate_score == Σ scores`; `max_score == Σ max_marks`; unanswered → score 0, feedback notes "not attempted". Answer text is untrusted data (prompt-injection edge case) — the agent prompt frames answers as quoted material.

## Corrective-retry protocol (shared)

On pipeline validation failure the agent is re-run **once** with the original input plus a structured failure list ("Your previous output failed validation: …"). Second failure ⇒ persist with `needs_review` + reasons (FR-014/FR-017); never silently accepted, never lost (SC-004/006).
