"""Chunk-level data models and output contract for downstream modules."""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.document import DocumentMetadata, ExtractedTable, PageRenderInfo


class ChunkMetadata(BaseModel):
    """Metadata bound to every individual chunk for citation and traceability."""

    document_id: str = Field(..., description="Unique deterministic identifier of the source document")
    document_name: str = Field(..., description="Original filename of the PDF")
    page_numbers: List[int] = Field(..., description="List of 1-indexed page numbers covered by this chunk")
    chunk_id: str = Field(..., description="Unique chunk identifier e.g. <doc_id>_c0001")
    chunk_index: int = Field(..., description="0-indexed position of chunk in document sequence")
    section_heading: Optional[str] = Field(default=None, description="Nearest section heading context")
    extraction_method: str = Field(..., description="Method used to extract this text (docling, pymupdf, fallback)")
    source_citation: str = Field(
        ...,
        description="Formatted citation string for the final answer synthesis (e.g. 'report.pdf, pp. 2-3')",
    )
    char_count: int = Field(..., description="Length of chunk text in characters")
    token_estimate: int = Field(..., description="Approximate token count (characters / 4)")


class DocumentChunk(BaseModel):
    """Unit of text ingestion prepared for downstream embeddings and hybrid retrieval."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    chunk_text: str = Field(..., description="Clean text content of the chunk")
    metadata: ChunkMetadata = Field(..., description="Traceable metadata for RAG citation")


class ProcessedDocumentOutput(BaseModel):
    """Complete structured JSON schema produced by Document Processing Module.

    This contract is consumed by:
    - Person 2 (Dense & Sparse Indexing: Qdrant, BM25)
    - Person 3 (ColPali Visual Indexing using rendered_pages)
    - Person 4 (Adaptive Retrieval, Evaluation, and Citation Generation)
    """

    document_id: str
    document_name: str
    metadata: DocumentMetadata
    status: str = Field(
        ...,
        description="Overall status: 'success', 'warning_ocr_needed', 'duplicate_skipped', or 'failed'",
    )
    is_scanned: bool = Field(default=False, description="True if document appears to be scanned raster images")
    ocr_needed: bool = Field(default=False, description="True if downstream OCR pipeline must be invoked")
    extraction_method: str = Field(..., description="Method used: docling, pymupdf, or pymupdf_fallback")
    rendered_pages: List[PageRenderInfo] = Field(
        default_factory=list,
        description="Rendered page image paths and resolutions for downstream ColPali visual indexing",
    )
    chunks: List[DocumentChunk] = Field(
        default_factory=list,
        description="Text chunks with complete metadata for dense/sparse indexing",
    )
    total_chunks: int = Field(default=0, description="Total number of chunks produced")
    tables: List[ExtractedTable] = Field(default_factory=list, description="Structured tables extracted from the document")
    warnings: List[str] = Field(default_factory=list, description="Any warnings logged during execution")
    error_message: Optional[str] = Field(default=None, description="Detailed error message if processing failed")
