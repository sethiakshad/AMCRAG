"""schemas.py - Universal Data Schemas & Inter-Module Contracts for AMCRAG.

Module: AMCRAG Central Contracts (Person 1 & Person 2 Interoperability Layer)
Project: AMCRAG (Adaptive Multimodal Corrective RAG)

This module provides the canonical schemas used across the AMC-RAG project,
organized clearly by subsystem responsibility:
- PERSON 1: Document Processing, Extraction & Knowledge Base Schemas
- PERSON 2: Dense & Sparse Text Retrieval, RRF Fusion & Retrieval Candidates
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


# =============================================================================
# PERSON 1: Document Ingestion, PDF Processing & Chunking Schemas
# Teammate: Person 1 (Document Processing & Knowledge Base)
# =============================================================================

from app.schemas.chunk import ChunkMetadata, DocumentChunk, ProcessedDocumentOutput
from app.schemas.document import (
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionMethod,
    ExtractedTable,
    PageExtraction,
    PageRenderInfo,
)


# =============================================================================
# PERSON 2: Dense & Sparse Text Retrieval, RRF Fusion & Candidates
# Teammate: Person 2 / Om Khapekar (Dense/Sparse Text Retrieval & Hybrid Fusion)
# =============================================================================

class ScoredCandidate(BaseModel):
    """
    Intermediate scored candidate passage from a single retrieval channel
    (Dense BGE vector search, Sparse BM25 lexical search, or ColPali visual retrieval).
    Owner: Person 2 (Om Khapekar)
    """
    chunk_id: str = Field(..., description="Unique chunk or page identifier")
    score: float = Field(..., description="Channel-specific raw score (cosine similarity, BM25, etc.)")
    rank: int = Field(..., description="Ordinal rank position in channel results (1-indexed)")
    modality: str = Field(default="text", description="Candidate modality ('text' or 'visual_page')")
    candidate_type: str = Field(default="text_chunk", description="'text_chunk' or 'visual_page'")
    document_id: str = Field(default="", description="Parent document identifier")
    page_number: int = Field(default=1, description="Primary 1-indexed page number")
    text: str = Field(default="", description="Extracted passage text or visual page text")
    source_filename: Optional[str] = Field(default=None, description="Source filename of parent document")
    page_start: Optional[int] = Field(default=1, description="Starting page span (1-indexed)")
    page_end: Optional[int] = Field(default=1, description="Ending page span (1-indexed)")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Layout metadata (headings, bbox coordinates, table/figure tags)"
    )

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _sync_candidate_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "candidate_type" in data and ("modality" not in data or not data.get("modality")):
                data["modality"] = "visual_page" if data["candidate_type"] == "visual_page" else "text"
            elif "modality" in data and ("candidate_type" not in data or not data.get("candidate_type")):
                data["candidate_type"] = "visual_page" if data["modality"] == "visual_page" else "text_chunk"
            if hasattr(data.get("metadata"), "model_dump"):
                data["metadata"] = data["metadata"].model_dump()
        return data

    @property
    def candidate_id(self) -> str:
        """Alias for chunk_id."""
        return self.chunk_id


class RetrievalResult(BaseModel):
    """
    Universal retrieval candidate emitted by the Hybrid Retrieval engine.
    Unified hybrid retrieval result produced by Reciprocal Rank Fusion (RRF).
    Fully aligned with Section 10.1 RetrievalCandidate specification and
    matches Person 4's expected input for CRAG evaluation.
    Owner: Person 2 (Om Khapekar)
    """
    chunk_id: str = Field(..., description="Unique chunk or page candidate identifier")
    document_id: str = Field(..., description="Parent document identifier")
    page_number: int = Field(..., description="Primary 1-indexed page number")
    text: str = Field(default="", description="Passage text content")
    modality: str = Field(default="text", description="'text' from this engine, or 'visual_page' from ColPali")
    source_filename: Optional[str] = Field(default="", description="Source filename for citations")
    page_start: Optional[int] = Field(default=1, description="Starting page span (1-indexed)")
    page_end: Optional[int] = Field(default=1, description="Ending page span (1-indexed)")
    dense_score: Optional[float] = Field(default=None, description="Raw BGE cosine similarity score")
    sparse_score: Optional[float] = Field(default=None, description="Raw BM25 lexical score")
    dense_rank: Optional[int] = Field(default=None, description="Rank in dense retrieval (1-indexed)")
    sparse_rank: Optional[int] = Field(default=None, description="Rank in sparse retrieval (1-indexed)")
    fused_score: float = Field(default=0.0, description="Reciprocal Rank Fusion (RRF) combined score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Preserved layout and citation metadata")

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _sync_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("source_filename") and data.get("document_id"):
                data["source_filename"] = data.get("document_id")
            if hasattr(data.get("metadata"), "model_dump"):
                data["metadata"] = data["metadata"].model_dump()
        return data

    @property
    def candidate_id(self) -> str:
        """Alias for chunk_id required by Person 4 CRAG Evaluator."""
        return self.chunk_id

    @property
    def candidate_type(self) -> str:
        """Alias returning 'visual_page' or 'text_chunk' for Person 4 CRAG Evaluator."""
        return "visual_page" if self.modality == "visual_page" else "text_chunk"

    @property
    def retrieval_score(self) -> float:
        """Alias for fused_score required by Person 4 CRAG Evaluator."""
        return self.fused_score

    def get_evaluable_content(self) -> str:
        """Return text content or fallback to metadata caption/title for visual pages."""
        if self.text and self.text.strip():
            return self.text.strip()
        for k in ("caption", "description", "title", "section"):
            if self.metadata.get(k):
                return str(self.metadata[k])
        filename = self.source_filename or self.document_id or "document"
        return f"{filename} Page {self.page_number}"


# Universal alias conforming to Section 10.1 of Central Project Documentation
RetrievalCandidate = RetrievalResult


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Person 1
    "ChunkMetadata",
    "DocumentChunk",
    "DocumentExtractionResult",
    "DocumentMetadata",
    "ExtractionMethod",
    "ExtractedTable",
    "PageExtraction",
    "PageRenderInfo",
    "ProcessedDocumentOutput",
    # Person 2
    "ScoredCandidate",
    "RetrievalResult",
    "RetrievalCandidate",
]
