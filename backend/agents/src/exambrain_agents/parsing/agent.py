"""Parsing agent definition (FR-001/FR-002, contracts/tools.md).

The pipeline extracts raw page/slide text deterministically and passes it
as input; the agent structures it. Re-extraction tools are registered so
the agent can reread specific pages when structuring is ambiguous — both
paths are read-only (FR-019).
"""

import json
from typing import Any

from agents import Agent, function_tool

from exambrain_agents import config
from exambrain_agents.parsing.prompt import PARSING_PROMPT_V1
from exambrain_agents.schemas.parsing import ParsedDocument
from exambrain_agents.tools.extraction import (
    PageText,
    SlideText,
    extract_pdf_text,
    extract_pptx_text,
    ocr_pdf_pages,
)


def _make_tools(
    pdf_bytes: bytes | None, pptx_bytes: bytes | None
) -> list[Any]:
    """Read-only re-extraction tools closing over the document bytes."""

    @function_tool
    def reread_pdf_page(page: int) -> str:
        """Re-extract the digital text of one PDF page (1-based)."""
        if pdf_bytes is None:
            return "no PDF loaded"
        pages = extract_pdf_text(pdf_bytes)
        match = [p.text for p in pages if p.page == page]
        return match[0] if match else f"page {page} out of range"

    @function_tool
    async def reread_pdf_page_ocr(page: int) -> str:
        """Re-OCR one PDF page (1-based) — for image-only pages."""
        if pdf_bytes is None:
            return "no PDF loaded"
        results = await ocr_pdf_pages(pdf_bytes, [page])
        return results[0].text if results else f"page {page} out of range"

    @function_tool
    def reread_pptx(slide: int) -> str:
        """Re-extract the text of one PPTX slide (1-based)."""
        if pptx_bytes is None:
            return "no PPTX loaded"
        slides = extract_pptx_text(pptx_bytes)
        match = [s for s in slides if s.slide == slide]
        if not match:
            return f"slide {slide} out of range"
        s = match[0]
        return f"{s.title or ''}\n{s.text}".strip()

    return [reread_pdf_page, reread_pdf_page_ocr, reread_pptx]


def build_parsing_agent(
    *, pdf_bytes: bytes | None = None, pptx_bytes: bytes | None = None
) -> Agent[Any]:
    """Build the parsing agent with re-extraction tools registered."""
    return Agent(
        name="parsing",
        instructions=PARSING_PROMPT_V1,
        tools=_make_tools(pdf_bytes, pptx_bytes),
        output_type=ParsedDocument,
        model=config.model_for_or_none("parsing"),
    )


def parsing_input(
    kind: str,
    document_type: str,
    pages: list[PageText] | None = None,
    slides: list[SlideText] | None = None,
) -> str:
    """Serialize preprocessed extraction output as the agent's input."""
    payload: dict[str, Any] = {"kind": kind, "document_type": document_type}
    if pages is not None:
        payload["pages"] = [
            {"page": p.page, "text": p.text} for p in pages
        ]
    if slides is not None:
        payload["slides"] = [
            {"slide": s.slide, "title": s.title, "text": s.text} for s in slides
        ]
    return json.dumps(payload)
