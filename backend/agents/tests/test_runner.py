"""Tests for run_agent error translation, retry helper, and log redaction.

Verifies T008 (FakeModel drives the real SDK loop) and T009 (runner
wrapper): turn-limit and schema errors map to typed platform errors
(FR-023), the corrective-retry helper retries exactly once (R11), and log
records never carry content (FR-022).
"""

import logging

import pytest
from agents import Agent, function_tool
from pydantic import BaseModel

from exambrain_agents.errors import AgentOutputError, AgentTurnLimitError
from exambrain_agents.runner import run_agent, run_agent_with_corrective_retry
from exambrain_agents.testing import FakeModel, FinalOutput, ToolCall

SECRET_CONTENT = "TOP-SECRET-DOCUMENT-TEXT-1029384756"


class Answer(BaseModel):
    value: int
    note: str


@function_tool
def lookup(key: str) -> str:
    """Return a canned lookup value."""
    return f"value-for-{key}"


def make_agent(model: FakeModel) -> Agent:
    return Agent(
        name="test-agent",
        instructions="Answer using the lookup tool.",
        tools=[lookup],
        output_type=Answer,
        model=model,
    )


async def test_tool_loop_and_typed_output() -> None:
    model = FakeModel(
        outputs=[
            ToolCall("lookup", {"key": "x"}),
            FinalOutput(Answer(value=42, note="done")),
        ]
    )
    result = await run_agent(make_agent(model), "what is x?")
    assert isinstance(result, Answer)
    assert result.value == 42
    assert model.turns == 2  # real SDK loop: tool turn + final turn


async def test_turn_limit_maps_to_typed_error() -> None:
    model = FakeModel(outputs=[ToolCall("lookup", {"key": "x"})] * 5)
    with pytest.raises(AgentTurnLimitError) as exc_info:
        await run_agent(make_agent(model), "loop forever", max_turns=3)
    assert exc_info.value.agent_name == "test-agent"
    assert exc_info.value.max_turns == 3


async def test_bad_output_schema_maps_to_typed_error() -> None:
    model = FakeModel(outputs=[FinalOutput('{"wrong_field": true}')])
    with pytest.raises(AgentOutputError):
        await run_agent(make_agent(model), "answer")


async def test_corrective_retry_success_on_second_attempt() -> None:
    model = FakeModel(
        outputs=[
            FinalOutput(Answer(value=-1, note="bad")),
            FinalOutput(Answer(value=7, note="good")),
        ]
    )

    def validate(out: Answer) -> list[str]:
        return [] if out.value >= 0 else ["value must be non-negative"]

    output, failures = await run_agent_with_corrective_retry(
        make_agent(model), "answer", validate
    )
    assert output.value == 7
    assert failures == []
    assert model.turns == 2  # exactly one retry


async def test_corrective_retry_second_failure_returns_reasons() -> None:
    model = FakeModel(
        outputs=[
            FinalOutput(Answer(value=-1, note="bad")),
            FinalOutput(Answer(value=-2, note="still bad")),
        ]
    )

    def validate(out: Answer) -> list[str]:
        return [] if out.value >= 0 else ["value must be non-negative"]

    output, failures = await run_agent_with_corrective_retry(
        make_agent(model), "answer", validate
    )
    assert output.value == -2
    assert failures == ["value must be non-negative"]
    assert model.turns == 2  # never a third attempt


async def test_valid_first_output_skips_retry() -> None:
    model = FakeModel(outputs=[FinalOutput(Answer(value=1, note="ok"))])
    output, failures = await run_agent_with_corrective_retry(
        make_agent(model), "answer", lambda _out: []
    )
    assert output.value == 1
    assert failures == []
    assert model.turns == 1


async def test_log_records_never_contain_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FR-022: run logs carry metadata only — never document/prompt text."""
    model = FakeModel(outputs=[FinalOutput(Answer(value=1, note=SECRET_CONTENT))])
    with caplog.at_level(logging.DEBUG):
        await run_agent(make_agent(model), f"summarize: {SECRET_CONTENT}")
    for record in caplog.records:
        assert SECRET_CONTENT not in record.getMessage()
        assert SECRET_CONTENT not in str(getattr(record, "msg", ""))
