"""Unit tests for text chunking, overlap, metadata preservation, and citation formatting."""

from pathlib import Path
import pytest

from app.chunking.text_chunker import TextChunker, format_citation
from app.config import Settings
from app.extractors.pymupdf_extractor import PyMuPDFExtractor


def test_format_citation():
    """Verify source-page citation generation."""
    assert format_citation("report.pdf", [1]) == "report.pdf, Page 1"
    assert format_citation("report.pdf", [1, 2]) == "report.pdf, Pages 1-2"
    assert format_citation("report.pdf", [1, 3, 5]) == "report.pdf, Pages 1, 3, 5"


def test_chunker_invalid_overlap_raises():
    """Verify chunk_overlap >= chunk_size raises ValueError."""
    with pytest.raises(ValueError, match="chunk_overlap .* must be strictly less than chunk_size"):
        TextChunker(chunk_size=100, chunk_overlap=100)


def test_chunker_metadata_preservation(sample_text_pdf: Path, test_settings: Settings):
    """Verify all required metadata is preserved on every chunk."""
    extractor = PyMuPDFExtractor(settings=test_settings)
    extraction_res = extractor.extract(sample_text_pdf)

    chunker = TextChunker(chunk_size=150, chunk_overlap=30, settings=test_settings)
    chunks = chunker.chunk_document(extraction_res)

    assert len(chunks) > 0

    for i, c in enumerate(chunks):
        assert c.chunk_id == f"{extraction_res.metadata.document_id}_c{i:04d}"
        assert c.chunk_text.strip() != ""
        meta = c.metadata
        assert meta.document_id == extraction_res.metadata.document_id
        assert meta.document_name == "sample_text.pdf"
        assert len(meta.page_numbers) > 0
        assert meta.chunk_id == c.chunk_id
        assert meta.extraction_method == extraction_res.extraction_method.value
        assert "sample_text.pdf, Page" in meta.source_citation
        assert meta.char_count == len(c.chunk_text)
        assert meta.token_estimate > 0


def test_chunk_size_adherence(sample_text_pdf: Path, test_settings: Settings):
    """Verify that chunks adhere reasonably to the configured chunk size limit."""
    extractor = PyMuPDFExtractor(settings=test_settings)
    extraction_res = extractor.extract(sample_text_pdf)

    target_size = 200
    chunker = TextChunker(chunk_size=target_size, chunk_overlap=40, settings=test_settings)
    chunks = chunker.chunk_document(extraction_res)

    for c in chunks:
        # Chunks should be within bounds (+ allowance for unbreakable long sentence segment)
        assert len(c.chunk_text) <= target_size + 100
