"""Document-level schemas and data models for extracted PDF contents."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtractionMethod(str, Enum):
    """Method used for extracting document content."""

    DOCLING = "docling"
    PYMUPDF = "pymupdf"
    PYMUPDF_FALLBACK = "pymupdf_fallback"
    FAILED = "failed"


class PageRenderInfo(BaseModel):
    """Information regarding a rendered page image for downstream ColPali module."""

    page_number: int = Field(..., description="1-indexed page number")
    image_path: str = Field(..., description="Relative or absolute path to the rendered PNG image")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    dpi: int = Field(..., description="Rendered DPI resolution")


class ExtractedTable(BaseModel):
    """Structured table extracted from document (via Docling or PyMuPDF)."""

    table_index: int = Field(..., description="Sequential index of table in document")
    page_number: int = Field(..., description="1-indexed page number where table resides")
    num_rows: int = Field(..., description="Number of table rows")
    num_cols: int = Field(..., description="Number of table columns")
    caption: Optional[str] = Field(default=None, description="Table caption or title if found")
    markdown_content: str = Field(..., description="Markdown representation of the table")
    headers: List[str] = Field(default_factory=list, description="Column headers")
    raw_data: Optional[List[List[Any]]] = Field(default=None, description="2D matrix of cell values")


class PageExtraction(BaseModel):
    """Text and structural content extracted from a single PDF page."""

    page_number: int = Field(..., description="1-indexed page number")
    text: str = Field(..., description="Extracted clean text content")
    char_count: int = Field(..., description="Number of characters extracted")
    has_images: bool = Field(default=False, description="Whether the page contains embedded raster images")
    is_empty: bool = Field(default=False, description="Whether no text was extracted from this page")
    ocr_needed: bool = Field(default=False, description="Whether page likely requires OCR (scanned image page)")
    headings: List[str] = Field(default_factory=list, description="Section headings detected on this page")
    tables: List[ExtractedTable] = Field(default_factory=list, description="Tables identified on this page")


class DocumentMetadata(BaseModel):
    """Core metadata identifying an uploaded document."""

    document_id: str = Field(..., description="Deterministic content-based hash (SHA-256) of file")
    document_name: str = Field(..., description="Original filename of the uploaded PDF")
    file_path: str = Field(..., description="Filesystem path of the stored upload")
    file_size_bytes: int = Field(..., description="Size of the file in bytes")
    page_count: int = Field(..., description="Total number of pages")
    upload_timestamp: str = Field(..., description="ISO 8601 timestamp of processing")
    content_hash: str = Field(..., description="SHA-256 checksum of raw file bytes")


class DocumentExtractionResult(BaseModel):
    """Intermediate extraction result before chunking."""

    metadata: DocumentMetadata
    extraction_method: ExtractionMethod
    pages: List[PageExtraction] = Field(default_factory=list)
    tables: List[ExtractedTable] = Field(default_factory=list)
    is_scanned: bool = Field(default=False, description="Flagged if document text is absent or near zero across pages")
    ocr_needed: bool = Field(default=False, description="Explicit warning that OCR is required for indexing")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings encountered during extraction")
    error_message: Optional[str] = Field(default=None, description="Fatal error message if extraction failed")
