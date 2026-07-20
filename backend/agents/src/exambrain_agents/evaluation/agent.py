"""TA-evaluation agent (FR-016).

No tools: the exam, rubric, and answers are passed as input. Answers are
embedded as quoted JSON data — the prompt frames them as untrusted
(prompt-injection edge case).
"""

import json
from typing import Any

from agents import Agent

from exambrain_agents import config
from exambrain_agents.evaluation.prompt import EVALUATION_PROMPT_V1
from exambrain_agents.schemas.evaluation import EvaluationOutput


def build_evaluation_agent() -> Agent[Any]:
    """Build the evaluation agent (input-only, no tools)."""
    return Agent(
        name="evaluation",
        instructions=EVALUATION_PROMPT_V1,
        tools=[],
        output_type=EvaluationOutput,
        model=config.model_for_or_none("evaluation"),
    )


def evaluation_input(
    exam_content: dict[str, Any],
    rubric: list[dict[str, Any]],
    answers: list[dict[str, Any]],
) -> str:
    """Serialize exam + rubric + answers as the agent's input.

    Answers are nested JSON values — quoted data, never instructions.
    """
    return json.dumps(
        {"exam": exam_content, "rubric": rubric, "answers": answers}
    )
