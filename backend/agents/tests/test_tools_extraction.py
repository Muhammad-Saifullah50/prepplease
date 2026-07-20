"""Deterministic extraction-tool tests — no model involved (T014, FR-018).

Covers pypdfium2 per-page text extraction, OCR routing for low-character
pages, the PPTX slide walk, and ParsingFailedError on corrupt input.
"""

import pytest

from exambrain_agents.errors import ParsingFailedError
from exambrain_agents.tools.extraction import (
    DIGITAL_TEXT_CHAR_THRESHOLD,
    classify_pages,
    extract_pdf_text,
    extract_pptx_text,
    ocr_pdf_pages,
)


def test_extract_pdf_text_per_page(digital_pdf_bytes: bytes) -> None:
    pages = extract_pdf_text(digital_pdf_bytes)
    assert len(pages) == 2
    assert pages[0].page == 1
    assert "Section A" in pages[0].text
    assert "entropy" in pages[0].text
    assert pages[0].char_count == len(pages[0].text)
    assert "Section B" in pages[1].text


def test_extract_pdf_text_scanned_pages_empty(scanned_pdf_bytes: bytes) -> None:
    pages = extract_pdf_text(scanned_pdf_bytes)
    assert len(pages) == 2
    assert all(p.char_count < DIGITAL_TEXT_CHAR_THRESHOLD for p in pages)


def test_classify_pages_routes_low_char_pages_to_ocr(
    digital_pdf_bytes: bytes, scanned_pdf_bytes: bytes
) -> None:
    digital = extract_pdf_text(digital_pdf_bytes)
    scanned = extract_pdf_text(scanned_pdf_bytes)
    kind, ocr_pages = classify_pages(digital)
    assert kind == "pdf_digital"
    assert ocr_pages == []
    kind, ocr_pages = classify_pages(scanned)
    assert kind == "pdf_scanned"
    assert ocr_pages == [1, 2]  # every page below the char threshold


async def test_ocr_pdf_pages_returns_page_texts(scanned_pdf_bytes: bytes) -> None:
    """OCR of blank rendered pages returns empty-ish text without error."""
    pytest.importorskip("pytesseract")
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not installed")
    pages = await ocr_pdf_pages(scanned_pdf_bytes, [1])
    assert len(pages) == 1
    assert pages[0].page == 1


def test_extract_pptx_text_slide_walk(pptx_bytes: bytes) -> None:
    slides = extract_pptx_text(pptx_bytes)
    assert len(slides) == 2
    assert slides[0].slide == 1
    assert slides[0].title == "Week 1: Thermodynamics"
    assert "Entropy" in slides[0].text
    assert slides[1].title == "Week 2: Gas Laws"


def test_corrupt_pdf_raises_parsing_failed(corrupt_pdf_bytes: bytes) -> None:
    with pytest.raises(ParsingFailedError):
        extract_pdf_text(corrupt_pdf_bytes)


def test_corrupt_pptx_raises_parsing_failed() -> None:
    with pytest.raises(ParsingFailedError):
        extract_pptx_text(b"not a pptx at all")


def test_empty_pdf_raises_parsing_failed() -> None:
    with pytest.raises(ParsingFailedError):
        extract_pdf_text(b"")
