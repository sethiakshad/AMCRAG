"""Automated pytest test suite for extract_pdf.py (Milestone 1).

Covers all 8 correctness and reliability criteria:
1. Valid PDF extracts text from every page.
2. Page numbers start at 1 and maintain correct order.
3. JSON output is valid UTF-8 and conforms to required schema.
4. Empty-text and whitespace-only pages are detected and reported.
5. Missing file paths produce clear errors.
6. Corrupted, invalid, or 0-byte PDFs are handled gracefully.
7. Existing files are not overwritten unexpectedly without explicit flag.
8. File paths containing spaces work correctly.
"""

import json
import subprocess
import sys
from pathlib import Path

import pymupdf as fitz
import pytest

from extract_pdf import extract_page_text, save_json_output


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def multi_page_text_pdf(tmp_path: Path) -> Path:
    """Create a 3-page PDF with distinct text on every page."""
    pdf_path = tmp_path / "valid_multipage.pdf"
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_textbox(fitz.Rect(50, 50, 500, 300), "First Page Text: Introduction to RAG.", fontsize=11)

    p2 = doc.new_page()
    p2.insert_textbox(fitz.Rect(50, 50, 500, 300), "Second Page Text: Adaptive Multimodal Architecture.", fontsize=11)

    p3 = doc.new_page()
    p3.insert_textbox(fitz.Rect(50, 50, 500, 300), "Third Page Text: Evaluation and Conclusion.", fontsize=11)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def pdf_with_empty_and_whitespace_pages(tmp_path: Path) -> Path:
    """Create a 4-page PDF with empty, whitespace-only, and populated pages."""
    pdf_path = tmp_path / "has_empty_pages.pdf"
    doc = fitz.open()

    # Page 1: Normal text
    p1 = doc.new_page()
    p1.insert_text(fitz.Point(50, 50), "Valid Page Content", fontsize=12)

    # Page 2: Completely blank (0 text)
    doc.new_page()

    # Page 3: Whitespace only (spaces, newlines, tabs)
    p3 = doc.new_page()
    p3.insert_text(fitz.Point(50, 50), "   \n\t   \n   ", fontsize=10)

    # Page 4: Another valid text page
    p4 = doc.new_page()
    p4.insert_text(fitz.Point(50, 50), "Final Valid Page", fontsize=12)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def pdf_with_unicode_characters(tmp_path: Path) -> Path:
    """Create a PDF with Unicode characters (accents, guillemets, degree symbols)."""
    pdf_path = tmp_path / "unicode_doc.pdf"
    doc = fitz.open()
    p1 = doc.new_page()
    unicode_text = "RAG evaluation: café résumé, «Adaptive Retrieval», 25°C."
    p1.insert_textbox(fitz.Rect(50, 50, 500, 300), unicode_text, fontsize=11)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# ---------------------------------------------------------------------------
# Criterion 1: Valid PDF extracts text from every page
# ---------------------------------------------------------------------------


def test_valid_pdf_extracts_text_from_every_page(multi_page_text_pdf: Path):
    """Verify text is extracted from all pages of a multi-page PDF."""
    result = extract_page_text(multi_page_text_pdf)

    assert result["source_file"] == "valid_multipage.pdf"
    assert result["total_pages"] == 3
    assert len(result["pages"]) == 3

    assert "First Page Text" in result["pages"][0]["text"]
    assert "Second Page Text" in result["pages"][1]["text"]
    assert "Third Page Text" in result["pages"][2]["text"]

    for page in result["pages"]:
        assert page["is_empty"] is False
        assert page["char_count"] > 0


# ---------------------------------------------------------------------------
# Criterion 2: Page numbers start at 1 and remain in correct order
# ---------------------------------------------------------------------------


def test_page_numbers_start_at_1_and_maintain_order(multi_page_text_pdf: Path):
    """Verify page numbers are strictly 1-based and follow original document order."""
    result = extract_page_text(multi_page_text_pdf)

    page_numbers = [p["page_number"] for p in result["pages"]]
    assert page_numbers == [1, 2, 3]


# ---------------------------------------------------------------------------
# Criterion 3: Valid UTF-8 JSON output conforming to schema
# ---------------------------------------------------------------------------


