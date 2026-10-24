"""Retrieval candidate contract for AMCRAG.

Follows Section 10.1 of AMCRAG Central Project Documentation.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field

CandidateType = Literal["text_chunk", "visual_page"]


class RetrievalCandidate(BaseModel):
    """Unified retrieval candidate representation across dense, sparse, and visual search."""

    candidate_id: str = Field(..., description="Unique identifier for the chunk or visual page")
    document_id: str = Field(..., description="Parent document identifier")
    source_filename: str = Field(..., description="Original filename of the document")
    page_start: int | None = Field(default=None, description="Starting page number (1-indexed)")
    page_end: int | None = Field(default=None, description="Ending page number (1-indexed)")
    candidate_type: CandidateType = Field(..., description="'text_chunk' or 'visual_page'")
    text: str | None = Field(default=None, description="Extracted textual content if available")
    page_reference: str | None = Field(
        default=None, description="Managed visual page URI or artifact reference"
    )
    retrieval_method: str = Field(
        ..., description="Method that retrieved this candidate (dense, bm25, colpali, rrf)"
    )
    retrieval_rank: int = Field(default=1, description="Rank position in the candidate list")
    retrieval_score: float | None = Field(
        default=None, description="Reranker or retriever relevance score"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Supplementary metadata (e.g. section titles, layout tags)"
    )

    def get_evaluable_content(self) -> str:
        """Returns the primary string content available for text-based evaluation.

        If extracted text exists, returns it. If it is a visual page without text,
        falls back to descriptive metadata (e.g. caption, layout tags) or a placeholder.
        """
        if self.text and self.text.strip():
            return self.text.strip()
        
        # Fallback for visual pages
        meta_summary = self.metadata.get("description") or self.metadata.get("caption") or self.metadata.get("title")
        if meta_summary:
            return f"[Visual Page on page {self.page_start}: {meta_summary}]"
        
        return f"[Visual Page from {self.source_filename}, page {self.page_start}]"
