"""Hierarchy-aware deterministic chunker (FR-003, research R5).

Pure pipeline code — chunking is never agent work. Each parsed question or
slide becomes one chunk (split further when it exceeds the ~500-token
target), carrying hierarchy metadata ``{kind, section, question_no,
page|slide, marks}`` for the existing ``document_chunks`` schema.
"""

from typing import Any

from exambrain_agents.schemas.parsing import ParsedDocument

# ~500-token target with the standard ~4 chars/token heuristic.
TARGET_TOKENS = 500
CHARS_PER_TOKEN = 4
TARGET_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN


def _split_text(text: str) -> list[str]:
    """Split on word boundaries into pieces of at most ~TARGET_CHARS."""
    if len(text) <= TARGET_CHARS:
        return [text]
    pieces: list[str] = []
    current: list[str] = []
    length = 0
    for word in text.split():
        if length and length + 1 + len(word) > TARGET_CHARS:
            pieces.append(" ".join(current))
            current, length = [], 0
        current.append(word)
        length += (1 if length else 0) + len(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def chunk_document(document: ParsedDocument) -> list[dict[str, Any]]:
    """Chunk a parsed document into ``{content, position, hierarchy}`` rows.

    Deterministic: identical input always yields identical output.
    """
    chunks: list[dict[str, Any]] = []
    position = 0
    for section in document.sections:
        for question in section.questions:
            hierarchy: dict[str, Any] = {
                "kind": document.kind,
                "section": section.title,
                "question_no": question.number,
            }
            if question.page is not None:
                hierarchy["page"] = question.page
            if question.marks is not None:
                hierarchy["marks"] = question.marks
            for piece in _split_text(question.text):
                chunks.append(
                    {"content": piece, "position": position, "hierarchy": hierarchy}
                )
                position += 1
        for slide in section.slides:
            slide_hierarchy: dict[str, Any] = {
                "kind": document.kind,
                "section": section.title,
                "slide": slide.index,
            }
            if slide.page is not None:
                slide_hierarchy["page"] = slide.page
            text = slide.text.strip()
            if not text:
                continue
            for piece in _split_text(text):
                chunks.append(
                    {
                        "content": piece,
                        "position": position,
                        "hierarchy": slide_hierarchy,
                    }
                )
                position += 1
    return chunks
