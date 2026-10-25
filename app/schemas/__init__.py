"""Schema exports for document processing and knowledge base preparation."""

from app.schemas.document import (
    DocumentExtractionResult,
    DocumentMetadata,
    ExtractionMethod,
    ExtractedTable,
    PageExtraction,
    PageRenderInfo,
)
from app.schemas.chunk import (
    ChunkMetadata,
    DocumentChunk,
    ProcessedDocumentOutput,
)


from app.schemas.crag import (
    AmbiguousPolicy,
    CandidateEvaluation,
    CRAGResult,
    EvidenceDecision,
    EvidenceLabel,
)


from app.schemas.api import (
    DeleteResponse,
    DocumentDetailResponse,
    DocumentSummary,
    DocumentUploadResponse,
    HealthResponse,
    LatencyBreakdown,
    QueryRequest,
    QueryResponse,
)


class ScoredCandidate:
    """Import lazily or from root schemas."""
    pass


# Re-export from root schemas for universal availability
try:
    from schemas import RetrievalCandidate, RetrievalResult, ScoredCandidate  # type: ignore
except ImportError:
    pass

__all__ = [
    "DocumentExtractionResult",
    "DocumentMetadata",
    "ExtractionMethod",
    "ExtractedTable",
    "PageExtraction",
    "PageRenderInfo",
    "ChunkMetadata",
    "DocumentChunk",
    "ProcessedDocumentOutput",
    "ScoredCandidate",
    "RetrievalResult",
    "RetrievalCandidate",
    # Person 4: CRAG Schemas
    "AmbiguousPolicy",
    "CandidateEvaluation",
    "CRAGResult",
    "EvidenceDecision",
    "EvidenceLabel",
    # Person 5: API Schemas
    "QueryRequest",
    "QueryResponse",
    "LatencyBreakdown",
    "DocumentUploadResponse",
    "DocumentSummary",
    "DocumentDetailResponse",
    "DeleteResponse",
    "HealthResponse",
]