def test_json_output_valid_utf8_and_schema(pdf_with_unicode_characters: Path, tmp_path: Path):
    """Verify saved JSON is strictly valid UTF-8 and contains all expected schema fields."""
    result = extract_page_text(pdf_with_unicode_characters)
    out_file = tmp_path / "processed" / "unicode_extracted.json"

    saved_path = save_json_output(result, out_file)
    assert saved_path.exists()

    # Read as raw bytes and decode strictly as UTF-8
    raw_bytes = out_file.read_bytes()
    decoded_str = raw_bytes.decode("utf-8")
    data = json.loads(decoded_str)

    # Check top-level schema keys
    assert data["source_file"] == "unicode_doc.pdf"
    assert data["total_pages"] == 1
    assert isinstance(data["empty_pages"], list)
    assert isinstance(data["has_empty_pages"], bool)
    assert isinstance(data["pages"], list)

    # Check page-level schema keys
    page = data["pages"][0]
    assert page["page_number"] == 1
    assert "café résumé" in page["text"]
    assert "«Adaptive Retrieval»" in page["text"]
    assert "25°C" in page["text"]
    assert page["char_count"] == len(page["text"])
    assert page["is_empty"] is False


# ---------------------------------------------------------------------------
# Criterion 4: Empty-text and whitespace-only pages detected and reported
# ---------------------------------------------------------------------------


def test_empty_and_whitespace_pages_detected(pdf_with_empty_and_whitespace_pages: Path):
    """Verify blank and whitespace-only pages are identified without inventing text."""
    result = extract_page_text(pdf_with_empty_and_whitespace_pages)

    assert result["total_pages"] == 4
    assert result["has_empty_pages"] is True
    # Pages 2 (blank) and 3 (whitespace) must be flagged
    assert result["empty_pages"] == [2, 3]

    assert result["pages"][0]["is_empty"] is False
    assert result["pages"][1]["is_empty"] is True
    assert result["pages"][1]["text"] == ""
    assert result["pages"][1]["char_count"] == 0

    assert result["pages"][2]["is_empty"] is True
    assert result["pages"][2]["text"] == ""
    assert result["pages"][2]["char_count"] == 0

    assert result["pages"][3]["is_empty"] is False


# ---------------------------------------------------------------------------
# Criterion 5: Missing file paths produce clear errors
# ---------------------------------------------------------------------------


def test_missing_file_path_raises_filenotfound(tmp_path: Path):
    """Verify nonexistent paths raise FileNotFoundError with clear message."""
    missing_path = tmp_path / "does_not_exist.pdf"
    with pytest.raises(FileNotFoundError) as exc_info:
        extract_page_text(missing_path)
    assert "File not found" in str(exc_info.value)


def test_empty_file_path_raises_valueerror():
    """Verify empty string or whitespace path raises ValueError."""
    with pytest.raises(ValueError, match="PDF file path cannot be empty"):
        extract_page_text(Path("   "))


# ---------------------------------------------------------------------------
# Criterion 6: Invalid or corrupted PDFs handled gracefully
# ---------------------------------------------------------------------------


def test_unsupported_file_extension_raises_valueerror(tmp_path: Path):
    """Verify non-.pdf files are rejected with a clear message."""
    txt_file = tmp_path / "document.txt"
    txt_file.write_text("Hello world")
    with pytest.raises(ValueError, match="Unsupported file type '.txt'"):
        extract_page_text(txt_file)


def test_zero_byte_pdf_raises_valueerror(tmp_path: Path):
    """Verify 0-byte PDF files are rejected clearly."""
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")
    with pytest.raises(ValueError, match="PDF file is empty \\(0 bytes\\)"):
        extract_page_text(empty_pdf)


def test_corrupted_pdf_raises_valueerror(tmp_path: Path):
    """Verify corrupted non-PDF binaries raise descriptive ValueError."""
    corrupted_pdf = tmp_path / "broken.pdf"
    corrupted_pdf.write_bytes(b"%PDF-1.4\nCorrupted random stream byte data that cannot parse")
    with pytest.raises(ValueError, match="Cannot open 'broken.pdf'"):
        extract_page_text(corrupted_pdf)


