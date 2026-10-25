"""PyMuPDF (fitz) based PDF text and structure extractor with OCR/scanned detection."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

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
    """Compute SHA-256 hash of a file for deterministic ID and duplicate detection."""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


class PyMuPDFExtractor(BaseExtractor):
    """High-speed text and layout extractor utilizing PyMuPDF (fitz)."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or default_settings

    def extract(
        self,
        pdf_path: Path,
        method_label: ExtractionMethod = ExtractionMethod.PYMUPDF,
    ) -> DocumentExtractionResult:
        """Extract text, tables, and detect scanned characteristics."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

        file_size = pdf_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"PDF file is completely empty (0 bytes): {pdf_path}")

        content_hash = compute_file_sha256(pdf_path)
        doc_id = f"doc_{content_hash[:16]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        warnings: List[str] = []

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error("Failed to open PDF %s: %s", pdf_path, e)
            raise ValueError(f"Corrupted or invalid PDF format: {e}") from e

        try:
            if doc.is_encrypted:
                raise ValueError("PDF is encrypted/password-protected and cannot be processed.")

            page_count = len(doc)
            if page_count == 0:
                warnings.append("Document has 0 pages.")

            # Pass 1: Detect repetitive header/footer watermarks across pages
            from collections import Counter
            line_occurrences = Counter()
            sample_count = min(page_count, 100)
            for s_idx in range(sample_count):
                p = doc[s_idx]
                p_lines = [ln.strip() for ln in p.get_text().splitlines() if ln.strip()]
                for unique_ln in set(p_lines):
                    line_occurrences[unique_ln] += 1

            watermark_lines = {
                ln for ln, count in line_occurrences.items()
                if count >= max(3, int(sample_count * 0.35)) and len(ln) < 160
            }
            if watermark_lines:
                logger.info("Detected %d repetitive watermark/header lines in %s: %s", len(watermark_lines), pdf_path.name, list(watermark_lines)[:3])

            pages: List[PageExtraction] = []
            all_tables: List[ExtractedTable] = []
            total_doc_chars = 0
            total_substantive_chars = 0
            scanned_pages_count = 0
            global_table_idx = 0

            for page_idx in range(page_count):
                page_num = page_idx + 1
                page = doc[page_idx]

                # 1. Text extraction and block inspection
                text, headings = self._extract_text_and_headings(page)
                
                # Filter out repetitive watermarks to measure substantive content
                clean_lines = [
                    ln for ln in text.splitlines()
                    if ln.strip() and ln.strip() not in watermark_lines
                ]
                substantive_text = "\n".join(clean_lines).strip()
                substantive_chars = len(substantive_text)
                
                # If page only had watermarks, use substantive text to avoid indexing pure watermarks
                page_text = substantive_text if substantive_chars > 0 else text.strip()
                char_count = len(page_text)
                total_doc_chars += char_count
                total_substantive_chars += substantive_chars

                # 2. Image inspection for scanned check
                images = page.get_images(full=True)
                has_images = len(images) > 0

                is_empty = substantive_chars == 0
                page_ocr_needed = False

                # Scanned page detection heuristic
                if substantive_chars < self.settings.ocr_min_chars_per_page:
                    if has_images or is_empty:
                        page_ocr_needed = True
                        scanned_pages_count += 1
                        logger.warning(
                            "Page %d of %s has low substantive text (%d chars) and %d images; flagging for OCR.",
                            page_num,
                            pdf_path.name,
                            substantive_chars,
                            len(images),
                        )

                # 3. Table extraction
                page_tables, global_table_idx = self._extract_tables(page, page_num, global_table_idx)
                all_tables.extend(page_tables)

                pages.append(
                    PageExtraction(
                        page_number=page_num,
                        text=page_text,
                        char_count=char_count,
                        has_images=has_images,
                        is_empty=is_empty,
                        ocr_needed=page_ocr_needed,
                        headings=headings,
                        tables=page_tables,
                    )
                )

            # Document-level scanned / OCR-needed determination
            is_scanned = False
            ocr_needed = False

            if page_count > 0:
                is_scanned_ratio = (scanned_pages_count / page_count) >= 0.6
                if total_substantive_chars < self.settings.ocr_min_doc_chars or is_scanned_ratio:
                    is_scanned = True
                    ocr_needed = True
                    msg = (
                        f"Document '{pdf_path.name}' appears to be a scanned PDF or contains minimal substantive text "
                        f"({total_substantive_chars} characters across {page_count} pages; {scanned_pages_count}/{page_count} pages flagged). "
                        "OCR is required for text indexing."
                    )
                    warnings.append(msg)
                    logger.warning(msg)
                elif scanned_pages_count > 0:
                    ocr_needed = True
                    msg = (
                        f"Document '{pdf_path.name}' has {scanned_pages_count}/{page_count} pages "
                        f"with minimal text requiring OCR."
                    )
                    warnings.append(msg)

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
                extraction_method=method_label,
                pages=pages,
                tables=all_tables,
                is_scanned=is_scanned,
                ocr_needed=ocr_needed,
                warnings=warnings,
            )

        finally:
            doc.close()

    def _extract_text_and_headings(self, page: fitz.Page) -> Tuple[str, List[str]]:
        """Extract text content and infer section headings from font sizes/blocks."""
        blocks = page.get_text("blocks")
        text_lines: List[str] = []
        headings: List[str] = []

        # Get detailed spans for font-size based heading detection
        text_page = page.get_text("dict")
        font_sizes: List[float] = []

        for block in text_page.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            font_sizes.append(span.get("size", 10.0))

        # Heuristic: base font is usually median or ~10-12pt. Headings > 1.25x avg
        avg_font = (sum(font_sizes) / len(font_sizes)) if font_sizes else 11.0

        for block in text_page.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    line_text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                    if not line_text:
                        continue
                    max_span_size = max((span.get("size", 10.0) for span in line.get("spans", [])), default=10.0)

                    # Heading heuristic: larger font size or short uppercase title line
                    if (max_span_size > avg_font * 1.2 and len(line_text) < 120) or (
                        line_text.isupper() and len(line_text) < 80 and not line_text.endswith(".")
                    ):
                        if line_text not in headings:
                            headings.append(line_text)

        # Standard plain text
        raw_text = page.get_text("text")
        return raw_text, headings

    def _extract_tables(
        self,
        page: fitz.Page,
        page_num: int,
        start_index: int,
    ) -> Tuple[List[ExtractedTable], int]:
        """Extract tables from the page using PyMuPDF's table detection."""
        extracted: List[ExtractedTable] = []
        current_idx = start_index

        try:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for tab in tabs.tables:
                    df_data = tab.extract()
                    if not df_data or len(df_data) < 2:
                        continue

                    headers = [str(col).strip() if col is not None else f"Col_{i}" for i, col in enumerate(df_data[0])]
                    rows = df_data[1:]
                    num_rows = len(rows)
                    num_cols = len(headers)

                    # Build markdown table representation
                    md_lines = [
                        "| " + " | ".join(headers) + " |",
                        "| " + " | ".join(["---"] * num_cols) + " |",
                    ]
                    for row in rows:
                        cells = [str(c).replace("\n", " ").strip() if c is not None else "" for c in row]
                        # Pad or truncate row to header length
                        if len(cells) < num_cols:
                            cells.extend([""] * (num_cols - len(cells)))
                        cells = cells[:num_cols]
                        md_lines.append("| " + " | ".join(cells) + " |")

                    markdown_str = "\n".join(md_lines)

                    extracted.append(
                        ExtractedTable(
                            table_index=current_idx,
                            page_number=page_num,
                            num_rows=num_rows,
                            num_cols=num_cols,
                            caption=None,
                            markdown_content=markdown_str,
                            headers=headers,
                            raw_data=df_data,
                        )
                    )
                    current_idx += 1
        except Exception as e:
            logger.debug("Table extraction not available or encountered exception on page %d: %s", page_num, e)

        return extracted, current_idx
