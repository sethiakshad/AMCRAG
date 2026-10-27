"""normal_rag — Conventional Normal RAG Baseline Module for AMCRAG.

Provides a standard text-based RAG baseline (Dense Embedding Top-K Retrieval + LLM Generation)
designed for comparative benchmark evaluation against the adaptive multimodal AMCRAG system.
"""

from app.normal_rag.config import NormalRAGConfig
from app.normal_rag.pipeline import NormalRAGPipeline
from app.normal_rag.retriever import NormalRAGRetriever
from app.normal_rag.schemas import (
    NormalRAGChunk,
    NormalRAGRequest,
    NormalRAGResponse,
    NormalRAGResult,
)

__all__ = [
    "NormalRAGConfig",
    "NormalRAGRetriever",
    "NormalRAGPipeline",
    "NormalRAGChunk",
    "NormalRAGResult",
    "NormalRAGRequest",
    "NormalRAGResponse",
]
