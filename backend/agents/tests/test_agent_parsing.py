"""Parsing-agent tests via FakeModel (T016, FR-001/FR-002)."""

from exambrain_agents.parsing.agent import build_parsing_agent, parsing_input
from exambrain_agents.runner import run_agent
from exambrain_agents.schemas.parsing import (
    ParsedDocument,
    ParsedQuestion,
    ParsedSection,
)
from exambrain_agents.testing import FakeModel, FinalOutput, ToolCall
from exambrain_agents.tools.extraction import PageText


def make_output(confidence: float) -> ParsedDocument:
    return ParsedDocument(
        kind="past_paper",
        document_type="pdf_digital",
        instructor_name_seen="Dr. A. Rahman",
        sections=[
            ParsedSection(
                title="Section A",
                instructions=None,
                questions=[
                    ParsedQuestion(
                        number="1", text="Define entropy.", marks=5.0, page=1
                    )
                ],
                slides=[],
            )
        ],
        total_marks=5.0,
        confidence=confidence,
    )


PAGES = [
    PageText(page=1, text="Section A Q1. Define entropy. [5 marks]", char_count=39)
]


async def test_parsing_agent_returns_typed_document() -> None:
    model = FakeModel(outputs=[FinalOutput(make_output(0.95))])
    agent = build_parsing_agent()
    result = await run_agent(
        agent, parsing_input("past_paper", "pdf_digital", PAGES), model=model
    )
    assert isinstance(result, ParsedDocument)
    assert result.confidence == 0.95
    assert result.sections[0].questions[0].marks == 5.0


async def test_low_confidence_flows_through_unaltered() -> None:
    """FR-002: low confidence is a flag, not a failure — output passes."""
    model = FakeModel(outputs=[FinalOutput(make_output(0.30))])
    result = await run_agent(
        build_parsing_agent(),
        parsing_input("past_paper", "pdf_digital", PAGES),
        model=model,
    )
    assert result.confidence == 0.30  # pipeline decides needs_review, not agent


async def test_parsing_agent_tool_loop_re_extraction() -> None:
    """The agent may re-extract specific pages via its registered tools."""
    doc_bytes_key = "unused"  # tools receive bytes via closure in real runs
    model = FakeModel(
        outputs=[
            ToolCall("reread_pdf_page", {"page": 1}),
            FinalOutput(make_output(0.9)),
        ]
    )
    agent = build_parsing_agent(pdf_bytes=b"%PDF-fake")
    # The scripted tool call must resolve against a registered tool name.
    tool_names = {t.name for t in agent.tools}
    assert "reread_pdf_page" in tool_names
    assert doc_bytes_key  # silence linters about the explanatory var
    result = await run_agent(
        agent, parsing_input("past_paper", "pdf_digital", PAGES), model=model
    )
    assert isinstance(result, ParsedDocument)
    assert model.turns == 2


async def test_parsing_time_limit_extraction() -> None:
    parsed = make_output(0.95)
    parsed = parsed.model_copy(update={"time_limit_minutes": 180})
    model = FakeModel(outputs=[FinalOutput(parsed)])
    agent = build_parsing_agent()
    result = await run_agent(
        agent, parsing_input("past_paper", "pdf_digital", PAGES), model=model
    )
    assert isinstance(result, ParsedDocument)
    assert result.time_limit_minutes == 180


async def test_parsing_time_limit_null_when_not_stated() -> None:
    parsed = make_output(0.95)
    parsed = parsed.model_copy(update={"time_limit_minutes": None})
    model = FakeModel(outputs=[FinalOutput(parsed)])
    result = await run_agent(
        build_parsing_agent(),
        parsing_input("past_paper", "pdf_digital", PAGES),
        model=model,
    )
    assert result.time_limit_minutes is None


def test_parsing_prompt_includes_time_limit_instruction() -> None:
    from exambrain_agents.parsing.prompt import PARSING_PROMPT_V1

    text = PARSING_PROMPT_V1.lower()
    assert "time_limit_minutes" in text or "time limit" in text
