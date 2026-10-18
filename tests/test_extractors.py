"""Unit tests for PyMuPDF, Docling, scanned detection, and fallback extraction."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from app.config import Settings
from app.extractors.fallback_extractor import FallbackExtractor
from app.extractors.pymupdf_extractor import PyMuPDFExtractor
from app.schemas.document import ExtractionMethod


def test_pymupdf_text_extraction(sample_text_pdf: Path, test_settings: Settings):
    """Test standard text and heading extraction with PyMuPDF."""
    extractor = PyMuPDFExtractor(settings=test_settings)
    result = extractor.extract(sample_text_pdf)

    assert result.metadata.page_count == 2
    assert result.metadata.document_name == "sample_text.pdf"
    assert not result.is_scanned
    assert not result.ocr_needed
    assert len(result.pages) == 2

    # Check page 1
    p1 = result.pages[0]
    assert p1.page_number == 1
    assert "Adaptive Multimodal Corrective RAG" in p1.text
    assert any("CHAPTER 1" in h for h in p1.headings)

    # Check page 2
    p2 = result.pages[1]
    assert p2.page_number == 2
    assert "high-performance page-wise text extraction" in p2.text
    assert any("CHAPTER 2" in h for h in p2.headings)


def test_scanned_pdf_detection(scanned_mock_pdf: Path, test_settings: Settings):
    """Verify that scanned PDFs without text streams are detected and flagged for OCR."""
    extractor = PyMuPDFExtractor(settings=test_settings)
    result = extractor.extract(scanned_mock_pdf)

    # Must flag scanned and OCR needed - must NOT claim successful text extraction
    assert result.is_scanned is True
    assert result.ocr_needed is True
    assert len(result.warnings) > 0
    assert any("OCR is required" in w or "scanned" in w.lower() for w in result.warnings)
    assert result.pages[0].ocr_needed is True


def test_empty_page_handling(empty_page_pdf: Path, test_settings: Settings):
    """Verify that completely blank pages are identified gracefully."""
    extractor = PyMuPDFExtractor(settings=test_settings)
    result = extractor.extract(empty_page_pdf)

    assert len(result.pages) == 2
    assert result.pages[0].is_empty is True
    assert result.pages[0].char_count == 0
    assert result.pages[1].is_empty is False


def test_corrupted_pdf_error(corrupted_pdf: Path, test_settings: Settings):
    """Verify corrupted non-PDF files raise descriptive ValueError."""
    extractor = PyMuPDFExtractor(settings=test_settings)
    with pytest.raises(ValueError, match="Corrupted or invalid PDF"):
        extractor.extract(corrupted_pdf)


def test_nonexistent_pdf_error(tmp_path: Path, test_settings: Settings):
    """Verify missing file raises FileNotFoundError."""
    extractor = PyMuPDFExtractor(settings=test_settings)
    missing = tmp_path / "does_not_exist.pdf"
    with pytest.raises(FileNotFoundError):
        extractor.extract(missing)


def test_fallback_extractor_triggers_on_docling_failure(sample_text_pdf: Path, test_settings: Settings):
    """Verify that when Docling fails or raises an exception, the FallbackExtractor engages PyMuPDF."""
    mock_docling = MagicMock()
    mock_docling.is_available.return_value = True
    mock_docling.extract.side_effect = RuntimeError("Docling out of memory or parsing exception")

    extractor = FallbackExtractor(
        settings=test_settings,
        docling_extractor=mock_docling,
    )

    result = extractor.extract(sample_text_pdf)

    assert result.extraction_method == ExtractionMethod.PYMUPDF_FALLBACK
    assert result.metadata.page_count == 2
    assert any("Docling extraction failed" in w for w in result.warnings)
    assert "Adaptive Multimodal Corrective RAG" in result.pages[0].text
