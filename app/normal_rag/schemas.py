"""schemas.py — Data contracts and structured output models for Normal RAG."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class NormalRAGChunk(BaseModel):
    """Structured representation of a single text chunk retrieved for Normal RAG."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(default="", description="Parent document identifier")
    source_filename: Optional[str] = Field(default=None, description="Original source document filename")
    page_number: int = Field(default=1, description="Primary 1-indexed page number")
    page_start: Optional[int] = Field(default=None, description="Starting page span (1-indexed)")
    page_end: Optional[int] = Field(default=None, description="Ending page span (1-indexed)")
    text: str = Field(..., description="Text content of the retrieved passage")
    score: float = Field(default=0.0, description="Cosine similarity score from dense vector search")
    rank: int = Field(default=1, description="Rank position among retrieved candidates (1-indexed)")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved extraction metadata (section, headings, char_count, etc.)",
    )

    model_config = {"extra": "allow"}


class NormalRAGResult(BaseModel):
    """Canonical structured result returned by Normal RAG.

    Conforms strictly to the required comparison interface for future evaluation
    against AMCRAG.
    """

    system: str = Field(
        default="normal_rag",
        description="Identifies the generating RAG baseline system",
    )
    question: str = Field(..., description="The user's query / question")
    answer: str = Field(..., description="Generated answer grounded in retrieved context")
    retrieved_chunks: List[NormalRAGChunk] = Field(
        default_factory=list,
        description="List of top-k text chunks retrieved from vector store",
    )
    source_pages: List[int] = Field(
        default_factory=list,
        description="Sorted unique 1-indexed page numbers contributing to retrieved context",
    )
    retrieval_latency_ms: float = Field(
        default=0.0,
        description="Elapsed time in milliseconds for vector embedding and similarity search",
    )
    generation_latency_ms: float = Field(
        default=0.0,
        description="Elapsed time in milliseconds for LLM answer synthesis",
    )
    total_latency_ms: float = Field(
        default=0.0,
        description="Total end-to-end execution latency in milliseconds",
    )
    token_usage: Optional[Dict[str, int]] = Field(
        default=None,
        description="Estimated or reported token usage (e.g. prompt_tokens, completion_tokens)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if any step encountered failure or warning",
    )

    model_config = {"extra": "allow"}


class NormalRAGRequest(BaseModel):
    """Incoming request payload for querying Normal RAG."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Natural language question to answer",
        examples=["What is the primary contribution of the paper?"],
    )
    top_k: Optional[int] = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of evidence chunks to retrieve",
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of document IDs to restrict retrieval scope",
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Optional single document ID shorthand",
    )

    @field_validator("query")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Query cannot be empty or purely whitespace.")
        return s

    model_config = {"extra": "allow"}


# NormalRAGResponse is an alias of NormalRAGResult for API serialization
NormalRAGResponse = NormalRAGResult
