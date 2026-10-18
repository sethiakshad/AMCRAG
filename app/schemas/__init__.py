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
]

