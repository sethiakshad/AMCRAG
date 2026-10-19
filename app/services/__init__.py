"""Services package exports."""

from app.services.duplicate_detector import DuplicateDetector
from app.services.page_renderer import PageRenderer
from app.services.pipeline import DocumentProcessingPipeline
from app.services.retrieval_bridge import (
    ColPaliVisualBridge,
    index_colpali_pages,
    index_document_chunks,
)

__all__ = [
    "ColPaliVisualBridge",
    "DocumentProcessingPipeline",
    "DuplicateDetector",
    "PageRenderer",
    "index_colpali_pages",
    "index_document_chunks",
]
