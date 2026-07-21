"""Opt-in live-provider smoke tests (T053, FR-024).

Marked ``live_llm`` — deselected by default; run explicitly with::

    uv run pytest -m live_llm

Requires real provider credentials (LLM_MODEL + AWS trio or LLM_API_KEY).
One tiny prompt per agent proves the LiteLLM path end-to-end.
"""

import pytest

from exambrain_agents import config
from exambrain_agents.runner import run_agent
from exambrain_shared.config import get_settings

pytestmark = pytest.mark.live_llm


def _configured() -> bool:
    s = get_settings()
    return bool(
        s.llm_model
        and (
            s.llm_api_key
            or (s.aws_access_key_id and s.aws_secret_access_key and s.aws_region)
        )
    )


requires_creds = pytest.mark.skipif(
    not _configured(), reason="LLM provider credentials not configured"
)


@requires_creds
async def test_parsing_agent_live() -> None:
    from exambrain_agents.parsing.agent import build_parsing_agent, parsing_input
    from exambrain_agents.schemas.parsing import ParsedDocument
    from exambrain_agents.tools.extraction import PageText

    pages = [
        PageText(
            page=1,
            text="Section A. Q1. Define entropy. [5 marks]",
            char_count=40,
        )
    ]
    result = await run_agent(
        build_parsing_agent(), parsing_input("past_paper", "pdf_digital", pages)
    )
    assert isinstance(result, ParsedDocument)
    assert result.sections


@requires_creds
async def test_alignment_agent_live() -> None:
    from exambrain_agents.alignment.agent import (
        alignment_input,
        build_alignment_agent,
    )
    from exambrain_agents.schemas.alignment import InstructorResolution
    from tests.conftest import FakeCourseCoreRepo

    repo = FakeCourseCoreRepo()
    repo.add_instructor("abdul rahman", "Abdul Rahman")
    result = await run_agent(
        build_alignment_agent(repo=repo), alignment_input("Dr. A. Rahman")
    )
    assert isinstance(result, InstructorResolution)


@requires_creds
async def test_evaluation_agent_live() -> None:
    from exambrain_agents.evaluation.agent import (
        build_evaluation_agent,
        evaluation_input,
    )
    from exambrain_agents.schemas.evaluation import EvaluationOutput

    exam = {
        "sections": [
            {
                "name": "A",
                "question_type": "short_answer",
                "questions": [{"number": "1", "text": "Define entropy.", "marks": 5.0}],
            }
        ],
        "total_marks": 5.0,
    }
    rubric = [
        {
            "question_number": "1",
            "expected_points": ["measure of disorder"],
            "marks": 5.0,
            "source_chunk_ids": [],
        }
    ]
    answers = [{"question_number": "1", "text": "It measures disorder."}]
    result = await run_agent(
        build_evaluation_agent(), evaluation_input(exam, rubric, answers)
    )
    assert isinstance(result, EvaluationOutput)


@requires_creds
async def test_blueprint_agent_live() -> None:
    import uuid

    from exambrain_agents.blueprint.agent import (
        blueprint_input,
        build_blueprint_agent,
    )
    from exambrain_agents.schemas.blueprint import BlueprintStructure

    paper_id = uuid.uuid4()
    result = await run_agent(
        build_blueprint_agent(),
        blueprint_input(
            [
                (
                    paper_id,
                    "Section A: two short questions, 5 marks each. "
                    "Q1 Define entropy [5]. Q2 State the second law [5].",
                )
            ]
        ),
    )
    assert isinstance(result, BlueprintStructure)
    assert result.sections


@requires_creds
async def test_generator_agent_live() -> None:
    import uuid

    from exambrain_agents.generator.agent import (
        build_generator_agent,
        generator_input,
    )
    from exambrain_agents.schemas.generation import GeneratedExam
    from tests.conftest import FakeEmbedder, FakeIngestionRepo

    course_id = uuid.uuid4()
    repo = FakeIngestionRepo()
    embedder = FakeEmbedder()
    emb = await embedder.embed("entropy measures disorder; units J/K")
    await repo.replace_chunks(
        course_id=course_id,
        source_s3_key="k",
        past_paper_id=None,
        chunks=[
            {
                "content": "entropy measures disorder; units J/K",
                "position": 0,
                "hierarchy": {"kind": "course_material", "slide": 1},
                "embedding": emb,
            }
        ],
    )
    blueprint = {
        "sections": [
            {
                "name": "Section A",
                "question_type": "short_answer",
                "question_count": 1,
                "marks_each": 5.0,
                "total_marks": 5.0,
            }
        ],
        "total_marks": 5.0,
        "marks_distribution": {"short_answer": 1.0},
        "topic_weights": [{"topic": "entropy", "weight": 1.0}],
        "phrasing_style": ["terse"],
        "evidence": [],
        "instructor_sightings": [],
        "confidence": 0.9,
    }
    result = await run_agent(
        build_generator_agent(course_id, embedder=embedder, repo=repo),
        generator_input(blueprint),
    )
    assert isinstance(result, GeneratedExam)


@requires_creds
def test_model_resolution_uses_settings() -> None:
    """FR-021 sanity: every agent resolves a LitellmModel from settings."""
    for name in ("parsing", "alignment", "blueprint", "generator", "evaluation"):
        model = config.model_for(name)
        assert model.model
