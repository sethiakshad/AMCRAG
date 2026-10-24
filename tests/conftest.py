import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from pathlib import Path
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None
import pytest

from app.config import Settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Create isolated Settings pointing to a temporary directory."""
    return Settings(
        base_dir=tmp_path,
        uploads_dir=tmp_path / "uploads",
        processed_dir=tmp_path / "processed",
        page_images_dir=tmp_path / "page_images",
        chunk_size=300,
        chunk_overlap=50,
        render_dpi=100,
        ocr_min_chars_per_page=30,
        ocr_min_doc_chars=60,
    )


@pytest.fixture
def sample_text_pdf(tmp_path: Path) -> Path:
    """Create a 2-page clean PDF with headings, paragraphs, and text."""
    if fitz is None:
        pytest.skip("PyMuPDF (fitz) is not installed")
    pdf_path = tmp_path / "sample_text.pdf"
    doc = fitz.open()

    # Page 1
    p1 = doc.new_page()
    p1.insert_text(fitz.Point(50, 70), "CHAPTER 1: INTRODUCTION", fontsize=16)
    p1_body = (
        "Adaptive Multimodal Corrective RAG is an architecture designed for high-precision retrieval. "
        "It balances dense semantic search, sparse lexical retrieval, and direct visual understanding "
        "using ColPali representations. Each module is specialized and communicates via structured schemas. "
        "This ensures that downstream generators can attribute facts with fine-grained page-level citations."
    )
    p1.insert_textbox(fitz.Rect(50, 90, 550, 400), p1_body, fontsize=10)

    # Page 2
    p2 = doc.new_page()
    p2.insert_text(fitz.Point(50, 70), "CHAPTER 2: ARCHITECTURE", fontsize=16)
    p2_body = (
        "The document processing pipeline is responsible for parsing raw PDFs into clean text chunks. "
        "PyMuPDF provides high-performance page-wise text extraction, while Docling provides rich table "
        "and hierarchy parsing. When Docling encounters errors or is unavailable, the pipeline falls back "
        "to PyMuPDF gracefully, logging all steps."
    )
    p2.insert_textbox(fitz.Rect(50, 90, 550, 400), p2_body, fontsize=10)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def scanned_mock_pdf(tmp_path: Path) -> Path:
    """Create a PDF containing only a raster image and 0 text, simulating a scanned document."""
    if fitz is None:
        pytest.skip("PyMuPDF (fitz) is not installed")
    pdf_path = tmp_path / "scanned_doc.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)

    # Generate a pure red 100x100 pixmap image
    pix = fitz.Pixmap(fitz.csRGB, (0, 0, 100, 100), 0)
    pix.clear_with(255)  # white background
    img_rect = fitz.Rect(50, 50, 250, 250)
    page.insert_image(img_rect, pixmap=pix)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def empty_page_pdf(tmp_path: Path) -> Path:
    """Create a PDF with one empty page and one minimal text page."""
    if fitz is None:
        pytest.skip("PyMuPDF (fitz) is not installed")
    pdf_path = tmp_path / "empty_pages.pdf"
    doc = fitz.open()
    doc.new_page()  # Page 1: totally empty
    p2 = doc.new_page()  # Page 2: short text
    p2.insert_text(fitz.Point(50, 50), "Only one line here.", fontsize=10)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def corrupted_pdf(tmp_path: Path) -> Path:
    """Create an invalid binary file masquerading as a PDF."""
    corrupt_path = tmp_path / "corrupted.pdf"
    corrupt_path.write_bytes(b"NOT A REAL PDF CONTENT AT ALL 12345")
    return corrupt_path
