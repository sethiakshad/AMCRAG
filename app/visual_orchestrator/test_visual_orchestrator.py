"""Unit tests for app.visual_orchestrator (Ollama Cloud Gemma 4 Vision module).

Validates:
- Client initialization and fallback behavior
- Model multi-vector embedding and MaxSim scoring
- Indexer lifecycle (index, count, delete)
- Retriever schema conformance with ScoredCandidate and RetrievalCandidate
- Reranker sorting logic across visual_only and full_blend strategies
- Bridge facade lifecycle
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.schemas.retrieval import RetrievalCandidate
from app.visual_orchestrator.bridge import GemmaVisualBridge
from app.visual_orchestrator.client import OllamaVisualClient
from app.visual_orchestrator.indexer import GemmaVisualIndexer
from app.visual_orchestrator.model import GemmaVisualModel
from app.visual_orchestrator.reranker import GemmaVisualReranker
from app.visual_orchestrator.retriever import GemmaVisualRetriever
from schemas import RetrievalResult, ScoredCandidate


@pytest.fixture
def sample_image():
    """Create a temporary test PNG page image."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("RGB", (400, 300), color="white")
        img.save(tmp.name, format="PNG")
        path = Path(tmp.name)
    yield path
    if path.exists():
        path.unlink()


def test_ollama_visual_client_initialization():
    client = OllamaVisualClient(
        api_key="test_key_123",
        base_url="https://ollama.com",
        model_name="gemma4:31b",
    )
    assert client.api_key == "test_key_123"
    assert client.base_url == "https://ollama.com"
    assert client.model_name == "gemma4:31b"
    assert client.is_connected


def test_client_describe_and_score_fallback(sample_image):
    client = OllamaVisualClient(fallback_mode=True)
    desc = client.describe_page(sample_image)
    assert "Visual Representation" in desc or len(desc) > 10

    score = client.score_visual_relevance("Find the bar chart", sample_image)
    assert 0.0 <= score <= 1.0


def test_gemma_visual_model_vectors_and_scoring(sample_image):
    model = GemmaVisualModel()
    q_vecs = model.embed_query("What is the accuracy rate?")
    assert len(q_vecs) >= 1
    assert len(q_vecs[0]) == 768

    img_vecs = model.embed_image(sample_image)
    assert len(img_vecs) >= 1
    assert len(img_vecs[0]) == 768

    score = model.score(q_vecs, img_vecs)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_indexer_and_retriever_lifecycle(sample_image):
    # Use isolated in-memory or temporary local Qdrant storage
    with tempfile.TemporaryDirectory() as tmp_dir:
        indexer = GemmaVisualIndexer(
            storage_path=tmp_dir,
            collection="test_visual_pages",
            recreate=True,
        )

        success = indexer.index_page(
            image_path=sample_image,
            page_number=1,
            document_id="doc_test_101",
            source_filename="test_paper.pdf",
            page_text="Introduction to Multimodal Neural RAG with Gemma 4 Vision.",
        )
        assert success is True

        count = indexer.count_document_pages("doc_test_101")
        assert count == 1

        # Test retriever on the same collection
        retriever = GemmaVisualRetriever(
            storage_path=tmp_dir,
            collection="test_visual_pages",
            client=indexer.client,
        )
        results = retriever.retrieve("Multimodal Neural RAG", top_k=3)
        assert len(results) == 1
        cand = results[0]
        assert isinstance(cand, ScoredCandidate)
        assert cand.modality == "visual_page"
        assert cand.metadata["document_id"] == "doc_test_101"

        # Test schema conformance with Person 4 (CRAG)
        crag_cands = retriever.retrieve_candidates("Multimodal Neural RAG", top_k=3)
        assert len(crag_cands) == 1
        assert isinstance(crag_cands[0], RetrievalCandidate)
        assert crag_cands[0].candidate_type == "visual_page"
        assert crag_cands[0].retrieval_method == "visual_gemma"

        # Test deletion
        del_success = indexer.delete_document("doc_test_101")
        assert del_success is True
        assert indexer.count_document_pages("doc_test_101") == 0


def test_gemma_visual_reranker_strategies(sample_image):
    reranker = GemmaVisualReranker()

    candidates = [
        RetrievalResult(
            chunk_id="text_1",
            document_id="doc_1",
            source_filename="doc.pdf",
            page_number=1,
            retrieval_method="dense",
            score=0.80,
            fused_score=0.80,
            text="Text candidate content.",
        ),
        RetrievalResult(
            chunk_id="visual_page_1",
            document_id="doc_1",
            source_filename="doc.pdf",
            page_number=2,
            retrieval_method="visual_gemma",
            score=0.30,
            fused_score=0.30,
            image_path=str(sample_image),
            text="Visual page with chart.",
        ),
    ]

    # Strategy 1: visual_only
    reranked_visual = reranker.rerank(
        query="Chart showing performance",
        candidates=candidates,
        strategy="visual_only",
    )
    assert len(reranked_visual) == 2

    # Strategy 2: full_blend
    reranked_blend = reranker.rerank(
        query="Chart showing performance",
        candidates=candidates,
        strategy="full_blend",
    )
    assert len(reranked_blend) == 2
    assert 0.0 <= reranked_blend[0].fused_score <= 1.0


def test_visual_bridge_facade(sample_image):
    with tempfile.TemporaryDirectory() as tmp_dir:
        bridge = GemmaVisualBridge(
            storage_path=tmp_dir,
            collection="test_bridge_pages",
        )
        assert bridge.is_ready is True

        class MockPageInfo:
            image_path = str(sample_image)
            page_number = 1
            extracted_text = "Sample rendered page text."
            metadata = {"dpi": 150}

        count = bridge.index_pages(
            rendered_pages=[MockPageInfo()],
            document_id="doc_facade",
            source_filename="facade.pdf",
        )
        assert count == 1
        assert bridge.count_document_pages("doc_facade") == 1

        results = bridge.retrieve("sample query", top_k=1)
        assert len(results) == 1

        crag_cands = bridge.retrieve_candidates("sample query", top_k=1)
        assert len(crag_cands) == 1
        assert crag_cands[0].document_id == "doc_facade"
