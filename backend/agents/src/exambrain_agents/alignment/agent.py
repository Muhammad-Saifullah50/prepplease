"""Instructor-alignment agent + code-level banding (FR-005..FR-007).

``enforce_banding`` re-applies the similarity bands to the agent's output
in deterministic code — an LLM can never merge a band-b match (R4).
"""

import json
import uuid
from typing import Any

from agents import Agent, function_tool

from exambrain_agents import config
from exambrain_agents.alignment.prompt import alignment_prompt
from exambrain_agents.schemas.alignment import Candidate, InstructorResolution
from exambrain_agents.tools.matching import (
    list_known_instructors,
    normalize_name,
    score_name_candidates,
)


def build_alignment_agent(*, repo: Any = None) -> Agent[Any]:
    """Build the alignment agent with its matching tools registered."""

    @function_tool(name_override="normalize_name")
    def normalize(raw: str) -> str:
        """Normalize an instructor name (case, honorifics, punctuation)."""
        return normalize_name(raw)

    @function_tool(name_override="list_known_instructors")
    async def list_known() -> str:
        """List stored professors as JSON: instructor_id, normalized_name,
        display_name."""
        rows = await list_known_instructors(repo=repo)
        return json.dumps(
            [
                {
                    "instructor_id": str(r["instructor_id"]),
                    "normalized_name": r["normalized_name"],
                    "display_name": r["display_name"],
                }
                for r in rows
            ]
        )

    @function_tool(name_override="score_name_candidates")
    def score(name: str, candidates: list[str]) -> str:
        """Similarity of a name vs candidate names, JSON sorted best-first."""
        return json.dumps(score_name_candidates(name, candidates))

    return Agent(
        name="alignment",
        instructions=alignment_prompt(
            config.alignment_auto_match_threshold(),
            config.alignment_review_threshold(),
        ),
        tools=[normalize, list_known, score],
        output_type=InstructorResolution,
        model=config.model_for_or_none("alignment"),
    )


def alignment_input(raw_name: str) -> str:
    """The agent's input: the raw name to resolve."""
    return json.dumps({"raw_name": raw_name})


def enforce_banding(
    resolution: InstructorResolution,
    scored_candidates: list[Candidate],
) -> InstructorResolution:
    """Re-apply FR-007 banding in code, overriding a misbehaving agent.

    ``scored_candidates`` are the deterministic rapidfuzz scores computed
    by the pipeline against all stored instructors.
    """
    auto = config.alignment_auto_match_threshold()
    review = config.alignment_review_threshold()

    best: Candidate | None = (
        max(scored_candidates, key=lambda c: c.score) if scored_candidates else None
    )
    band_b = [c for c in scored_candidates if review <= c.score < auto]

    # An agent-flagged review is honored even on an exact tie (edge case:
    # identical normalized names with conflicting context never auto-merge).
    if resolution.outcome == "needs_review":
        return resolution.model_copy(
            update={
                "matched_instructor_id": None,
                "candidates": resolution.candidates or scored_candidates,
            }
        )

    if best is not None and best.score >= auto:
        return resolution.model_copy(
            update={
                "outcome": "matched",
                "matched_instructor_id": best.instructor_id,
                "confidence": best.score,
                "candidates": [],
            }
        )
    if band_b:
        # Band b: never merged, regardless of what the agent decided.
        return resolution.model_copy(
            update={
                "outcome": "needs_review",
                "matched_instructor_id": None,
                "confidence": best.score if best else resolution.confidence,
                "candidates": band_b,
            }
        )
    return resolution.model_copy(
        update={"outcome": "created", "matched_instructor_id": None}
    )


def score_stored_instructors(
    raw_name: str, instructors: list[dict[str, Any]]
) -> list[Candidate]:
    """Deterministic candidate scores for banding enforcement (R4)."""
    normalized = normalize_name(raw_name)
    by_name: dict[str, uuid.UUID] = {i["normalized_name"]: i["id"] for i in instructors}
    scored = score_name_candidates(normalized, list(by_name))
    return [
        Candidate(
            instructor_id=by_name[s["candidate"]],
            normalized_name=s["candidate"],
            score=s["score"],
        )
        for s in scored
    ]
