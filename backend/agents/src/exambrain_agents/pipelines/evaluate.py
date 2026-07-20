"""``evaluate_submission`` pipeline (contracts/pipelines.md, US4).

Grades stored answers rubric-strictly, validates the arithmetic (FR-017)
with one corrective retry, then upserts exactly one result per session
(FR-016). The needs-review marker is carried inside the question_scores
JSONB envelope (data-model.md — no schema change this phase).
"""

import math
from decimal import Decimal
from typing import Any
from uuid import UUID

from agents.models.interface import Model
from pydantic import BaseModel

from exambrain_agents.evaluation.agent import (
    build_evaluation_agent,
    evaluation_input,
)
from exambrain_agents.runner import run_agent_with_corrective_retry
from exambrain_agents.schemas.evaluation import EvaluationOutput, QuestionScore

SCORE_TOLERANCE = 0.01


class SubmittedAnswer(BaseModel):
    """One stored answer; ``text`` None/empty means unanswered."""

    question_number: str
    text: str | None


class EvaluationRecord(BaseModel):
    """Persisted grading outcome (contracts/pipelines.md)."""

    exam_session_id: UUID
    question_scores: list[QuestionScore]
    aggregate_score: Decimal
    max_score: Decimal
    weak_topics: list[str]
    needs_review: bool


async def evaluate_submission(
    exam_session_id: UUID,
    generated_exam_id: UUID,
    answers: list[dict[str, Any]] | list[SubmittedAnswer],
    *,
    course_repo: Any = None,
    exam_sim_repo: Any = None,
    evaluation_model: Model | None = None,
) -> EvaluationRecord:
    """Grade one completed exam session (FR-016/FR-017)."""
    if course_repo is None:
        from exambrain_agents.repositories.course_core import CourseCoreRepository

        course_repo = CourseCoreRepository()
    if exam_sim_repo is None:
        from exambrain_agents.repositories.exam_sim import ExamSimRepository

        exam_sim_repo = ExamSimRepository()

    session = await exam_sim_repo.get_session(exam_session_id)
    exam = await exam_sim_repo.get_generated_exam(generated_exam_id)

    normalized_answers = [
        a.model_dump() if isinstance(a, SubmittedAnswer) else dict(a)
        for a in answers
    ]
    expected = _question_allocations(exam["content"])

    output: EvaluationOutput
    output, failures = await run_agent_with_corrective_retry(
        build_evaluation_agent(),
        evaluation_input(exam["content"], exam["rubric"], normalized_answers),
        lambda out: _validate_arithmetic(out, expected),
        model=evaluation_model,
    )
    needs_review = bool(failures)

    question_scores_payload: dict[str, Any] = {
        "scores": [s.model_dump(mode="json") for s in output.question_scores],
    }
    if needs_review:
        # Needs-review envelope inside the JSONB payload (data-model.md).
        question_scores_payload["needs_review"] = True
        question_scores_payload["reasons"] = failures

    await course_repo.upsert_result(
        exam_session_id,
        {
            "user_id": session["user_id"],
            "course_id": session["course_id"],
            "question_scores": question_scores_payload,
            "aggregate_score": Decimal(str(output.aggregate_score)),
            "max_score": Decimal(str(output.max_score)),
            "weak_topics": output.weak_topics,
        },
    )
    return EvaluationRecord(
        exam_session_id=exam_session_id,
        question_scores=output.question_scores,
        aggregate_score=Decimal(str(output.aggregate_score)),
        max_score=Decimal(str(output.max_score)),
        weak_topics=output.weak_topics,
        needs_review=needs_review,
    )


def _question_allocations(exam_content: dict[str, Any]) -> dict[str, float]:
    """Question number → mark allocation from the stored exam content."""
    return {
        q["number"]: float(q["marks"])
        for section in exam_content.get("sections", [])
        for q in section.get("questions", [])
    }


def _validate_arithmetic(
    output: EvaluationOutput, expected: dict[str, float]
) -> list[str]:
    """FR-017: scores in range, aggregate = Σ scores, max = Σ max_marks."""
    failures: list[str] = []

    scored_numbers = {s.question_number for s in output.question_scores}
    for number in expected:
        if number not in scored_numbers:
            failures.append(f"question {number} missing from the evaluation")

    for score in output.question_scores:
        allocation = expected.get(score.question_number)
        if allocation is not None and not math.isclose(
            score.max_marks, allocation, abs_tol=SCORE_TOLERANCE
        ):
            failures.append(
                f"question {score.question_number} max_marks "
                f"{score.max_marks} != exam allocation {allocation}"
            )
        if score.score < -SCORE_TOLERANCE or score.score > score.max_marks + (
            SCORE_TOLERANCE
        ):
            failures.append(
                f"question {score.question_number} score {score.score} "
                f"outside [0, {score.max_marks}]"
            )

    total = sum(s.score for s in output.question_scores)
    if not math.isclose(output.aggregate_score, total, abs_tol=SCORE_TOLERANCE):
        failures.append(
            f"aggregate_score {output.aggregate_score} != sum of scores {total}"
        )
    max_total = sum(s.max_marks for s in output.question_scores)
    if not math.isclose(output.max_score, max_total, abs_tol=SCORE_TOLERANCE):
        failures.append(
            f"max_score {output.max_score} != sum of max_marks {max_total}"
        )
    return failures
