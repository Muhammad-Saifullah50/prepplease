"""Hierarchy-aware deterministic chunker tests (T015, FR-003, research R5)."""

from exambrain_agents.chunking import chunk_document
from exambrain_agents.schemas.parsing import (
    ParsedDocument,
    ParsedQuestion,
    ParsedSection,
    ParsedSlide,
)


def make_paper() -> ParsedDocument:
    return ParsedDocument(
        kind="past_paper",
        document_type="pdf_digital",
        instructor_name_seen="Dr. A. Rahman",
        sections=[
            ParsedSection(
                title="Section A",
                instructions="Answer all questions.",
                questions=[
                    ParsedQuestion(
                        number="1", text="Define entropy.", marks=5.0, page=1
                    ),
                    ParsedQuestion(
                        number="2(a)",
                        text="Derive the ideal gas law.",
                        marks=10.0,
                        page=2,
                    ),
                ],
                slides=[],
            )
        ],
        total_marks=15.0,
        confidence=0.95,
    )


def make_slides() -> ParsedDocument:
    return ParsedDocument(
        kind="course_material",
        document_type="pptx",
        instructor_name_seen=None,
        sections=[
            ParsedSection(
                title="Week 1",
                instructions=None,
                questions=[],
                slides=[
                    ParsedSlide(index=1, text="Entropy and enthalpy basics."),
                    ParsedSlide(index=2, text="PV = nRT and applications."),
                ],
            )
        ],
        total_marks=None,
        confidence=0.9,
    )


def test_past_paper_chunks_carry_hierarchy_metadata() -> None:
    chunks = chunk_document(make_paper())
    assert len(chunks) == 2  # one per question at this size
    first = chunks[0]
    assert first["content"] == "Define entropy."
    assert first["position"] == 0
    assert first["hierarchy"] == {
        "kind": "past_paper",
        "section": "Section A",
        "question_no": "1",
        "page": 1,
        "marks": 5.0,
    }
    assert chunks[1]["hierarchy"]["question_no"] == "2(a)"


def test_slide_chunks_carry_slide_hierarchy() -> None:
    chunks = chunk_document(make_slides())
    assert len(chunks) == 2
    assert chunks[0]["hierarchy"] == {
        "kind": "course_material",
        "section": "Week 1",
        "slide": 1,
    }
    assert "Entropy" in chunks[0]["content"]


def test_long_text_splits_near_token_target() -> None:
    """A very long question splits into multiple ~500-token chunks."""
    long_text = " ".join(f"word{i}" for i in range(3000))  # ≫ 500 tokens
    doc = ParsedDocument(
        kind="past_paper",
        document_type="pdf_digital",
        instructor_name_seen=None,
        sections=[
            ParsedSection(
                title="S",
                instructions=None,
                questions=[
                    ParsedQuestion(number="1", text=long_text, marks=None, page=1)
                ],
                slides=[],
            )
        ],
        total_marks=None,
        confidence=1.0,
    )
    chunks = chunk_document(doc)
    assert len(chunks) > 1
    # Every piece keeps the same hierarchy; positions are sequential.
    assert [c["position"] for c in chunks] == list(range(len(chunks)))
    assert all(c["hierarchy"]["question_no"] == "1" for c in chunks)
    # No chunk wildly exceeds the ~500-token target (~4 chars/token heuristic).
    assert all(len(c["content"]) <= 500 * 6 for c in chunks)
    # Content is lossless when rejoined.
    assert " ".join(c["content"] for c in chunks).split() == long_text.split()


def test_chunking_is_deterministic() -> None:
    doc = make_paper()
    assert chunk_document(doc) == chunk_document(doc)
