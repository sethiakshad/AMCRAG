"""Docling-based structured document extractor for advanced layout, tables, and hierarchies."""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.config import Settings, default_settings
from app.extractors.base import BaseExtractor
from app.schemas.document import (
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionMethod,
    ExtractedTable,
    PageExtraction,
)

logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


class DoclingExtractor(BaseExtractor):
    """Structured extractor wrapping IBM's Docling framework."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or default_settings
        self._converter = None
        self._docling_available = self._check_docling_available()

    def _check_docling_available(self) -> bool:
        """Check if docling package can be imported."""
        try:
            import docling  # noqa: F401
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Return True if Docling is installed and importable."""
        return self._docling_available

    def _get_converter(self):
        """Lazy load the Docling DocumentConverter."""
        if not self._docling_available:
            raise ImportError(
                "Docling is not installed in the current Python environment. "
                "Install with `pip install docling` or rely on PyMuPDF fallback."
            )
        if self._converter is None:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
        return self._converter

    def extract(self, pdf_path: Path) -> DocumentExtractionResult:
        """Execute Docling extraction for the PDF file."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

        file_size = pdf_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"PDF file is completely empty: {pdf_path}")

        converter = self._get_converter()
        logger.info("Starting Docling conversion for %s", pdf_path.name)

        conv_res = converter.convert(str(pdf_path.resolve()))
        doc = conv_res.document

        content_hash = compute_file_sha256(pdf_path)
        doc_id = f"doc_{content_hash[:16]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Extract tables
        extracted_tables: List[ExtractedTable] = []
        table_idx = 0
        if hasattr(doc, "tables") and doc.tables:
            for tbl in doc.tables:
                page_no = 1
                if hasattr(tbl, "prov") and tbl.prov and len(tbl.prov) > 0:
                    page_no = getattr(tbl.prov[0], "page_no", 1)

                md = tbl.export_to_markdown() if hasattr(tbl, "export_to_markdown") else ""
                df = tbl.export_to_dataframe() if hasattr(tbl, "export_to_dataframe") else None

                headers = list(df.columns) if df is not None else []
                num_rows = len(df) if df is not None else 0
                num_cols = len(headers) if headers else 0

                extracted_tables.append(
                    ExtractedTable(
                        table_index=table_idx,
                        page_number=page_no,
                        num_rows=num_rows,
                        num_cols=num_cols,
                        caption=getattr(tbl, "caption", None),
                        markdown_content=md,
                        headers=[str(h) for h in headers],
                        raw_data=df.values.tolist() if df is not None else None,
                    )
                )
                table_idx += 1

        # 2. Extract pages and structural elements
        pages: List[PageExtraction] = []
        page_count = getattr(doc, "num_pages", None) or len(getattr(doc, "pages", []))
        if page_count == 0:
            # Fallback to checking max page number in provenance
            page_count = 1

        # Group text and headings by page
        page_texts: dict[int, List[str]] = {p: [] for p in range(1, page_count + 1)}
        page_headings: dict[int, List[str]] = {p: [] for p in range(1, page_count + 1)}

        if hasattr(doc, "iterate_items"):
            for item, level in doc.iterate_items():
                p_no = 1
                if hasattr(item, "prov") and item.prov and len(item.prov) > 0:
                    p_no = getattr(item.prov[0], "page_no", 1)

                p_no = max(1, min(p_no, page_count))
                item_text = getattr(item, "text", "").strip()
                if not item_text:
                    continue

                item_type = getattr(item, "label", "").lower()
                if "heading" in item_type or "title" in item_type:
                    page_headings[p_no].append(item_text)

                page_texts[p_no].append(item_text)
        else:
            # Markdown fallback from Docling
            full_md = doc.export_to_markdown() if hasattr(doc, "export_to_markdown") else ""
            page_texts[1].append(full_md)

        total_chars = 0
        for p in range(1, page_count + 1):
            p_text = "\n\n".join(page_texts[p]).strip()
            c_count = len(p_text)
            total_chars += c_count
            p_tables = [t for t in extracted_tables if t.page_number == p]

            pages.append(
                PageExtraction(
                    page_number=p,
                    text=p_text,
                    char_count=c_count,
                    has_images=False,
                    is_empty=(c_count == 0),
                    ocr_needed=(c_count < self.settings.ocr_min_chars_per_page),
                    headings=page_headings[p],
                    tables=p_tables,
                )
            )

        is_scanned = total_chars < self.settings.ocr_min_doc_chars
        warnings = []
        if is_scanned:
            warnings.append(
                f"Minimal text ({total_chars} chars) extracted by Docling; document may require dedicated OCR."
            )

        metadata = DocumentMetadata(
            document_id=doc_id,
            document_name=pdf_path.name,
            file_path=str(pdf_path.resolve()),
            file_size_bytes=file_size,
            page_count=page_count,
            upload_timestamp=now_iso,
            content_hash=content_hash,
        )

        return DocumentExtractionResult(
            metadata=metadata,
            extraction_method=ExtractionMethod.DOCLING,
            pages=pages,
            tables=extracted_tables,
            is_scanned=is_scanned,
            ocr_needed=is_scanned,
            warnings=warnings,
        )
