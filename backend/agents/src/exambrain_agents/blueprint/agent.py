"""Blueprint-extraction agent + domain validation (FR-009, T025/T046).

The alignment agent is attached as the ``resolve_instructor_sighting``
tool (FR-008, research R2) when a tool is supplied by the pipeline — US2
integration; without it the agent runs with no tools.
"""

import json
import math
from typing import Any
from uuid import UUID

from agents import Agent
from agents.agent_output import AgentOutputSchema
from agents.tool import Tool

from exambrain_agents import config
from exambrain_agents.blueprint.prompt import BLUEPRINT_PROMPT_V1
from exambrain_agents.schemas.blueprint import BlueprintStructure

TOPIC_WEIGHT_TOLERANCE = 0.01
MARKS_TOLERANCE = 0.01


def build_blueprint_agent(*, alignment_tool: Tool | None = None) -> Agent[Any]:
    """Build the blueprint agent, optionally with alignment-as-tool."""
    return Agent(
        name="blueprint",
        instructions=BLUEPRINT_PROMPT_V1,
        tools=[alignment_tool] if alignment_tool is not None else [],
        # Non-strict: `marks_distribution` is a free-form mapping, which
        # strict JSON schemas disallow; Pydantic still validates the output.
        output_type=AgentOutputSchema(BlueprintStructure, strict_json_schema=False),
        model=config.model_for_or_none("blueprint"),
    )


def blueprint_input(papers: list[tuple[UUID, str]]) -> str:
    """Serialize the eligible papers as the agent's input.

    ``papers`` is ``[(past_paper_id, structured_text), ...]`` for the
    course's full eligible set (FR-009).
    """
    return json.dumps(
        {
            "papers": [
                {"past_paper_id": str(paper_id), "text": text}
                for paper_id, text in papers
            ]
        }
    )


def validate_blueprint(
    structure: BlueprintStructure, source_paper_ids: list[UUID]
) -> list[str]:
    """Domain invariants enforced in pipeline code (contracts, FR-009)."""
    failures: list[str] = []
    if not structure.sections:
        failures.append("blueprint has no sections")

    section_total = sum(s.total_marks for s in structure.sections)
    if not math.isclose(structure.total_marks, section_total, abs_tol=MARKS_TOLERANCE):
        failures.append(
            f"total_marks {structure.total_marks} != sum of section totals "
            f"{section_total}"
        )

    weight_sum = sum(w.weight for w in structure.topic_weights)
    if structure.topic_weights and not math.isclose(
        weight_sum, 1.0, abs_tol=TOPIC_WEIGHT_TOLERANCE
    ):
        failures.append(f"topic weights sum to {weight_sum:.3f}, expected ~1.0")

    evidenced = {e.past_paper_id for e in structure.evidence}
    for paper_id in source_paper_ids:
        if paper_id not in evidenced:
            failures.append(f"missing evidence for source paper {paper_id}")
    return failures
