"""Blueprint agent + validation tests (T017 — TDD critical path, FR-009)."""

import uuid

from exambrain_agents.blueprint.agent import (
    blueprint_input,
    build_blueprint_agent,
    validate_blueprint,
)
from exambrain_agents.runner import run_agent
from exambrain_agents.schemas.blueprint import (
    BlueprintSection,
    BlueprintStructure,
    PaperEvidence,
    TopicWeight,
)
from exambrain_agents.testing import FakeModel, FinalOutput

PAPER_A = uuid.uuid4()
PAPER_B = uuid.uuid4()


def make_structure(
    *,
    paper_ids: list[uuid.UUID],
    weights: list[float] | None = None,
    total_marks: float = 50.0,
    section_totals: list[float] | None = None,
    confidence: float = 0.85,
) -> BlueprintStructure:
    weights = weights if weights is not None else [0.6, 0.4]
    section_totals = section_totals or [20.0, 30.0]
    return BlueprintStructure(
        sections=[
            BlueprintSection(
                name=f"Section {i}",
                question_type="short_answer",
                question_count=2,
                marks_each=t / 2,
                total_marks=t,
            )
            for i, t in enumerate(section_totals)
        ],
        total_marks=total_marks,
        marks_distribution={"short_answer": 1.0},
        topic_weights=[
            TopicWeight(topic=f"topic-{i}", weight=w) for i, w in enumerate(weights)
        ],
        phrasing_style=["imperative", "derivation-heavy"],
        evidence=[
            PaperEvidence(past_paper_id=p, observations=["2 sections"])
            for p in paper_ids
        ],
        instructor_sightings=[],
        confidence=confidence,
    )


async def test_merge_across_multiple_papers_returns_structure() -> None:
    structure = make_structure(paper_ids=[PAPER_A, PAPER_B])
    model = FakeModel(outputs=[FinalOutput(structure)])
    result = await run_agent(
        build_blueprint_agent(),
        blueprint_input([(PAPER_A, "paper A text"), (PAPER_B, "paper B text")]),
        model=model,
    )
    assert isinstance(result, BlueprintStructure)
    assert {e.past_paper_id for e in result.evidence} == {PAPER_A, PAPER_B}


def test_validate_accepts_clean_structure() -> None:
    structure = make_structure(paper_ids=[PAPER_A, PAPER_B])
    assert validate_blueprint(structure, [PAPER_A, PAPER_B]) == []


def test_validate_requires_evidence_for_every_paper() -> None:
    structure = make_structure(paper_ids=[PAPER_A])  # B missing
    failures = validate_blueprint(structure, [PAPER_A, PAPER_B])
    assert any(str(PAPER_B) in f for f in failures)


def test_validate_topic_weights_must_sum_to_one() -> None:
    structure = make_structure(paper_ids=[PAPER_A], weights=[0.5, 0.2])
    failures = validate_blueprint(structure, [PAPER_A])
    assert any("weight" in f.lower() for f in failures)


def test_validate_total_marks_invariant() -> None:
    structure = make_structure(
        paper_ids=[PAPER_A], total_marks=99.0, section_totals=[20.0, 30.0]
    )
    failures = validate_blueprint(structure, [PAPER_A])
    assert any("total" in f.lower() for f in failures)


async def test_single_paper_low_confidence_case() -> None:
    """Edge case: one paper still yields a blueprint, confidence reflects it."""
    structure = make_structure(paper_ids=[PAPER_A], confidence=0.4)
    model = FakeModel(outputs=[FinalOutput(structure)])
    result = await run_agent(
        build_blueprint_agent(),
        blueprint_input([(PAPER_A, "the only paper")]),
        model=model,
    )
    assert result.confidence == 0.4
    assert validate_blueprint(result, [PAPER_A]) == []


def test_prompt_covers_merge_evidence_and_recency_rules() -> None:
    """The versioned prompt encodes merge/evidence/recency/confidence rules."""
    from exambrain_agents.blueprint.prompt import BLUEPRINT_PROMPT_V1

    text = BLUEPRINT_PROMPT_V1.lower()
    for keyword in ("merge", "evidence", "recent", "confidence"):
        assert keyword in text, f"prompt missing '{keyword}' guidance"


async def test_sighting_routed_through_alignment_tool() -> None:
    """FR-008: the blueprint agent resolves sightings via the attached
    alignment agent-as-tool, and the resolution surfaces in its output."""
    from exambrain_agents.pipelines.ingest import _alignment_tool
    from exambrain_agents.schemas.alignment import InstructorResolution
    from exambrain_agents.testing import ToolCall
    from tests.conftest import FakeCourseCoreRepo

    repo = FakeCourseCoreRepo()
    sighting = InstructorResolution(
        raw_name="Dr. Someone New",
        normalized_name="someone new",
        outcome="created",
        matched_instructor_id=None,
        confidence=1.0,
        candidates=[],
    )
    # The inner alignment agent inherits the blueprint run's FakeModel via
    # as_tool; script: (1) blueprint calls the tool, (2) alignment answers,
    # (3) blueprint finishes with the sighting embedded.
    structure = make_structure(paper_ids=[PAPER_A]).model_copy(
        update={"instructor_sightings": [sighting]}
    )
    model = FakeModel(
        outputs=[
            ToolCall(
                "resolve_instructor_sighting", {"input": "Dr. Someone New"}
            ),
            FinalOutput(sighting),  # inner alignment agent's final output
            FinalOutput(structure),
        ]
    )
    tool = _alignment_tool(model, repo)
    assert tool.name == "resolve_instructor_sighting"
    agent = build_blueprint_agent(alignment_tool=tool)
    result = await run_agent(
        agent, blueprint_input([(PAPER_A, "paper text")]), model=model
    )
    assert result.instructor_sightings == [sighting]
