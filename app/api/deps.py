"""FastAPI dependencies and service provider injectors for AMCRAG API."""

from __future__ import annotations

import logging
from typing import Any, Optional
from fastapi import Request

from app.config import Settings, default_settings
from app.services.duplicate_detector import DuplicateDetector
from app.services.pipeline import DocumentProcessingPipeline
from app.services.orchestrator import RAGOrchestrator

logger = logging.getLogger(__name__)


def get_settings(request: Request) -> Settings:
    """Retrieve application settings."""
    if hasattr(request.app.state, "settings") and request.app.state.settings is not None:
        return request.app.state.settings
    return default_settings


def get_orchestrator(request: Request) -> RAGOrchestrator:
    """Retrieve or instantiate singleton RAGOrchestrator."""
    if hasattr(request.app.state, "orchestrator") and request.app.state.orchestrator is not None:
        return request.app.state.orchestrator
    # Lazy fallback instance
    generator = getattr(request.app.state, "generator", None)
    orchestrator = RAGOrchestrator(generator=generator)
    request.app.state.orchestrator = orchestrator
    return orchestrator


def get_pipeline(request: Request) -> DocumentProcessingPipeline:
    """Retrieve or instantiate DocumentProcessingPipeline."""
    if hasattr(request.app.state, "pipeline") and request.app.state.pipeline is not None:
        return request.app.state.pipeline
    settings = get_settings(request)
    pipeline = DocumentProcessingPipeline(settings=settings)
    request.app.state.pipeline = pipeline
    return pipeline


def get_duplicate_detector(request: Request) -> DuplicateDetector:
    """Retrieve or instantiate DuplicateDetector."""
    if hasattr(request.app.state, "duplicate_detector") and request.app.state.duplicate_detector is not None:
        return request.app.state.duplicate_detector
    settings = get_settings(request)
    detector = DuplicateDetector(settings=settings)
    request.app.state.duplicate_detector = detector
    return detector


def get_retriever(request: Request) -> Optional[Any]:
    """Retrieve Person 2 HybridTextRetriever if available."""
    if hasattr(request.app.state, "retriever") and request.app.state.retriever is not None:
        return request.app.state.retriever
    if hasattr(request.app.state, "orchestrator") and request.app.state.orchestrator is not None:
        return request.app.state.orchestrator.retriever
    return None


def get_visual_bridge(request: Request) -> Optional[Any]:
    """Retrieve Person 3 ColPaliVisualBridge if available."""
    if hasattr(request.app.state, "visual_bridge") and request.app.state.visual_bridge is not None:
        return request.app.state.visual_bridge
    if hasattr(request.app.state, "orchestrator") and request.app.state.orchestrator is not None:
        return request.app.state.orchestrator.visual_bridge
    return None


def get_normal_rag_pipeline(request: Request) -> Any:
    """Retrieve or instantiate singleton NormalRAGPipeline reusing shared engines."""
    if hasattr(request.app.state, "normal_rag_pipeline") and request.app.state.normal_rag_pipeline is not None:
        return request.app.state.normal_rag_pipeline
    from app.normal_rag.pipeline import NormalRAGPipeline
    from app.normal_rag.retriever import NormalRAGRetriever

    dense_engine = None
    if hasattr(request.app.state, "retriever") and request.app.state.retriever is not None:
        dense_engine = getattr(request.app.state.retriever, "dense_engine", None)

    retriever = NormalRAGRetriever(dense_engine=dense_engine)
    generator = getattr(request.app.state, "generator", None)
    pipeline = NormalRAGPipeline(retriever=retriever, generator=generator)
    request.app.state.normal_rag_pipeline = pipeline
    return pipeline


def get_comparison_pipeline(request: Request) -> Any:
    """Retrieve or instantiate ComparisonPipeline connecting orchestrator and Normal RAG."""
    if hasattr(request.app.state, "comparison_pipeline") and request.app.state.comparison_pipeline is not None:
        return request.app.state.comparison_pipeline
    from app.comparison.pipeline import ComparisonPipeline

    orchestrator = get_orchestrator(request)
    normal_rag = get_normal_rag_pipeline(request)
    pipeline = ComparisonPipeline(orchestrator=orchestrator, normal_rag=normal_rag)
    request.app.state.comparison_pipeline = pipeline
    return pipeline

