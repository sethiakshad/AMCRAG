"""Integration tests for the complete DocumentProcessingPipeline."""

import json
from pathlib import Path

from app.config import Settings
from app.extractors.pymupdf_extractor import PyMuPDFExtractor
from app.services.pipeline import DocumentProcessingPipeline


def test_pipeline_end_to_end_success(sample_text_pdf: Path, test_settings: Settings):
    """Verify complete processing flow on a standard text PDF."""
    pipeline = DocumentProcessingPipeline(settings=test_settings)
    output = pipeline.process_file(sample_text_pdf)

    assert output.status == "success"
    assert output.document_name == "sample_text.pdf"
    assert output.metadata.page_count == 2
    assert output.total_chunks > 0
    assert len(output.rendered_pages) == 2
    assert output.is_scanned is False
    assert output.ocr_needed is False

    # Check saved JSON on filesystem
    json_path = test_settings.get_processed_path() / f"{output.document_id}.json"
    assert json_path.exists()

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["document_id"] == output.document_id
    assert len(data["chunks"]) == output.total_chunks


def test_pipeline_duplicate_detection(sample_text_pdf: Path, test_settings: Settings):
    """Verify duplicate upload detection skips redundant processing."""
    pipeline = DocumentProcessingPipeline(settings=test_settings)

    # First run: processes normally
    res1 = pipeline.process_file(sample_text_pdf)
    assert res1.status == "success"

    # Second run without force: skips processing
    res2 = pipeline.process_file(sample_text_pdf, force_reprocess=False)
    assert res2.status == "duplicate_skipped"
    assert res2.document_id == res1.document_id

    # Third run with force: reprocesses
    res3 = pipeline.process_file(sample_text_pdf, force_reprocess=True)
    assert res3.status == "success"


def test_pipeline_scanned_pdf_flags_ocr(scanned_mock_pdf: Path, test_settings: Settings):
    """Verify that pipeline identifies scanned PDFs and warns downstream modules."""
    pipeline = DocumentProcessingPipeline(settings=test_settings)
    output = pipeline.process_file(scanned_mock_pdf)

    assert output.status == "warning_ocr_needed"
    assert output.is_scanned is True
    assert output.ocr_needed is True
    assert len(output.warnings) > 0
    assert len(output.rendered_pages) == 1


def test_pipeline_directory_processing(sample_text_pdf: Path, scanned_mock_pdf: Path, test_settings: Settings):
    """Verify batch processing of an input directory."""
    pipeline = DocumentProcessingPipeline(settings=test_settings)
    input_dir = sample_text_pdf.parent

    results = pipeline.process_directory(input_dir)
    assert len(results) >= 2
    doc_names = [r.document_name for r in results]
    assert "sample_text.pdf" in doc_names
    assert "scanned_doc.pdf" in doc_names
