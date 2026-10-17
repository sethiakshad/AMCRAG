"""schemas.py - Universal Data Schemas & Inter-Module Contracts for AMCRAG.

Module: AMCRAG Central Contracts (Person 1 & Person 2 Interoperability Layer)
Project: AMCRAG (Adaptive Multimodal Corrective RAG)

This module provides the canonical schemas used across the AMC-RAG project:
- DocumentChunk: Ingestion contract consumed by Person 2 (Qdrant & BM25)
- ChunkMetadata: Citation and provenance metadata
- ScoredCandidate: Candidate representation from single retrieval channels
- RetrievalResult: Fused candidate output from Reciprocal Rank Fusion (RRF)
- RetrievalCandidate: Canonical alias matching Section 10.1 of Project Documentation
- ProcessedDocumentOutput: Complete output contract from Person 1
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Re-export Person 1 core schemas
from app.schemas.chunk import ChunkMetadata, DocumentChunk, ProcessedDocumentOutput
from app.schemas.document import (
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionMethod,
    ExtractedTable,
    PageExtraction,
    PageRenderInfo,
)


class ScoredCandidate(BaseModel):
    """Scored candidate passage from a single retrieval channel (dense, sparse, or visual)."""

    chunk_id: str = Field(..., description="Unique chunk or page identifier")
    score: float = Field(..., description="Channel-specific raw score (cosine similarity, BM25, etc.)")
    rank: int = Field(..., description="Ordinal rank position in channel results (1-indexed)")
    modality: str = Field(default="text", description="Candidate modality ('text' or 'visual_page')")
    document_id: str = Field(default="", description="Parent document identifier")
    page_number: int = Field(default=1, description="Primary 1-indexed page number")
    text: str = Field(default="", description="Extracted passage text or visual page text")
    source_filename: str = Field(default="", description="Source filename of parent document")
    page_start: int = Field(default=1, description="Starting page span (1-indexed)")
    page_end: int = Field(default=1, description="Ending page span (1-indexed)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary layout and provenance metadata")


class RetrievalResult(BaseModel):
    """Unified hybrid retrieval result produced by Reciprocal Rank Fusion (RRF).

    Conforms strictly to Section 10.1 of Central Documentation and matches
    Person 4's expected input for CRAG evaluation.
    """

    chunk_id: str = Field(..., description="Unique chunk or page candidate identifier")
    document_id: str = Field(..., description="Parent document identifier")
    page_number: int = Field(..., description="Primary 1-indexed page number")
    text: str = Field(default="", description="Passage text content")
    modality: str = Field(default="text", description="Modality of candidate ('text' or 'visual_page')")
    source_filename: str = Field(..., description="Source filename for citations")
    page_start: int = Field(default=1, description="Starting page span (1-indexed)")
    page_end: int = Field(default=1, description="Ending page span (1-indexed)")
    dense_score: Optional[float] = Field(default=None, description="Raw BGE cosine similarity score")
    sparse_score: Optional[float] = Field(default=None, description="Raw BM25 lexical score")
    dense_rank: Optional[int] = Field(default=None, description="Rank in dense retrieval (1-indexed)")
    sparse_rank: Optional[int] = Field(default=None, description="Rank in sparse retrieval (1-indexed)")
    fused_score: float = Field(default=0.0, description="RRF combined reciprocal score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Preserved layout and citation metadata")

    model_config = {"extra": "allow"}

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
        return f"{self.source_filename} Page {self.page_number}"


# Canonical alias matching Section 10.1 of Central Project Documentation
RetrievalCandidate = RetrievalResult


__all__ = [
    "ChunkMetadata",
    "DocumentChunk",
    "DocumentExtractionResult",
    "DocumentMetadata",
    "ExtractionMethod",
    "ExtractedTable",
    "PageExtraction",
    "PageRenderInfo",
    "ProcessedDocumentOutput",
    "RetrievalCandidate",
    "RetrievalResult",
    "ScoredCandidate",
]
