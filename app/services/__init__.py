"""Services package exports."""

from app.services.duplicate_detector import DuplicateDetector
from app.services.generator import AnswerGenerator, GeneratorConfig
from app.services.orchestrator import OrchestratorConfig, RAGOrchestrator
from app.services.page_renderer import PageRenderer
from app.services.pipeline import DocumentProcessingPipeline
from app.services.retrieval_bridge import (
    ColPaliVisualBridge,
    GemmaVisualBridge,
    index_colpali_pages,
    index_document_chunks,
    index_visual_pages,
)

__all__ = [
    "AnswerGenerator",
    "ColPaliVisualBridge",
    "DocumentProcessingPipeline",
    "DuplicateDetector",
    "GemmaVisualBridge",
    "GeneratorConfig",
    "OrchestratorConfig",
    "PageRenderer",
    "RAGOrchestrator",
    "index_colpali_pages",
    "index_document_chunks",
    "index_visual_pages",
]

