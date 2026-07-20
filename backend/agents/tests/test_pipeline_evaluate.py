"""Evaluate-submission pipeline tests (T048 — TDD critical path, US4)."""

import uuid
from typing import Any

import pytest

from exambrain_agents.errors import AgentOutputError
from exambrain_agents.pipelines.evaluate import evaluate_submission
from exambrain_agents.schemas.evaluation import EvaluationOutput, QuestionScore
from exambrain_agents.testing import FakeModel, FinalOutput
from exambrain_shared.errors import ObjectNotFoundError
from tests.conftest import FakeCourseCoreRepo, FakeExamSimRepo

EXAM_CONTENT = {
    "sections": [
        {
            "name": "Section A",
            "question_type": "short_answer",
            "questions": [
                {"number": "1", "text": "Define entropy.", "marks": 5.0},
                {"number": "2", "text": "State the second law.", "marks": 5.0},
            ],
        }
    ],
    "total_marks": 10.0,
}
RUBRIC = [
    {
        "question_number": "1",
        "expected_points": ["measure of disorder"],
        "marks": 5.0,
        "source_chunk_ids": [],
    },
    {
        "question_number": "2",
        "expected_points": ["never decreases"],
        "marks": 5.0,
        "source_chunk_ids": [],
    },
]
ANSWERS = [
    {"question_number": "1", "text": "Disorder measure."},
    {"question_number": "2", "text": None},
]


def scores(q1: float = 4.0, q2: float = 0.0) -> list[QuestionScore]:
    return [
        QuestionScore(
            question_number="1",
            score=q1,
            max_marks=5.0,
            credited_points=["measure of disorder"],
            missing_points=[],
            feedback="Good.",
        ),
        QuestionScore(
            question_number="2",
            score=q2,
            max_marks=5.0,
            credited_points=[],
            missing_points=["never decreases"],
            feedback="Not attempted.",
        ),
    ]


def evaluation(
    question_scores: list[QuestionScore] | None = None,
    *,
    aggregate: float | None = None,
    max_score: float | None = None,
) -> EvaluationOutput:
    qs = question_scores if question_scores is not None else scores()
    return EvaluationOutput(
        question_scores=qs,
        aggregate_score=(
            aggregate if aggregate is not None else sum(s.score for s in qs)
        ),
        max_score=(
            max_score if max_score is not None else sum(s.max_marks for s in qs)
        ),
        weak_topics=["thermodynamics"],
    )


@pytest.fixture
async def env(
    course_repo: FakeCourseCoreRepo, exam_sim_repo: FakeExamSimRepo
) -> dict[str, Any]:
    course_id = course_repo.add_course()
    session_id = exam_sim_repo.add_session(course_id, uuid.uuid4())
    exam_id = await exam_sim_repo.insert_generated_exam(
        {
            "course_id": course_id,
            "blueprint_id": uuid.uuid4(),
            "blueprint_version": 1,
            "content": EXAM_CONTENT,
            "rubric": RUBRIC,
            "status": "ready",
            "needs_review_reasons": [],
        }
    )
    return {
        "course_repo": course_repo,
        "exam_sim_repo": exam_sim_repo,
        "session_id": session_id,
        "exam_id": exam_id,
    }


async def run(env: dict[str, Any], model: FakeModel) -> Any:
    return await evaluate_submission(
        env["session_id"],
        env["exam_id"],
        ANSWERS,
        course_repo=env["course_repo"],
        exam_sim_repo=env["exam_sim_repo"],
        evaluation_model=model,
    )


async def test_valid_evaluation_persists_one_result(env: dict[str, Any]) -> None:
    """US4 AS1: result with scores, feedback, aggregate, weak topics."""
    model = FakeModel(outputs=[FinalOutput(evaluation())])
    record = await run(env, model)
    assert record.needs_review is False
    assert float(record.aggregate_score) == 4.0
    assert float(record.max_score) == 10.0
    assert record.weak_topics == ["thermodynamics"]
    assert env["session_id"] in env["course_repo"].results


async def test_arithmetic_validation_score_in_range(env: dict[str, Any]) -> None:
    """FR-017: score > max_marks fails both attempts → needs_review."""
    bad = evaluation(scores(q1=7.0))  # 7 > 5 allocation
    model = FakeModel(outputs=[FinalOutput(bad), FinalOutput(bad)])
    record = await run(env, model)
    assert record.needs_review is True
    stored = env["course_repo"].results[env["session_id"]]
    assert stored["question_scores"]["needs_review"] is True
    assert stored["question_scores"]["reasons"]


async def test_aggregate_mismatch_retry_then_recover(env: dict[str, Any]) -> None:
    """FR-017: aggregate != Σ scores → one corrective retry, then clean."""
    bad = evaluation(aggregate=9.5)  # Σ = 4.0
    good = evaluation()
    model = FakeModel(outputs=[FinalOutput(bad), FinalOutput(good)])
    record = await run(env, model)
    assert record.needs_review is False
    assert model.turns == 2


async def test_max_score_mismatch_flags(env: dict[str, Any]) -> None:
    bad = evaluation(max_score=42.0)  # Σ max = 10
    model = FakeModel(outputs=[FinalOutput(bad), FinalOutput(bad)])
    record = await run(env, model)
    assert record.needs_review is True


async def test_exactly_one_result_upsert_on_repeat(env: dict[str, Any]) -> None:
    """FR-016: repeated calls upsert the same session row."""
    await run(env, FakeModel(outputs=[FinalOutput(evaluation())]))
    better = evaluation(scores(q1=5.0))
    record = await run(env, FakeModel(outputs=[FinalOutput(better)]))
    assert len(env["course_repo"].results) == 1
    assert float(record.aggregate_score) == 5.0


async def test_unknown_exam_raises(env: dict[str, Any]) -> None:
    with pytest.raises(ObjectNotFoundError):
        await evaluate_submission(
            env["session_id"],
            uuid.uuid4(),
            ANSWERS,
            course_repo=env["course_repo"],
            exam_sim_repo=env["exam_sim_repo"],
            evaluation_model=FakeModel(outputs=[]),
        )


async def test_unknown_session_raises(env: dict[str, Any]) -> None:
    with pytest.raises(ObjectNotFoundError):
        await evaluate_submission(
            uuid.uuid4(),
            env["exam_id"],
            ANSWERS,
            course_repo=env["course_repo"],
            exam_sim_repo=env["exam_sim_repo"],
            evaluation_model=FakeModel(outputs=[]),
        )


async def test_agent_failure_no_write(env: dict[str, Any]) -> None:
    """FR-023: a typed agent failure persists nothing (turn-limit mapping
    itself is covered in test_runner; the evaluation agent has no tools, so
    a malformed final output is the reachable failure here)."""
    model = FakeModel(outputs=[FinalOutput('{"not": "an evaluation"}')] * 2)
    with pytest.raises(AgentOutputError):
        await run(env, model)
    assert env["course_repo"].results == {}
