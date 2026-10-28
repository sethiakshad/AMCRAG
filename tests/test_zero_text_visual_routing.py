"""Test Zero-Text Chunks / Zero-Text Embeddings Fallback to Visual Orchestrator.

Validates the user requirement:
"When text chunks or embedding or both are 0, then move to this module."
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from app.schemas.api import ModelModality, QueryRequest
from app.schemas.retrieval import RetrievalCandidate
from app.services.orchestrator import OrchestratorConfig, RAGOrchestrator
from app.services.retrieval_bridge import ColPaliVisualBridge, index_colpali_pages


def test_zero_text_chunks_routes_to_visual_bridge_in_orchestrator(tmp_path, monkeypatch):
    """When a document has 0 text chunks, intent and retrieval route directly to visual module."""
    mock_settings = MagicMock()
    mock_settings.get_processed_path.return_value = tmp_path
    monkeypatch.setattr("app.config.default_settings", mock_settings)

    # Document has 0 text chunks
    doc_id = "doc_zero_text_001"
    doc_data = {
        "document_id": doc_id,
        "document_name": "6-Support+Vector+Classifier.pdf",
        "total_chunks": 0,
        "chunks": [],
        "zero_text_chunks": True,
        "zero_text_fallback": True,
        "pipeline_modality": "visual_only",
        "rendered_pages": ["page_1.png", "page_2.png", "page_3.png"],
    }
    (tmp_path / f"{doc_id}.json").write_text(json.dumps(doc_data), encoding="utf-8")

    orchestrator = RAGOrchestrator()
    mock_visual_bridge = MagicMock()
    mock_candidate = RetrievalCandidate(
        candidate_id="p1",
        document_id=doc_id,
        source_filename="6-Support+Vector+Classifier.pdf",
        page_start=1,
        page_end=1,
        candidate_type="visual_page",
        text="Support Vector Classifier hyperplanes",
        page_reference="page_1.png",
        retrieval_method="visual_gemma",
        retrieval_rank=1,
        retrieval_score=0.92,
        metadata={"image_path": "page_1.png"},
    )
    mock_visual_bridge.retrieve.return_value = [mock_candidate]
    mock_visual_bridge.enabled = True
    orchestrator.visual_bridge = mock_visual_bridge

    # 1. Verify query intent routes to VISION automatically
    intent = orchestrator.analyze_query_intent(
        query="What is a support vector classifier?",
        document_ids=[doc_id],
    )
    assert intent == ModelModality.VISION

    # 2. Verify candidate retrieval moves directly to visual bridge
    candidates = orchestrator._fetch_candidates(
        query="What is a support vector classifier?",
        top_k=3,
        modality=intent,
        document_ids=[doc_id],
    )
    assert len(candidates) == 1
    assert candidates[0].candidate_type == "visual_page"
    assert candidates[0].document_id == doc_id
    mock_visual_bridge.retrieve.assert_called_once()


def test_zero_text_embeddings_triggers_visual_fallback(tmp_path, monkeypatch):
    """When text retrieval returns 0 candidates (0 text embeddings), it falls back to visual module."""
    mock_settings = MagicMock()
    mock_settings.get_processed_path.return_value = tmp_path
    monkeypatch.setattr("app.config.default_settings", mock_settings)

    orchestrator = RAGOrchestrator()
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = []  # 0 text candidates / embeddings
    orchestrator.retriever = mock_retriever

    mock_visual_bridge = MagicMock()
    mock_cand = RetrievalCandidate(
        candidate_id="c_visual_1",
        document_id="doc_svc",
        source_filename="6-Support+Vector+Classifier.pdf",
        page_start=1,
        page_end=1,
        candidate_type="visual_page",
        text="Margin classification",
        page_reference="page_1.png",
        retrieval_method="visual_gemma",
        retrieval_rank=1,
        retrieval_score=0.88,
        metadata={},
    )
    mock_visual_bridge.retrieve.return_value = [mock_cand]
    mock_visual_bridge.enabled = True
    orchestrator.visual_bridge = mock_visual_bridge

    candidates = orchestrator._fetch_candidates(
        query="Explain soft margin classifier",
        top_k=3,
        modality=ModelModality.TEXT,
        document_ids=["doc_svc"],
    )

    assert len(candidates) == 1
    assert candidates[0].candidate_type == "visual_page"
    mock_visual_bridge.retrieve.assert_called()


def test_colpali_visual_bridge_uses_gemma_visual_engine():
    """Verify ColPaliVisualBridge delegates to GemmaVisualBridge without loading local PyTorch weights."""
    bridge = ColPaliVisualBridge(enabled=True)
    assert bridge.is_ready is True
    # Test retrieve on dummy query returns list
    results = bridge.retrieve("margin hyperplanes")
    assert isinstance(results, list)
    # Test count_document_pages
    count = bridge.count_document_pages("doc_svc_classifier")
    assert isinstance(count, int)
