"""Alignment-agent tests via FakeModel + banding coercion (T040, US2)."""

import uuid

from exambrain_agents.alignment.agent import (
    alignment_input,
    build_alignment_agent,
    enforce_banding,
)
from exambrain_agents.runner import run_agent
from exambrain_agents.schemas.alignment import Candidate, InstructorResolution
from exambrain_agents.testing import FakeModel, FinalOutput, ToolCall
from tests.conftest import FakeCourseCoreRepo


def resolution(
    outcome: str,
    *,
    confidence: float,
    matched: uuid.UUID | None = None,
    candidates: list[Candidate] | None = None,
) -> InstructorResolution:
    return InstructorResolution(
        raw_name="Dr. A. Rahman",
        normalized_name="a rahman",
        outcome=outcome,  # type: ignore[arg-type]
        matched_instructor_id=matched,
        confidence=confidence,
        candidates=candidates or [],
    )


async def test_high_similarity_match(course_repo: FakeCourseCoreRepo) -> None:
    """US2 AS1: ≥0.90 → matched to the existing instructor."""
    iid = course_repo.add_instructor("abdul rahman", "Abdul Rahman")
    model = FakeModel(
        outputs=[
            ToolCall("list_known_instructors", {}),
            ToolCall(
                "score_name_candidates",
                {"name": "a rahman", "candidates": ["abdul rahman"]},
            ),
            FinalOutput(resolution("matched", confidence=0.95, matched=iid)),
        ]
    )
    agent = build_alignment_agent(repo=course_repo)
    result = await run_agent(agent, alignment_input("Dr. A. Rahman"), model=model)
    assert result.outcome == "matched"
    assert result.matched_instructor_id == iid
    assert model.turns == 3  # real tool loop exercised


async def test_no_match_creates_new(course_repo: FakeCourseCoreRepo) -> None:
    """US2 AS2: all scores < 0.70 → created."""
    model = FakeModel(
        outputs=[
            ToolCall("list_known_instructors", {}),
            FinalOutput(resolution("created", confidence=1.0)),
        ]
    )
    result = await run_agent(
        build_alignment_agent(repo=course_repo),
        alignment_input("Dr. Someone New"),
        model=model,
    )
    assert result.outcome == "created"


async def test_gray_zone_needs_review_with_candidates(
    course_repo: FakeCourseCoreRepo,
) -> None:
    """US2 AS3: band-b match → needs_review with the candidate list."""
    iid = course_repo.add_instructor("abdul raheem", "Abdul Raheem")
    cands = [Candidate(instructor_id=iid, normalized_name="abdul raheem", score=0.8)]
    model = FakeModel(
        outputs=[
            FinalOutput(resolution("needs_review", confidence=0.8, candidates=cands))
        ]
    )
    result = await run_agent(
        build_alignment_agent(repo=course_repo),
        alignment_input("Dr. A. Rahim"),
        model=model,
    )
    assert result.outcome == "needs_review"
    assert result.candidates == cands


class TestEnforceBanding:
    """FR-007 hard rule: banding re-enforced in code, agent never trusted."""

    def setup_method(self) -> None:
        self.iid = uuid.uuid4()

    def cands(self, score: float) -> list[Candidate]:
        return [
            Candidate(
                instructor_id=self.iid, normalized_name="abdul rahman", score=score
            )
        ]

    def test_band_b_agent_match_coerced_to_needs_review(self) -> None:
        """A misbehaving agent 'matched' at 0.80 is coerced — never merged."""
        bad = resolution("matched", confidence=0.80, matched=self.iid)
        fixed = enforce_banding(bad, self.cands(0.80))
        assert fixed.outcome == "needs_review"
        assert fixed.matched_instructor_id is None
        assert fixed.candidates  # candidate list preserved for review

    def test_band_a_match_stands(self) -> None:
        good = resolution("matched", confidence=0.95, matched=self.iid)
        fixed = enforce_banding(good, self.cands(0.95))
        assert fixed.outcome == "matched"
        assert fixed.matched_instructor_id == self.iid

    def test_band_a_agent_create_coerced_to_match(self) -> None:
        """Agent 'created' despite a ≥0.90 candidate → coerced to matched."""
        bad = resolution("created", confidence=1.0)
        fixed = enforce_banding(bad, self.cands(0.93))
        assert fixed.outcome == "matched"
        assert fixed.matched_instructor_id == self.iid

    def test_band_c_create_stands(self) -> None:
        low = resolution("created", confidence=1.0)
        fixed = enforce_banding(low, self.cands(0.4))
        assert fixed.outcome == "created"

    def test_no_candidates_creates(self) -> None:
        fixed = enforce_banding(resolution("created", confidence=1.0), [])
        assert fixed.outcome == "created"

    def test_exact_tie_conflicting_context_needs_review(self) -> None:
        """Edge case: exact normalized-name tie is surfaced for review when
        the agent flags it — code never silently merges over a review flag."""
        tie = resolution("needs_review", confidence=1.0, candidates=self.cands(1.0))
        fixed = enforce_banding(tie, self.cands(1.0))
        assert fixed.outcome == "needs_review"
        assert fixed.matched_instructor_id is None
