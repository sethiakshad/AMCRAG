"""Automated pytest test suite for docling_extractor.py (Milestone 3).

Covers:
1. Structured normalization of headings, paragraphs, and tables.
2. Page information preservation from provenance metadata.
3. Fallback when Docling is uninstalled or unavailable.
4. Fallback when Docling conversion raises a runtime exception.
5. No silent empty replacement on failure.
6. Reporting of backend_used, fallback_occurred, and fallback_reason.
7. CLI integration with --backend pymupdf, docling, and auto.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docling_extractor import (
    extract_docling_structured,
    extract_with_fallback,
    is_docling_available,
    normalize_docling_document,
)


# ---------------------------------------------------------------------------
# Mocks & Fixtures
# ---------------------------------------------------------------------------


class MockProv:
    """Mock provenance item specifying page number."""
    def __init__(self, page_no: int):
        self.page_no = page_no


class MockDocItem:
    """Mock document item (heading, paragraph)."""
    def __init__(self, text: str, label: str, page_no: int):
        self.text = text
        self.label = label
        self.prov = [MockProv(page_no)]


class MockDataFrame:
    """Mock dataframe representation for table export."""
    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = rows

    def __len__(self):
        return len(self.rows)


class MockTable:
    """Mock table item."""
    def __init__(self, page_no: int, headers, rows, md: str):
        self.prov = [MockProv(page_no)]
        self._df = MockDataFrame(headers, rows)
        self._md = md

    def export_to_markdown(self):
        return self._md

    def export_to_dataframe(self):
        return self._df


class MockDoclingDocument:
    """Mock IBM Docling document object."""
    def __init__(self, num_pages: int, items, tables):
        self.num_pages = num_pages
        self.items = items
        self.tables = tables

    def iterate_items(self):
        for item in self.items:
            yield item, 1


@pytest.fixture
def mock_structured_document():
    """Create a 2-page mock Docling document with headings, paragraphs, and a table."""
    items = [
        MockDocItem("Section 1: Introduction", "section_header", page_no=1),
        MockDocItem("AMCRAG is an adaptive retrieval framework.", "paragraph", page_no=1),
        MockDocItem("Section 2: Results & Benchmark", "section_header", page_no=2),
        MockDocItem("Evaluation shows 95% precision on complex queries.", "paragraph", page_no=2),
    ]
    tables = [
        MockTable(
            page_no=2,
            headers=["Model", "Accuracy", "Latency"],
            rows=[["AMCRAG", "95%", "120ms"], ["Baseline", "82%", "90ms"]],
            md="| Model | Accuracy | Latency |\n| --- | --- | --- |\n| AMCRAG | 95% | 120ms |",
        )
    ]
    return MockDoclingDocument(num_pages=2, items=items, tables=tables)


# ---------------------------------------------------------------------------
# 1. Normalization & Schema Conformance
# ---------------------------------------------------------------------------


def test_normalize_docling_document_structure(mock_structured_document):
    """Verify normalize_docling_document converts raw items into our standard JSON schema."""
    result = normalize_docling_document(mock_structured_document, source_file="paper.pdf")

    assert result["source_file"] == "paper.pdf"
    assert result["total_pages"] == 2
    assert result["backend_used"] == "docling"
    assert result["fallback_occurred"] is False
    assert result["fallback_reason"] is None

    # Check tables
    assert len(result["tables"]) == 1
    tbl = result["tables"][0]
    assert tbl["table_index"] == 0
    assert tbl["page_number"] == 2
    assert tbl["headers"] == ["Model", "Accuracy", "Latency"]
    assert tbl["num_rows"] == 2
    assert tbl["num_cols"] == 3
    assert "| Model | Accuracy |" in tbl["markdown"]

    # Check pages
    assert len(result["pages"]) == 2
    p1 = result["pages"][0]
    assert p1["page_number"] == 1
    assert "Section 1: Introduction" in p1["headings"]
    assert "AMCRAG is an adaptive retrieval framework." in p1["paragraphs"]
    assert p1["is_empty"] is False
    assert len(p1["tables"]) == 0

    p2 = result["pages"][1]
    assert p2["page_number"] == 2
    assert "Section 2: Results & Benchmark" in p2["headings"]
    assert len(p2["tables"]) == 1
    assert p2["tables"][0]["page_number"] == 2


# ---------------------------------------------------------------------------
# 2. Fallback Behavior
# ---------------------------------------------------------------------------


def test_fallback_when_docling_not_available(tmp_path: Path):
    """Verify that when Docling is not installed, extract_with_fallback uses PyMuPDF gracefully."""
    sample_pdf = Path("data/sample.pdf")

    with patch("docling_extractor.is_docling_available", return_value=False):
        result = extract_with_fallback(sample_pdf, prefer_docling=True)

        assert result["backend_used"] == "pymupdf"
        assert result["fallback_occurred"] is False
        assert result["total_pages"] == 3
        # Must contain actual text, not empty
        assert len(result["pages"][0]["text"]) > 0


def test_fallback_when_docling_throws_exception(tmp_path: Path):
    """Verify that if Docling raises an exception during conversion, PyMuPDF fallback engages."""
    sample_pdf = Path("data/sample.pdf")

    with patch("docling_extractor.is_docling_available", return_value=True):
        with patch("docling_extractor.extract_docling_structured", side_effect=RuntimeError("Docling native model OOM error")):
            result = extract_with_fallback(sample_pdf, prefer_docling=True)

            assert result["backend_used"] == "pymupdf_fallback"
            assert result["fallback_occurred"] is True
            assert "Docling native model OOM error" in result["fallback_reason"]

            # Must NOT silently produce empty text
            assert result["total_pages"] == 3
            assert len(result["pages"][0]["text"]) > 50
            assert "Adaptive Multimodal Corrective RAG" in result["pages"][0]["text"]


def test_strict_docling_mode_raises_error_when_unavailable():
    """Verify extract_docling_structured raises ImportError when Docling is missing (never empty output)."""
    with patch("docling_extractor.is_docling_available", return_value=False):
        with pytest.raises(ImportError, match="IBM Docling is not installed"):
            extract_docling_structured(Path("data/sample.pdf"))


# ---------------------------------------------------------------------------
# 3. CLI Integration Tests
# ---------------------------------------------------------------------------


def test_cli_default_backend_pymupdf(tmp_path: Path):
    """Verify default CLI invocation uses PyMuPDF backend."""
    out_dir = tmp_path / "cli_default"
    cmd = [
        sys.executable,
        "extract_pdf.py",
        "data/sample.pdf",
        "--output-dir",
        str(out_dir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Backend Used : pymupdf" in res.stdout
    assert (out_dir / "sample_extracted.json").exists()


def test_cli_auto_backend_with_fallback(tmp_path: Path):
    """Verify CLI --backend auto gracefully completes with PyMuPDF fallback when Docling is absent."""
    out_dir = tmp_path / "cli_auto"
    cmd = [
        sys.executable,
        "extract_pdf.py",
        "data/sample.pdf",
        "--backend",
        "auto",
        "--output-dir",
        str(out_dir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "EXTRACTION SUCCESSFUL" in res.stdout
    assert (out_dir / "sample_extracted.json").exists()


def test_cli_strict_docling_reports_notice_when_uninstalled():
    """Verify CLI --backend docling displays a clear dependency notice when Docling is uninstalled."""
    cmd = [
        sys.executable,
        "extract_pdf.py",
        "data/sample.pdf",
        "--backend",
        "docling",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    # If docling is not installed, it should exit with code 1 and show dependency notice
    if not is_docling_available():
        assert res.returncode == 1
        assert "IBM Docling is not installed" in res.stderr
