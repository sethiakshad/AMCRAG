"""test_end_to_end_integration.py - Full Pipeline Integration Test.

Tests the complete lifecycle of a document in Person 1's module:
1. PDF Text Extraction (PyMuPDF) -> <stem>_extracted.json
2. Text Chunking with Provenance -> <stem>_chunks.json
3. Page Image Rendering (ColPali format) -> <stem>_manifest.json + PNGs

Validates consistency across all 3 artifacts:
- Identical source_file and total_pages.
- Chunks' page_numbers map to existing extracted pages and rendered image files.
- Manifest image_path targets point to real, verified PNG files on disk.
"""

import json
import subprocess
import sys
from pathlib import Path

import pymupdf as fitz
import pytest

from chunk_text import chunk_extracted_document, save_chunk_output
from extract_pdf import extract_page_text, save_json_output
from render_pdf_pages import render_pdf_pages


@pytest.fixture
def integration_research_pdf(tmp_path: Path) -> Path:
    """Create a 3-page synthetic research paper PDF for integration testing."""
    pdf_path = tmp_path / "integration_paper.pdf"
    doc = fitz.open()

    # Page 1: Abstract & Introduction
    p1 = doc.new_page()
    p1.insert_text(fitz.Point(50, 60), "Neural Multimodal RAG with Corrective Feedback", fontsize=15)
    body1 = (
        "Abstract: Large language models generate inaccurate citations when reasoning over complex tables. "
        "In this work, we introduce an adaptive pipeline combining dense embeddings with ColPali visual embeddings. "
        "Section 1: Ingestion Architecture. We present the ingestion pipeline developed by Person 1."
    )
    p1.insert_textbox(fitz.Rect(50, 80, 520, 300), body1, fontsize=10)

    # Page 2: Methodology & Chunking Design
    p2 = doc.new_page()
    p2.insert_text(fitz.Point(50, 60), "Section 2: Chunking and Provenance Preservation", fontsize=14)
    body2 = (
        "Each chunk records its start page, end page, and formatted citation. "
        "When text spans across page boundaries, the manifest and chunk records maintain exact synchronization. "
        "This facilitates fine-grained attribution during final response generation."
    )
    p2.insert_textbox(fitz.Rect(50, 80, 520, 300), body2, fontsize=10)

    # Page 3: Blank page to test empty-page detection in the pipeline
    doc.new_page()

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_full_python_pipeline_integration(integration_research_pdf: Path, tmp_path: Path):
    """Verify programmatic end-to-end flow: extraction -> chunking -> page rendering."""
    processed_dir = tmp_path / "processed"
    images_dir = tmp_path / "page_images"

    # Step 1: Extraction
    extraction_data = extract_page_text(integration_research_pdf)
    assert extraction_data["source_file"] == "integration_paper.pdf"
    assert extraction_data["total_pages"] == 3
    assert extraction_data["empty_pages"] == [3]

    extracted_json_path = processed_dir / "integration_paper_extracted.json"
    save_json_output(extraction_data, extracted_json_path)
    assert extracted_json_path.exists()

    # Step 2: Chunking from extracted data
    chunk_data = chunk_extracted_document(extraction_data, chunk_size=300, chunk_overlap=50)
    assert chunk_data["source_file"] == "integration_paper.pdf"
    assert chunk_data["total_pages"] == 3
    assert chunk_data["total_chunks"] > 0

    chunk_json_path = processed_dir / "integration_paper_chunks.json"
    save_chunk_output(chunk_data, chunk_json_path)
    assert chunk_json_path.exists()

    # Step 3: Page Rendering & Manifest
    manifest_data = render_pdf_pages(
        pdf_path=integration_research_pdf,
        output_dir=images_dir / "integration_paper",
        dpi=100,
        image_format="png",
    )
    assert manifest_data["source_file"] == "integration_paper.pdf"
    assert manifest_data["total_pages"] == 3
    assert manifest_data["total_rendered_images"] == 3

    # Step 4: Consistency Checks Across All 3 Outputs
    # A. Page consistency
    assert extraction_data["total_pages"] == chunk_data["total_pages"] == manifest_data["total_pages"]
    assert extraction_data["source_file"] == chunk_data["source_file"] == manifest_data["source_file"]

    # B. Chunk page bounds consistency
    for chunk in chunk_data["chunks"]:
        assert 1 <= chunk["start_page"] <= 3
        assert 1 <= chunk["end_page"] <= 3
        assert chunk["start_page"] <= chunk["end_page"]
        assert "integration_paper.pdf, Page" in chunk["source_citation"]

    # C. Image file consistency
    for p_info in manifest_data["pages"]:
        img_p = Path(p_info["image_path"])
        assert img_p.exists()
        assert img_p.suffix == ".png"
        assert p_info["width"] > 0
        assert p_info["height"] > 0


def test_full_cli_pipeline_integration(integration_research_pdf: Path, tmp_path: Path):
    """Verify executing all 3 CLI scripts sequentially on a PDF produces consistent outputs."""
    processed_dir = tmp_path / "cli_processed"
    images_dir = tmp_path / "cli_images"

    # Command 1: Extract
    cmd_extract = [
        sys.executable,
        "extract_pdf.py",
        str(integration_research_pdf),
        "--output-dir",
        str(processed_dir),
    ]
    res1 = subprocess.run(cmd_extract, capture_output=True, text=True)
    assert res1.returncode == 0
    extracted_json = processed_dir / "integration_paper_extracted.json"
    assert extracted_json.exists()

    # Command 2: Chunk (consuming extracted JSON)
    cmd_chunk = [
        sys.executable,
        "chunk_text.py",
        str(extracted_json),
        "--output-dir",
        str(processed_dir),
        "--chunk-size",
        "250",
        "--chunk-overlap",
        "50",
    ]
    res2 = subprocess.run(cmd_chunk, capture_output=True, text=True)
    assert res2.returncode == 0
    chunks_json = processed_dir / "integration_paper_chunks.json"
    assert chunks_json.exists()

    # Command 3: Render Pages
    cmd_render = [
        sys.executable,
        "render_pdf_pages.py",
        str(integration_research_pdf),
        "--output-dir",
        str(images_dir / "integration_paper"),
        "--dpi",
        "120",
    ]
    res3 = subprocess.run(cmd_render, capture_output=True, text=True)
    assert res3.returncode == 0
    manifest_json = images_dir / "integration_paper" / "integration_paper_manifest.json"
    assert manifest_json.exists()

    # Validate output data
    with chunks_json.open("r", encoding="utf-8") as f:
        chunks_content = json.load(f)
    assert chunks_content["total_chunks"] > 0

    with manifest_json.open("r", encoding="utf-8") as f:
        manifest_content = json.load(f)
    assert manifest_content["total_rendered_images"] == 3
