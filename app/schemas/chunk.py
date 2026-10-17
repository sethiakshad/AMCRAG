"""Chunk-level data models and output contract for downstream modules."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from app.schemas.document import DocumentMetadata, ExtractedTable, PageRenderInfo


class ChunkMetadata(BaseModel):
    """Metadata bound to every individual chunk for citation and traceability.

    Supports both dictionary-style access (`meta['section']`) and attribute
    access (`meta.section_heading`) to maintain 100% interoperability with
    all AMCRAG teammates.
    """

    document_id: str = Field(default="", description="Unique deterministic identifier of the source document")
    document_name: str = Field(default="", description="Original filename of the PDF")
    source_filename: str = Field(default="", description="Source filename alias for document_name")
    page_numbers: List[int] = Field(default_factory=list, description="List of 1-indexed page numbers covered by this chunk")
    chunk_id: str = Field(default="", description="Unique chunk identifier e.g. <doc_id>_c0001")
    chunk_index: int = Field(default=0, description="0-indexed position of chunk in document sequence")
    section: Optional[str] = Field(default=None, description="Primary section context (e.g. 'Financial Results')")
    section_heading: Optional[str] = Field(default=None, description="Nearest section heading context")
    headings: List[str] = Field(default_factory=list, description="Hierarchical heading trail")
    extraction_method: str = Field(default="pymupdf", description="Extraction backend used (docling, pymupdf, fallback)")
    source_citation: str = Field(
        default="",
        description="Formatted citation string for the final answer synthesis (e.g. 'report.pdf, pp. 2-3')",
    )
    char_count: int = Field(default=0, description="Length of chunk text in characters")
    token_estimate: int = Field(default=0, description="Approximate token count (characters / 4)")
    table: bool = Field(default=False, description="True if chunk originated from a structured table")
    bbox: Optional[List[float]] = Field(default=None, description="Bounding box coordinates [x0, y0, x1, y1]")

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _sync_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "section" not in data and "section_heading" in data:
                data["section"] = data["section_heading"]
            if "section_heading" not in data and "section" in data:
                data["section_heading"] = data["section"]
            if "source_filename" not in data and "document_name" in data:
                data["source_filename"] = data["document_name"]
            if "document_name" not in data and "source_filename" in data:
                data["document_name"] = data["source_filename"]
            if "headings" not in data and data.get("section"):
                data["headings"] = [data["section"]]
        return data

    def __getitem__(self, item: str) -> Any:
        if item == "section":
            return getattr(self, "section", None) or getattr(self, "section_heading", None)
        if item == "section_heading":
            return getattr(self, "section_heading", None) or getattr(self, "section", None)
        if item == "document_name":
            return getattr(self, "document_name", None) or getattr(self, "source_filename", None)
        if item == "source_filename":
            return getattr(self, "source_filename", None) or getattr(self, "document_name", None)
        return getattr(self, item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.__dict__

    def get(self, item: str, default: Any = None) -> Any:
        try:
            val = self[item]
            return val if val is not None else default
        except (KeyError, AttributeError):
            return getattr(self, item, default)


class DocumentChunk(BaseModel):
    """Unit of text ingestion prepared for downstream embeddings and hybrid retrieval.

    Conforms strictly to Person 2's DocumentChunk input contract while
    preserving backwards-compatible fields and properties for Person 1.
    """

    chunk_id: str = Field(..., description="Unique deterministic chunk identifier or UUID")
    document_id: str = Field(default="", description="Parent document identifier")
    page_number: int = Field(default=1, description="Primary 1-indexed page number")
    text: str = Field(default="", description="Extracted passage text for dense & sparse indexing")
    source_filename: str = Field(default="", description="Source filename of parent document")
    page_start: int = Field(default=1, description="Starting page span (1-indexed)")
    page_end: int = Field(default=1, description="Ending page span (1-indexed)")
    chunk_text: Optional[str] = Field(default=None, description="Backward-compatible alias for text")
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata, description="Rich layout, section, and citation metadata")

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _harmonize_chunk(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Harmonize text and chunk_text
        if "text" not in data and "chunk_text" in data:
            data["text"] = data["chunk_text"]
        elif "text" in data and "chunk_text" not in data:
            data["chunk_text"] = data["text"]
        elif "text" in data and "chunk_text" in data:
            if not data["text"]:
                data["text"] = data["chunk_text"]
            elif not data["chunk_text"]:
                data["chunk_text"] = data["text"]

        meta = data.get("metadata", {})
        if isinstance(meta, BaseModel):
            meta_dict = meta.model_dump()
        elif isinstance(meta, dict):
            meta_dict = dict(meta)
        else:
            meta_dict = {}

        if not data.get("document_id"):
            data["document_id"] = meta_dict.get("document_id", "unknown_doc")

        if not data.get("source_filename"):
            data["source_filename"] = (
                data.get("source_file")
                or data.get("document_name")
                or meta_dict.get("document_name")
                or meta_dict.get("source_filename")
                or "unknown.pdf"
            )

        pages = data.get("page_numbers") or meta_dict.get("page_numbers") or [data.get("page_number", 1)]
        if "page_start" not in data:
            data["page_start"] = data.get("start_page") or (min(pages) if pages else 1)
        if "page_end" not in data:
            data["page_end"] = data.get("end_page") or (max(pages) if pages else 1)
        if "page_number" not in data or data.get("page_number") == 1:
            data["page_number"] = data["page_start"]

        # Ensure metadata has document and page fields aligned
        if "document_id" not in meta_dict:
            meta_dict["document_id"] = data["document_id"]
        if "document_name" not in meta_dict:
            meta_dict["document_name"] = data["source_filename"]
        if "source_filename" not in meta_dict:
            meta_dict["source_filename"] = data["source_filename"]
        if "page_numbers" not in meta_dict:
            meta_dict["page_numbers"] = list(range(data["page_start"], data["page_end"] + 1))
        if "chunk_id" not in meta_dict:
            meta_dict["chunk_id"] = data.get("chunk_id", "")
        if "char_count" not in meta_dict and data.get("text"):
            meta_dict["char_count"] = len(data["text"])
            meta_dict["token_estimate"] = max(1, len(data["text"]) // 4)

        data["metadata"] = meta_dict
        return data

    @property
    def document_name(self) -> str:
        """Backward-compatible alias for source_filename."""
        return self.source_filename

    @property
    def start_page(self) -> int:
        """Backward-compatible alias for page_start."""
        return self.page_start

    @property
    def end_page(self) -> int:
        """Backward-compatible alias for page_end."""
        return self.page_end

    @property
    def page_numbers(self) -> List[int]:
        """Backward-compatible alias for page span list."""
        return list(range(self.page_start, self.page_end + 1))


class ProcessedDocumentOutput(BaseModel):
    """Complete structured JSON schema produced by Document Processing Module.

    This contract is consumed by:
    - Person 2 (Dense & Sparse Indexing: Qdrant, BM25 via Plug 1)
    - Person 3 (ColPali Visual Indexing using rendered_pages)
    - Person 4 (Adaptive Retrieval, Evaluation, and Citation Generation)
    - Person 5 (FastAPI Orchestrator)
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
        description="Text chunks with complete metadata for dense/sparse indexing conforming to Person 2",
    )
    total_chunks: int = Field(default=0, description="Total number of chunks produced")
    tables: List[ExtractedTable] = Field(default_factory=list, description="Structured tables extracted from the document")
    warnings: List[str] = Field(default_factory=list, description="Any warnings logged during execution")
    error_message: Optional[str] = Field(default=None, description="Detailed error message if processing failed")

    def to_retriever_chunks(self) -> List[DocumentChunk]:
        """Return chunks ready for Person 2's retriever.index_knowledge_base()."""
        return self.chunks

