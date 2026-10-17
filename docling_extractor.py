"""docling_extractor.py - Milestone 3: Optional Structured Document Extraction with Docling.

Module: Person 1 (Document Processing & Knowledge Base Preparation)
Project: AMCRAG (Adaptive Multimodal Corrective RAG)

Provides:
- extract_docling_structured: Extracts headings, paragraphs, and tables via Docling.
- normalize_docling_document: Normalizes raw Docling output into AMCRAG's standard schema.
- extract_with_fallback: Tries Docling first, gracefully falling back to PyMuPDF if
  Docling is not installed or encounters an error.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from extract_pdf import extract_page_text

logger = logging.getLogger(__name__)


def is_docling_available() -> bool:
    """Check if IBM Docling library is installed and importable."""
    try:
        import docling  # noqa: F401
        return True
    except ImportError:
        return False


def normalize_docling_document(doc: Any, source_file: str) -> Dict[str, Any]:
    """Normalize a Docling Document object into AMCRAG's standard schema.

    Preserves full backward compatibility with Milestone 1 output schema while
    adding structured elements (headings, paragraphs, tables).

    Args:
        doc: The Docling document instance.
        source_file: Original filename string.

    Returns:
        A normalized dictionary conforming to the AMCRAG JSON schema.
    """
    total_pages = getattr(doc, "num_pages", None) or len(getattr(doc, "pages", []))
    if total_pages == 0:
        total_pages = 1

    page_headings: Dict[int, List[str]] = {p: [] for p in range(1, total_pages + 1)}
    page_paragraphs: Dict[int, List[str]] = {p: [] for p in range(1, total_pages + 1)}
    page_texts: Dict[int, List[str]] = {p: [] for p in range(1, total_pages + 1)}
    all_tables: List[Dict[str, Any]] = []

    # 1. Extract and normalize tables
    if hasattr(doc, "tables") and doc.tables:
        for idx, tbl in enumerate(doc.tables):
            # Page provenance
            p_no = 1
            if hasattr(tbl, "prov") and tbl.prov and len(tbl.prov) > 0:
                p_no = getattr(tbl.prov[0], "page_no", 1)
            p_no = max(1, min(p_no, total_pages))

            md_content = tbl.export_to_markdown() if hasattr(tbl, "export_to_markdown") else ""
            df = tbl.export_to_dataframe() if hasattr(tbl, "export_to_dataframe") else None

            headers = [str(c) for c in df.columns] if df is not None else []
            num_rows = len(df) if df is not None else 0
            num_cols = len(headers) if headers else 0

            table_dict = {
                "table_index": idx,
                "page_number": p_no,
                "num_rows": num_rows,
                "num_cols": num_cols,
                "headers": headers,
                "markdown": md_content,
            }
            all_tables.append(table_dict)

    # 2. Iterate items (headings, paragraphs, text)
    if hasattr(doc, "iterate_items"):
        for item, level in doc.iterate_items():
            p_no = 1
            if hasattr(item, "prov") and item.prov and len(item.prov) > 0:
                p_no = getattr(item.prov[0], "page_no", 1)
            p_no = max(1, min(p_no, total_pages))

            text = getattr(item, "text", "").strip()
            if not text:
                continue

            label = str(getattr(item, "label", "")).lower()

            if "heading" in label or "title" in label or "header" in label:
                page_headings[p_no].append(text)
            else:
                page_paragraphs[p_no].append(text)

            page_texts[p_no].append(text)
    else:
        # Fallback to general markdown export
        full_md = doc.export_to_markdown() if hasattr(doc, "export_to_markdown") else ""
        if full_md:
            page_paragraphs[1].append(full_md)
            page_texts[1].append(full_md)

    # 3. Assemble normalized page records
    pages_data: List[Dict[str, Any]] = []
    empty_pages: List[int] = []

    for p in range(1, total_pages + 1):
        combined_text = "\n\n".join(page_texts[p]).strip()
        is_empty = len(combined_text) == 0

        if is_empty:
            empty_pages.append(p)

        page_tables = [t for t in all_tables if t["page_number"] == p]

        pages_data.append(
            {
                "page_number": p,
                "text": combined_text,
                "char_count": len(combined_text),
                "is_empty": is_empty,
                "headings": page_headings[p],
                "paragraphs": page_paragraphs[p],
                "tables": page_tables,
            }
        )

    return {
        "source_file": source_file,
        "total_pages": total_pages,
        "empty_pages": empty_pages,
        "has_empty_pages": len(empty_pages) > 0,
        "backend_used": "docling",
        "fallback_occurred": False,
        "fallback_reason": None,
        "tables": all_tables,
        "pages": pages_data,
    }


def extract_docling_structured(pdf_path: Path) -> Dict[str, Any]:
    """Extract structured document elements (headings, tables, paragraphs) via Docling.

    Args:
        pdf_path: Path to the target PDF file.

    Returns:
        Normalized dictionary adhering to AMCRAG schema.

    Raises:
        ImportError: If docling is not installed.
        FileNotFoundError: If the target PDF does not exist.
        ValueError: If file is empty or corrupted.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"File not found: '{pdf_path.resolve()}'")

    if not is_docling_available():
        raise ImportError(
            "IBM Docling is not installed in the environment. "
            "Install it via `pip install docling` or use '--backend pymupdf'."
        )

    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    conv_result = converter.convert(str(pdf_path.resolve()))
    doc = conv_result.document

    return normalize_docling_document(doc, source_file=pdf_path.name)


def extract_with_fallback(
    pdf_path: Path,
    prefer_docling: bool = True,
) -> Dict[str, Any]:
    """Execute document extraction with automatic fallback from Docling to PyMuPDF.

    If prefer_docling is True:
        1. Tries Docling extraction.
        2. If Docling is uninstalled or fails with any exception, catches the error,
           logs the issue, and falls back to PyMuPDF extraction.
        3. Annotates output with backend_used='pymupdf_fallback' and fallback_reason.
    If prefer_docling is False:
        Extracts directly with PyMuPDF with backend_used='pymupdf'.

    Args:
        pdf_path: Target PDF path.
        prefer_docling: Whether to try Docling first.

    Returns:
        Structured output dictionary conforming to AMCRAG schema.
    """
    if not prefer_docling or not is_docling_available():
        res = extract_page_text(pdf_path)
        res["backend_used"] = "pymupdf"
        res["fallback_occurred"] = False
        res["fallback_reason"] = None
        res["tables"] = []
        for p in res["pages"]:
            p.setdefault("headings", [])
            p.setdefault("paragraphs", [p["text"]] if p["text"] else [])
            p.setdefault("tables", [])
        return res

    try:
        logger.info("Attempting Docling structured extraction for '%s'...", pdf_path.name)
        return extract_docling_structured(pdf_path)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "Docling extraction failed for '%s' (%s). Falling back to PyMuPDF.",
            pdf_path.name,
            reason,
        )

        # Fallback to PyMuPDF
        res = extract_page_text(pdf_path)
        res["backend_used"] = "pymupdf_fallback"
        res["fallback_occurred"] = True
        res["fallback_reason"] = reason
        res["tables"] = []
        for p in res["pages"]:
            p.setdefault("headings", [])
            p.setdefault("paragraphs", [p["text"]] if p["text"] else [])
            p.setdefault("tables", [])
        return res
