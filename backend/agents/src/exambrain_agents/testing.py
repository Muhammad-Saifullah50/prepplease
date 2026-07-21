"""Scripted fake model for offline agent tests (research R9, FR-024).

:class:`FakeModel` implements the Agents SDK ``Model`` interface and
returns a pre-scripted sequence of responses, so tests exercise the real
SDK tool loop, output-schema validation, and ``max_turns`` accounting with
zero network access. Script steps are built from :class:`ToolCall` and
:class:`FinalOutput` helpers::

    model = FakeModel(outputs=[
        ToolCall("score_name_candidates", {"name": "a rahman"}),
        FinalOutput(InstructorResolution(...)),
    ])
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from agents.agent_output import AgentOutputSchemaBase
from agents.handoffs import Handoff
from agents.items import ModelResponse, TResponseInputItem, TResponseStreamEvent
from agents.model_settings import ModelSettings
from agents.models.interface import Model, ModelTracing
from agents.tool import Tool
from agents.usage import Usage
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)
from pydantic import BaseModel


@dataclass(frozen=True)
class ToolCall:
    """One scripted tool invocation: the model 'decides' to call a tool."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinalOutput:
    """One scripted final answer — a typed Pydantic output or plain text."""

    output: BaseModel | str


ScriptStep = ToolCall | FinalOutput | list[ToolCall]


class FakeModel(Model):
    """Deterministic ``Model`` returning a scripted response sequence.

    Each ``get_response`` call consumes the next script step. A ``list``
    of :class:`ToolCall` emits several tool calls in one turn. Running past
    the end of the script raises ``AssertionError`` — a test bug.
    """

    def __init__(self, outputs: list[ScriptStep]) -> None:
        self._script = list(outputs)
        self._cursor = 0
        self.turns = 0  # number of get_response calls observed

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> ModelResponse:
        assert self._cursor < len(self._script), (
            f"FakeModel script exhausted after {self._cursor} steps "
            f"(turn {self.turns + 1} requested)"
        )
        step = self._script[self._cursor]
        self._cursor += 1
        self.turns += 1

        calls = (
            step
            if isinstance(step, list)
            else [step]
            if isinstance(step, ToolCall)
            else []
        )
        items: list[Any] = [
            ResponseFunctionToolCall(
                type="function_call",
                call_id=f"call_{self.turns}_{i}",
                name=call.name,
                arguments=json.dumps(call.arguments),
            )
            for i, call in enumerate(calls)
        ]
        if isinstance(step, FinalOutput):
            out = step.output
            text = (
                out
                if isinstance(out, str)
                else out.model_dump_json()  # typed output → strict JSON
            )
            items.append(
                ResponseOutputMessage(
                    id=f"msg_{self.turns}",
                    type="message",
                    role="assistant",
                    status="completed",
                    content=[
                        ResponseOutputText(
                            type="output_text", text=text, annotations=[]
                        )
                    ],
                )
            )

        return ModelResponse(
            output=items,
            usage=Usage(requests=1, input_tokens=10, output_tokens=10, total_tokens=20),
            response_id=f"fake_{self.turns}",
        )

    def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> AsyncIterator[TResponseStreamEvent]:
        raise NotImplementedError("FakeModel does not support streaming")
