"""api.py — Pydantic API Request and Response Schemas for AMCRAG.

Defines the external HTTP contracts for user query execution, streaming,
document ingestion, knowledge base management, and system health checks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.context_builder.schemas import ModelModality, SourceMetadata


class QueryRequest(BaseModel):
    """Incoming user query payload for the /api/v1/query endpoint."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="User's natural language question",
        examples=["What is the lock-in period and tax benefit for ELSS mutual funds?"],
    )
    model_modality: Optional[ModelModality] = Field(
        default=None,
        description="Target generator model capability ('text' or 'vision')",
    )

    token_budget: Optional[int] = Field(
        default=4096,
        ge=500,
        le=128000,
        description="Maximum token budget for prompt context",
    )
    top_k: Optional[int] = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of evidence chunks/pages to retrieve",
    )
    enable_crag: bool = Field(
        default=True,
        description="Whether to execute CRAG quality evaluation and corrective retry loop",
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of document IDs to restrict retrieval scope",
    )

    @field_validator("query")
    @classmethod
    def validate_non_empty_query(cls, v: str) -> str:
        """Ensure query is not empty or purely whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query cannot be empty or contain only whitespace.")
        return stripped

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "query": "What are the risk factors disclosed in the annual report?",
                "model_modality": "text",
                "token_budget": 4096,
                "top_k": 5,
                "enable_crag": True,
            }
        },
    }


class LatencyBreakdown(BaseModel):
    """Execution latency breakdown in milliseconds across pipeline stages."""

    query_analysis_ms: float = Field(default=0.0, description="Query intent classification latency")
    retrieval_ms: float = Field(default=0.0, description="Parallel hybrid retrieval and fusion latency")
    crag_evaluation_ms: float = Field(default=0.0, description="CRAG evaluation and retry loop latency")
    context_building_ms: float = Field(default=0.0, description="Context builder grounding synthesis latency")
    generation_ms: float = Field(default=0.0, description="Answer LLM generation latency")
    total_ms: float = Field(default=0.0, description="Total end-to-end request latency")

    model_config = {"extra": "allow"}


class QueryResponse(BaseModel):
    """Canonical response payload returned by /api/v1/query."""

    query: str = Field(..., description="Original user query")
    answer: str = Field(..., description="Generated answer with [E#] citation tags")
    sources: List[SourceMetadata] = Field(
        default_factory=list,
        description="Structured citation metadata mapped 1-to-1 with prompt [E#] tags",
    )
    visual_inputs: List[str] = Field(
        default_factory=list,
        description="Resolvable file paths to relevant page images for vision models",
    )
    crag_decision: Optional[str] = Field(
        default=None,
        description="CRAG evaluation decision label ('CORRECT', 'AMBIGUOUS', 'INCORRECT')",
    )
    insufficient_evidence: bool = Field(
        default=False,
        description="True if retrieval could not find sufficient evidence and answer generation halted",
    )
    retrieval_attempts: int = Field(
        default=1,
        description="Total retrieval attempts executed (initial query + reformulations)",
    )
    latency: LatencyBreakdown = Field(
        default_factory=LatencyBreakdown,
        description="Granular timing metrics for pipeline stages",
    )

    model_config = {"extra": "allow"}


class DocumentUploadResponse(BaseModel):
    """Response returned upon PDF upload and ingestion via /api/v1/documents."""

    document_id: str = Field(..., description="Unique deterministic identifier of uploaded document")
    filename: str = Field(..., description="Original PDF filename")
    status: Literal["indexed", "cached", "failed"] = Field(
        ..., description="Processing and indexing status"
    )
    page_count: int = Field(default=0, description="Total pages extracted and rendered")
    chunk_count: int = Field(default=0, description="Total text chunks generated and indexed")
    image_count: int = Field(default=0, description="Total 150 DPI page PNGs rendered for ColPali")
    message: str = Field(default="", description="Descriptive status or error message")

    model_config = {"extra": "allow"}


class DocumentSummary(BaseModel):
    """Summary record for a single indexed document in the catalog."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Source document filename")
    page_count: int = Field(default=0, description="Number of pages")
    chunk_count: int = Field(default=0, description="Number of text chunks")
    upload_timestamp: Optional[str] = Field(default=None, description="ISO timestamp of upload")
    file_size_bytes: Optional[int] = Field(default=None, description="PDF file size in bytes")

    model_config = {"extra": "allow"}


class DocumentDetailResponse(BaseModel):
    """Detailed record for a single document including manifest and page image paths."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Source document filename")
    page_count: int = Field(default=0, description="Number of pages")
    chunk_count: int = Field(default=0, description="Number of text chunks")
    image_count: int = Field(default=0, description="Number of rendered page images")
    status: str = Field(default="indexed", description="Indexing status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    page_images: List[str] = Field(default_factory=list, description="List of rendered page image paths")

    model_config = {"extra": "allow"}


class DeleteResponse(BaseModel):
    """Response returned upon document deletion."""

    document_id: str = Field(..., description="Identifier of deleted document")
    deleted: bool = Field(default=True, description="Whether document was successfully deleted")
    message: str = Field(default="Document deleted successfully", description="Status message")

    model_config = {"extra": "allow"}


class HealthResponse(BaseModel):
    """System readiness and health status response for /api/v1/health."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall health state"
    )
    version: str = Field(default="1.0.0", description="AMCRAG backend service version")
    components: Dict[str, bool] = Field(
        default_factory=dict,
        description="Health states of underlying subsystems (vector_db, bm25, crag, llm)",
    )
    uptime_seconds: Optional[float] = Field(default=None, description="Service uptime in seconds")

    model_config = {"extra": "allow"}
