"""Automated pytest test suite for chunk_text.py (Milestone 2).

Covers:
1. Short text (smaller than chunk_size -> exactly 1 chunk).
2. Long text (multiple chunks, respecting chunk_size constraint).
3. Overlap verification (shared words between consecutive chunks, no duplicate chunks).
4. Page boundary crossing (chunks spanning multiple pages with start_page and end_page).
5. Empty text and empty document handling (returns 0 chunks gracefully).
6. Documents with empty pages interspersed.
7. Parameter validation (chunk_overlap >= chunk_size, negative sizes).
8. CLI integration on both PDF and JSON inputs.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from chunk_text import (
    build_word_stream,
    chunk_extracted_document,
    chunk_pdf,
    save_chunk_output,
)


# ---------------------------------------------------------------------------
# 1. Short Text
# ---------------------------------------------------------------------------


def test_short_text_single_chunk():
    """Verify text shorter than chunk_size produces exactly 1 chunk without splitting."""
    extracted = {
        "source_file": "short.pdf",
        "total_pages": 1,
        "pages": [
            {"page_number": 1, "text": "This is a brief text document."}
        ],
    }

    result = chunk_extracted_document(extracted, chunk_size=500, chunk_overlap=100)

    assert result["total_chunks"] == 1
    chunk = result["chunks"][0]
    assert chunk["chunk_id"] == "short_chunk_0001"
    assert chunk["chunk_index"] == 0
    assert chunk["chunk_text"] == "This is a brief text document."
    assert chunk["start_page"] == 1
    assert chunk["end_page"] == 1
    assert chunk["page_numbers"] == [1]
    assert chunk["char_count"] == len("This is a brief text document.")


# ---------------------------------------------------------------------------
# 2. Long Text & Chunk Size Adherence
# ---------------------------------------------------------------------------


def test_long_text_split_into_multiple_chunks():
    """Verify long text is divided into multiple sequential chunks."""
    long_text = " ".join([f"Sentence_{i} with some descriptive words." for i in range(50)])
    extracted = {
        "source_file": "long.pdf",
        "total_pages": 1,
        "pages": [{"page_number": 1, "text": long_text}],
    }

    target_size = 200
    target_overlap = 50
    result = chunk_extracted_document(extracted, chunk_size=target_size, chunk_overlap=target_overlap)

    assert result["total_chunks"] > 1

    # Every chunk should have stable unique IDs and respect size
    ids = [c["chunk_id"] for c in result["chunks"]]
    assert len(ids) == len(set(ids)), "Chunk IDs must be strictly unique"

    for i, chunk in enumerate(result["chunks"]):
        assert chunk["chunk_index"] == i
        # Chunks should not exceed chunk_size by more than one word length
        assert chunk["char_count"] <= target_size + 30
        assert chunk["chunk_text"].strip() != ""


# ---------------------------------------------------------------------------
# 3. Overlap Verification & No Duplicates
# ---------------------------------------------------------------------------


def test_overlap_contains_shared_text_and_no_duplicate_chunks():
    """Verify consecutive chunks share overlapping words and no identical chunks are produced."""
    text = (
        "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
        "nu xi omicron pi rho sigma tau upsilon phi chi psi omega."
    )
    extracted = {
        "source_file": "greek.pdf",
        "total_pages": 1,
        "pages": [{"page_number": 1, "text": text}],
    }

    result = chunk_extracted_document(extracted, chunk_size=60, chunk_overlap=20)

    chunks = result["chunks"]
    assert len(chunks) >= 2

    # Check for no duplicate chunks
    chunk_texts = [c["chunk_text"] for c in chunks]
    assert len(chunk_texts) == len(set(chunk_texts)), "Overlap must not cause duplicate chunk texts"

    # Check that consecutive chunks share content (overlap)
    for i in range(len(chunks) - 1):
        c1_words = set(chunks[i]["chunk_text"].split())
        c2_words = set(chunks[i + 1]["chunk_text"].split())
        shared_words = c1_words.intersection(c2_words)
        assert len(shared_words) > 0, f"Chunk {i} and {i+1} must share overlapping words"


def test_zero_overlap():
    """Verify chunking functions cleanly when overlap is 0."""
    text = "Word1 Word2 Word3 Word4 Word5 Word6 Word7 Word8 Word9 Word10."
    extracted = {
        "source_file": "no_overlap.pdf",
        "total_pages": 1,
        "pages": [{"page_number": 1, "text": text}],
    }

    result = chunk_extracted_document(extracted, chunk_size=30, chunk_overlap=0)
    assert result["total_chunks"] >= 2
    # With 0 overlap, consecutive chunks must have no shared words
    for i in range(len(result["chunks"]) - 1):
        c1_words = set(result["chunks"][i]["chunk_text"].split())
        c2_words = set(result["chunks"][i + 1]["chunk_text"].split())
        assert len(c1_words.intersection(c2_words)) == 0


# ---------------------------------------------------------------------------
# 4. Multi-Page Spanning & Page Boundaries
# ---------------------------------------------------------------------------


def test_chunk_spanning_multiple_pages():
    """Verify that a chunk spanning across page 1 and page 2 correctly records start_page and end_page."""
    extracted = {
        "source_file": "multipage.pdf",
        "total_pages": 2,
        "pages": [
            {"page_number": 1, "text": "Page one text ends here."},
            {"page_number": 2, "text": "Page two text begins right here."},
        ],
    }

    # Set chunk_size large enough to encompass both pages
    result = chunk_extracted_document(extracted, chunk_size=200, chunk_overlap=30)

    assert result["total_chunks"] == 1
    chunk = result["chunks"][0]
    assert chunk["start_page"] == 1
    assert chunk["end_page"] == 2
    assert chunk["page_numbers"] == [1, 2]
    assert "Page one text" in chunk["chunk_text"]
    assert "Page two text" in chunk["chunk_text"]


def test_chunk_page_transitions_on_smaller_chunks():
    """Verify page numbers update correctly as sliding window moves across pages."""
    extracted = {
        "source_file": "doc_transitions.pdf",
        "total_pages": 3,
        "pages": [
            {"page_number": 1, "text": "Page one has sentence A. Page one has sentence B."},
            {"page_number": 2, "text": "Page two has sentence C. Page two has sentence D."},
            {"page_number": 3, "text": "Page three has sentence E. Page three has sentence F."},
        ],
    }

    result = chunk_extracted_document(extracted, chunk_size=60, chunk_overlap=15)
    chunks = result["chunks"]

    # First chunk must start on page 1
    assert chunks[0]["start_page"] == 1
    # Last chunk must end on page 3
    assert chunks[-1]["end_page"] == 3

    # Check page_numbers list contains both start and end
    for c in chunks:
        assert c["start_page"] in c["page_numbers"]
        assert c["end_page"] in c["page_numbers"]
        assert c["start_page"] <= c["end_page"]


# ---------------------------------------------------------------------------
# 5. Empty Text & Empty Pages
# ---------------------------------------------------------------------------


def test_empty_document_produces_zero_chunks():
    """Verify a document with no text or empty pages returns total_chunks=0 without error."""
    extracted = {
        "source_file": "empty.pdf",
        "total_pages": 2,
        "pages": [
            {"page_number": 1, "text": ""},
            {"page_number": 2, "text": "   \n\t  "},
        ],
    }

    result = chunk_extracted_document(extracted, chunk_size=500, chunk_overlap=100)
    assert result["total_chunks"] == 0
    assert result["chunks"] == []


def test_document_with_empty_page_in_middle():
    """Verify an empty page in the middle of a document does not disrupt chunking."""
    extracted = {
        "source_file": "gap.pdf",
        "total_pages": 3,
        "pages": [
            {"page_number": 1, "text": "Content on first page."},
            {"page_number": 2, "text": ""},  # Blank page
            {"page_number": 3, "text": "Content on third page."},
        ],
    }

    result = chunk_extracted_document(extracted, chunk_size=200, chunk_overlap=20)
    assert result["total_chunks"] == 1
    chunk = result["chunks"][0]
    assert chunk["start_page"] == 1
    assert chunk["end_page"] == 3
    assert chunk["page_numbers"] == [1, 3]  # Page 2 has no text, so excluded from word origin


# ---------------------------------------------------------------------------
# 6. Parameter Validation
# ---------------------------------------------------------------------------


def test_invalid_chunk_overlap_raises():
    """Verify chunk_overlap >= chunk_size or negative values raise ValueError."""
    dummy = {"source_file": "d.pdf", "pages": [{"page_number": 1, "text": "abc"}]}

    with pytest.raises(ValueError, match="chunk_overlap .* must be strictly less than chunk_size"):
        chunk_extracted_document(dummy, chunk_size=100, chunk_overlap=100)

    with pytest.raises(ValueError, match="chunk_overlap .* must be strictly less than chunk_size"):
        chunk_extracted_document(dummy, chunk_size=100, chunk_overlap=150)

    with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
        chunk_extracted_document(dummy, chunk_size=100, chunk_overlap=-10)

    with pytest.raises(ValueError, match="chunk_size must be positive"):
        chunk_extracted_document(dummy, chunk_size=0, chunk_overlap=0)


# ---------------------------------------------------------------------------
# 7. CLI Execution on PDF and JSON Inputs
# ---------------------------------------------------------------------------


def test_cli_chunk_pdf_file(tmp_path: Path):
    """Verify chunk_text.py can directly process a PDF file via CLI."""
    out_dir = tmp_path / "cli_chunk_out"
    cmd = [
        sys.executable,
        "chunk_text.py",
        "data/sample.pdf",
        "--output-dir",
        str(out_dir),
        "--chunk-size",
        "300",
        "--chunk-overlap",
        "50",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "CHUNKING SUCCESSFUL" in res.stdout
    assert (out_dir / "sample_chunks.json").exists()

    with (out_dir / "sample_chunks.json").open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_chunks"] > 0
    assert data["chunks"][0]["chunk_id"].startswith("sample_chunk_")


def test_cli_chunk_json_file(tmp_path: Path):
    """Verify chunk_text.py can process a pre-extracted JSON file via CLI."""
    out_dir = tmp_path / "cli_chunk_json_out"
    cmd = [
        sys.executable,
        "chunk_text.py",
        "data/processed/sample_extracted.json",
        "--output-dir",
        str(out_dir),
        "--chunk-size",
        "250",
        "--chunk-overlap",
        "50",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "CHUNKING SUCCESSFUL" in res.stdout
    assert (out_dir / "sample_chunks.json").exists()