def test_directory_passed_as_file_raises_valueerror(tmp_path: Path):
    """Verify passing a directory path instead of a file raises ValueError."""
    sub_dir = tmp_path / "some_dir.pdf"
    sub_dir.mkdir()
    with pytest.raises(ValueError, match="Path is not a file"):
        extract_page_text(sub_dir)


# ---------------------------------------------------------------------------
# Criterion 7: Existing files are not overwritten unexpectedly
# ---------------------------------------------------------------------------


def test_existing_file_overwrite_protection(tmp_path: Path):
    """Verify existing output files are protected from accidental overwrite unless explicitly allowed."""
    out_file = tmp_path / "output.json"
    initial_data = {"existing": "data"}

    # Save once
    save_json_output(initial_data, out_file, overwrite=False)
    assert out_file.exists()

    new_data = {"new": "content"}

    # Attempting to save again without overwrite must raise FileExistsError
    with pytest.raises(FileExistsError, match="Output file already exists"):
        save_json_output(new_data, out_file, overwrite=False)

    # Content must remain unchanged
    saved_content = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved_content == initial_data

    # Now save with overwrite=True
    save_json_output(new_data, out_file, overwrite=True)
    overwritten_content = json.loads(out_file.read_text(encoding="utf-8"))
    assert overwritten_content == new_data


# ---------------------------------------------------------------------------
# Criterion 8: File paths containing spaces work correctly
# ---------------------------------------------------------------------------


def test_file_paths_containing_spaces(tmp_path: Path):
    """Verify directories and PDF filenames containing spaces are fully supported."""
    space_dir = tmp_path / "deep learning research papers"
    space_dir.mkdir(parents=True)
    pdf_path = space_dir / "my project report 2026.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 50), "Testing spaces in file path.", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    result = extract_page_text(pdf_path)
    assert result["source_file"] == "my project report 2026.pdf"
    assert "Testing spaces in file path." in result["pages"][0]["text"]

    out_dir = tmp_path / "processed output with spaces"
    out_file = out_dir / "my project report 2026_extracted.json"

    saved_path = save_json_output(result, out_file)
    assert saved_path.exists()
    assert saved_path.name == "my project report 2026_extracted.json"


# ---------------------------------------------------------------------------
# CLI Integration Tests
# ---------------------------------------------------------------------------


def test_cli_execution_success(multi_page_text_pdf: Path, tmp_path: Path):
    """Verify extract_pdf.py runs successfully via CLI with valid exit code 0."""
    out_dir = tmp_path / "cli_out"
    cmd = [
        sys.executable,
        "extract_pdf.py",
        str(multi_page_text_pdf),
        "--output-dir",
        str(out_dir),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "EXTRACTION SUCCESSFUL" in res.stdout
    assert (out_dir / "valid_multipage_extracted.json").exists()


def test_cli_execution_missing_file():
    """Verify extract_pdf.py reports error and exits with code 1 for missing files."""
    cmd = [sys.executable, "extract_pdf.py", "does_not_exist_file.pdf"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1
    assert "File not found" in res.stderr or "File not found" in res.stdout


def test_cli_execution_overwrite_flag(multi_page_text_pdf: Path, tmp_path: Path):
    """Verify CLI requires --overwrite to overwrite an existing JSON output."""
    out_dir = tmp_path / "cli_overwrite"
    cmd = [
        sys.executable,
        "extract_pdf.py",
        str(multi_page_text_pdf),
        "--output-dir",
        str(out_dir),
    ]

    # First run succeeds
    res1 = subprocess.run(cmd, capture_output=True, text=True)
    assert res1.returncode == 0

    # Second run without --overwrite fails with exit code 1
    res2 = subprocess.run(cmd, capture_output=True, text=True)
    assert res2.returncode == 1
    assert "Output file already exists" in res2.stderr

    # Third run with --overwrite succeeds
    cmd_with_overwrite = cmd + ["--overwrite"]
    res3 = subprocess.run(cmd_with_overwrite, capture_output=True, text=True)
    assert res3.returncode == 0
    assert "Overwrote existing file" in res3.stdout
