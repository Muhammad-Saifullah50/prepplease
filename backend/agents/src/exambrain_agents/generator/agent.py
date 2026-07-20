"""Exam-generator agent (FR-011..FR-013).

The agent retrieves grounding chunks itself via the read-only
``search_course_content`` tool (FR-012); the pipeline validates the result
against the blueprint before persisting (FR-014).
"""

import json
import uuid
from typing import Any

from agents import Agent, function_tool

from exambrain_agents import config
from exambrain_agents.generator.prompt import GENERATOR_PROMPT_V1
from exambrain_agents.schemas.generation import GeneratedExam
from exambrain_agents.tools.retrieval import search_course_content


def build_generator_agent(
    course_id: uuid.UUID, *, embedder: Any = None, repo: Any = None
) -> Agent[Any]:
    """Build the generator agent with a course-scoped retrieval tool."""

    @function_tool(name_override="search_course_content")
    async def search(query: str, limit: int = 8) -> str:
        """Semantic search over this course's ingested content.

        Returns matching chunks as JSON: chunk_id, content, hierarchy,
        similarity — best match first. Use the returned chunk_id values
        for source_chunk_ids.
        """
        results = await search_course_content(
            course_id, query, limit=limit, embedder=embedder, repo=repo
        )
        return json.dumps(
            [
                {
                    "chunk_id": str(r["chunk_id"]),
                    "content": r["content"],
                    "hierarchy": r["hierarchy"],
                    "similarity": round(float(r["similarity"]), 4),
                }
                for r in results
            ]
        )

    return Agent(
        name="generator",
        instructions=GENERATOR_PROMPT_V1,
        tools=[search],
        output_type=GeneratedExam,
        model=config.model_for_or_none("generator"),
    )


def generator_input(blueprint_structure: dict[str, Any]) -> str:
    """Serialize the latest blueprint as the agent's input (FR-011)."""
    return json.dumps({"blueprint": blueprint_structure})
