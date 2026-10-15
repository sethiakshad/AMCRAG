"""
AMC-RAG Standard Retrieval Data Contracts
Project: Adaptive Multimodal Corrective RAG (AMC-RAG)
Owner: Om Khapekar (Person 2 - Dense/Sparse Text Retrieval & Fusion)
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """
    Standard data contract consumed from Upstream Teammate (Docling / PyMuPDF chunking).
    Plugs in directly after text chunking is performed.
    """
    chunk_id: str = Field(..., description="Unique deterministic or random chunk UUID")
    document_id: str = Field(..., description="Source document identifier (e.g. filename, hash)")
    page_number: int = Field(..., description="1-indexed source PDF page")
    text: str = Field(..., description="Text content extracted from document layout")
    source_filename: Optional[str] = Field(default=None, description="Original source PDF filename")
    page_start: Optional[int] = Field(default=None, description="Starting page number of chunk span")
    page_end: Optional[int] = Field(default=None, description="Ending page number of chunk span")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Layout metadata (headings, bbox coordinates, table/figure tags)"
    )


class ScoredCandidate(BaseModel):
    """
    Intermediate candidate from an individual retrieval engine (Dense, Sparse, or Visual).
    """
    chunk_id: str
    document_id: str
    page_number: int
    text: str
    score: float
    rank: int
    candidate_type: str = Field(default="text_chunk", description="'text_chunk' or 'visual_page'")
    source_filename: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """
    Universal retrieval candidate emitted by the Hybrid Retrieval engine.
    Fully aligned with Section 10.1 RetrievalCandidate specification.
    Also aliased as `RetrievalCandidate` for seamless cross-module interoperability.
    """
    chunk_id: str
    document_id: str
    page_number: int
    text: str
    modality: str = Field(default="text", description="'text' from this engine, or 'visual_page' from ColPali")
    source_filename: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None
    fused_score: float = Field(..., description="Reciprocal Rank Fusion (RRF) combined score")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def candidate_id(self) -> str:
        return self.chunk_id

    @property
    def candidate_type(self) -> str:
        return "visual_page" if self.modality == "visual_page" else "text_chunk"

    @property
    def retrieval_score(self) -> float:
        return self.fused_score


# Universal alias conforming to Section 10.1 of Central Project Documentation
RetrievalCandidate = RetrievalResult
