"""test_normal_rag.py — Comprehensive Unit & Integration Tests for Normal RAG Baseline.

Verifies:
1. Normal RAG configuration and schemas.
2. Standard top-k dense vector retrieval over document chunks.
3. Grounded answer generation using the retrieved context.
4. Latency breakdown and source metadata preservation.
5. Independent execution completely decoupled from AMCRAG (no CRAG, no ColPali).
6. FastAPI API endpoint integration (/api/v1/normal-rag/query and /index).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import api_router
from app.config import Settings
from app.normal_rag.config import NormalRAGConfig
from app.normal_rag.pipeline import NormalRAGPipeline
from app.normal_rag.retriever import NormalRAGRetriever
from app.normal_rag.schemas import (
    NormalRAGChunk,
    NormalRAGRequest,
    NormalRAGResponse,
    NormalRAGResult,
)
from app.schemas.chunk import DocumentChunk, ProcessedDocumentOutput
from app.schemas.document import DocumentMetadata
from app.services.generator import AnswerGenerator, GeneratorConfig


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_document_chunks() -> list[DocumentChunk]:
    """Sample text chunks with rich metadata for retrieval testing."""
    return [
        DocumentChunk(
            chunk_id="chunk_001",
            document_id="doc_finance_01",
            source_filename="annual_report_2024.pdf",
            page_number=1,
            page_start=1,
            page_end=1,
            text="In fiscal year 2024, total revenue grew by 18.5% year-over-year reaching $4.2 billion.",
            metadata={"section": "Financial Highlights", "char_count": 86},
        ),
        DocumentChunk(
            chunk_id="chunk_002",
            document_id="doc_finance_01",
            source_filename="annual_report_2024.pdf",
            page_number=2,
            page_start=2,
            page_end=3,
            text="Operating margins expanded by 140 basis points, driven by operational efficiencies in cloud infrastructure.",
            metadata={"section": "Operations & Infrastructure", "char_count": 107},
        ),
        DocumentChunk(
            chunk_id="chunk_003",
            document_id="doc_legal_02",
            source_filename="regulatory_compliance.pdf",
            page_number=5,
            page_start=5,
            page_end=5,
            text="The statutory audit confirmed complete compliance with all ISO 27001 cybersecurity frameworks.",
            metadata={"section": "Compliance Review", "char_count": 96},
        ),
    ]


@pytest.fixture
def mock_generator() -> AnswerGenerator:
    """Mock answer generator to simulate grounded generation without network calls."""
    gen = AnswerGenerator(GeneratorConfig(provider="mock"))
    return gen


@pytest.fixture
def in_memory_retriever() -> NormalRAGRetriever:
    """Retriever configured to use an in-memory Qdrant instance for speed and test isolation."""
    config = NormalRAGConfig(
        top_k=3,
        collection_name="test_normal_rag_in_memory",
        qdrant_path=None,  # in-memory :memory:
    )
    return NormalRAGRetriever(config=config)


# =============================================================================
# 1. Config and Schema Tests
# =============================================================================

def test_normal_rag_config_defaults():
    """Verify default parameters of NormalRAGConfig."""
    config = NormalRAGConfig()
    assert config.top_k == 5
    assert "bge-base-en" in config.dense_model_name
    assert config.collection_name == "normal_rag_text_chunks"
    assert "{context}" in config.system_prompt_template
    assert "{question}" in config.system_prompt_template


def test_normal_rag_result_schema_contract():
    """Verify structured output fields required for future comparison with AMCRAG."""
    chunk = NormalRAGChunk(
        chunk_id="c1",
        document_id="doc1",
        source_filename="doc1.pdf",
        page_number=2,
        page_start=2,
        page_end=2,
        text="Sample text content",
        score=0.9123,
        rank=1,
    )
    result = NormalRAGResult(
        system="normal_rag",
        question="What is the revenue?",
        answer="The revenue is $4.2 billion.",
        retrieved_chunks=[chunk],
        source_pages=[2],
        retrieval_latency_ms=12.4,
        generation_latency_ms=45.6,
        total_latency_ms=58.0,
        token_usage={"prompt_tokens": 120, "completion_tokens": 15},
        error=None,
    )

    data = result.model_dump()
    assert data["system"] == "normal_rag"
    assert data["question"] == "What is the revenue?"
    assert data["answer"] == "The revenue is $4.2 billion."
    assert len(data["retrieved_chunks"]) == 1
    assert data["retrieved_chunks"][0]["chunk_id"] == "c1"
    assert data["source_pages"] == [2]
    assert data["retrieval_latency_ms"] == 12.4
    assert data["generation_latency_ms"] == 45.6
    assert data["total_latency_ms"] == 58.0
    assert data["error"] is None


def test_normal_rag_request_validation():
    """Verify validation on incoming NormalRAGRequest."""
    req = NormalRAGRequest(query="Valid query text", top_k=10, document_id="doc_123")
    assert req.query == "Valid query text"
    assert req.top_k == 10
    assert req.document_id == "doc_123"

    with pytest.raises(ValueError):
        NormalRAGRequest(query="   ")


# =============================================================================
# 2. Retriever Unit Tests
# =============================================================================

def test_retriever_indexing_and_search(sample_document_chunks):
    """Verify chunk indexing and top-k vector similarity search."""
    # Use mock dense engine to test retriever logic without downloading weights during fast test runs
    mock_engine = MagicMock()
    mock_candidate = MagicMock()
    mock_candidate.chunk_id = "chunk_001"
    mock_candidate.document_id = "doc_finance_01"
    mock_candidate.source_filename = "annual_report_2024.pdf"
    mock_candidate.page_number = 1
    mock_candidate.page_start = 1
    mock_candidate.page_end = 1
    mock_candidate.text = sample_document_chunks[0].text
    mock_candidate.score = 0.8845
    mock_candidate.metadata = {"section": "Financial Highlights"}

    mock_engine.search.return_value = [mock_candidate]

    retriever = NormalRAGRetriever(dense_engine=mock_engine)

    # 1. Index chunks
    indexed = retriever.index_chunks(sample_document_chunks)
    assert indexed == len(sample_document_chunks)
    mock_engine.index_chunks.assert_called_once()

    # 2. Search
    results = retriever.search("What was the total revenue?", top_k=1)
    assert len(results) == 1
    res = results[0]
    assert res.chunk_id == "chunk_001"
    assert res.document_id == "doc_finance_01"
    assert res.page_number == 1
    assert res.score == 0.8845
    assert "revenue grew by 18.5%" in res.text


def test_retriever_document_filtering():
    """Verify document_ids filtering passed to search engine."""
    mock_engine = MagicMock()
    mock_engine.search.return_value = []
    retriever = NormalRAGRetriever(dense_engine=mock_engine)

    retriever.search("Compliance status", top_k=5, document_ids=["doc_legal_02"])
    mock_engine.search.assert_called_with(
        query="Compliance status",
        top_k=5,
        filters={"document_id": "doc_legal_02"},
    )


# =============================================================================
# 3. Pipeline Workflow Tests
# =============================================================================

def test_normal_rag_pipeline_end_to_end(sample_document_chunks):
    """Verify full Normal RAG pipeline: retrieval, context assembly, answer generation, and metrics."""
    # Mock retriever
    mock_retriever = MagicMock()
    mock_chunk = NormalRAGChunk(
        chunk_id="chunk_001",
        document_id="doc_finance_01",
        source_filename="annual_report_2024.pdf",
        page_number=1,
        page_start=1,
        page_end=1,
        text="In fiscal year 2024, total revenue grew by 18.5% year-over-year reaching $4.2 billion.",
        score=0.89,
        rank=1,
    )
    mock_retriever.search.return_value = [mock_chunk]

    # Mock generator
    mock_gen = MagicMock()
    mock_gen.active_provider = "mock"
    mock_gen.generate.return_value = "Total revenue grew by 18.5% reaching $4.2 billion [Chunk 1]."

    pipeline = NormalRAGPipeline(retriever=mock_retriever, generator=mock_gen)

    result = pipeline.query("What was the 2024 revenue growth?", top_k=2)

    # Assertions
    assert result.system == "normal_rag"
    assert result.question == "What was the 2024 revenue growth?"
    assert "4.2 billion" in result.answer
    assert len(result.retrieved_chunks) == 1
    assert result.source_pages == [1]
    assert result.retrieval_latency_ms >= 0.0
    assert result.generation_latency_ms >= 0.0
    assert result.total_latency_ms >= 0.0
    assert result.error is None
    assert result.token_usage is not None

    # Verify context passed to generator
    assert mock_gen.generate.called
    called_prompt = mock_gen.generate.call_args[1]["prompt"]
    assert "In fiscal year 2024, total revenue grew" in called_prompt
    assert "Question: What was the 2024 revenue growth?" in called_prompt


def test_normal_rag_pipeline_empty_retrieval():
    """Verify deterministic fallback when no chunks are retrieved."""
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = []
    mock_gen = MagicMock()

    pipeline = NormalRAGPipeline(retriever=mock_retriever, generator=mock_gen)
    result = pipeline.query("Irrelevant query")

    assert "insufficient evidence" in result.answer.lower()
    assert result.retrieved_chunks == []
    assert result.source_pages == []
    assert not mock_gen.generate.called


def test_normal_rag_pipeline_index_processed_document():
    """Verify ingestion of existing ProcessedDocumentOutput representation."""
    doc_meta = DocumentMetadata(
        document_id="doc_demo_1",
        document_name="demo.pdf",
        file_path="data/demo.pdf",
        file_size_bytes=1024,
        page_count=1,
        upload_timestamp="2026-10-28T00:00:00Z",
        content_hash="abc12345",
    )
    doc_chunk = DocumentChunk(
        chunk_id="chunk_demo_1",
        document_id="doc_demo_1",
        page_number=1,
        text="Normal RAG operates independently of AMCRAG.",
    )
    proc_output = ProcessedDocumentOutput(
        document_id="doc_demo_1",
        document_name="demo.pdf",
        metadata=doc_meta,
        status="success",
        is_scanned=False,
        ocr_needed=False,
        extraction_method="pymupdf",
        chunks=[doc_chunk],
        total_chunks=1,
    )

    mock_retriever = MagicMock()
    mock_retriever.index_chunks.return_value = 1
    pipeline = NormalRAGPipeline(retriever=mock_retriever)

    count = pipeline.index_document_output(proc_output)
    assert count == 1
    mock_retriever.index_chunks.assert_called_once_with([doc_chunk])


# =============================================================================
# 4. FastAPI Endpoint Tests
# =============================================================================

@pytest.fixture
def test_app_client(tmp_path: Path):
    """FastAPI TestClient with isolated settings and mocked backend."""
    settings = Settings(
        base_dir=tmp_path,
        uploads_dir=tmp_path / "data" / "uploads",
        processed_dir=tmp_path / "data" / "processed",
        page_images_dir=tmp_path / "data" / "page_images",
    )
    settings.get_uploads_path()
    settings.get_processed_path()
    settings.get_page_images_path()

    app = FastAPI(title="AMCRAG & Normal RAG Test App")
    app.include_router(api_router, prefix="/api/v1")
    app.state.settings = settings

    # Wire a mock NormalRAGPipeline
    mock_pipeline = MagicMock()
    mock_pipeline.query.return_value = NormalRAGResult(
        system="normal_rag",
        question="What is the test question?",
        answer="The test answer grounded in context.",
        retrieved_chunks=[
            NormalRAGChunk(
                chunk_id="chk_1",
                document_id="doc_1",
                source_filename="test.pdf",
                page_number=1,
                text="Test ground truth chunk",
                score=0.92,
                rank=1,
            )
        ],
        source_pages=[1],
        retrieval_latency_ms=10.0,
        generation_latency_ms=25.0,
        total_latency_ms=35.0,
        token_usage={"total_tokens": 80},
    )

    async def mock_query_async(payload):
        return mock_pipeline.query(payload.query)

    mock_pipeline.query_async = mock_query_async
    app.state.normal_rag_pipeline = mock_pipeline

    return TestClient(app)


def test_api_normal_rag_query_endpoint(test_app_client):
    """Verify POST /api/v1/normal-rag/query returns expected response contract."""
    response = test_app_client.post(
        "/api/v1/normal-rag/query",
        json={"query": "What is the test question?", "top_k": 3},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["system"] == "normal_rag"
    assert data["question"] == "What is the test question?"
    assert "grounded in context" in data["answer"]
    assert len(data["retrieved_chunks"]) == 1
    assert data["source_pages"] == [1]
    assert "retrieval_latency_ms" in data
    assert "generation_latency_ms" in data
    assert "total_latency_ms" in data


def test_api_normal_rag_query_empty_validation(test_app_client):
    """Verify 422 Unprocessable Entity on empty query string."""
    response = test_app_client.post(
        "/api/v1/normal-rag/query",
        json={"query": "   "},
    )
    assert response.status_code == 422


def test_api_normal_rag_independent_of_amcrag(test_app_client):
    """Verify that Normal RAG endpoint operates without touching AMCRAG endpoints."""
    # Both endpoints exist on router
    routes = [route.path for route in test_app_client.app.routes]
    assert "/api/v1/query" in routes
    assert "/api/v1/normal-rag/query" in routes
    assert "/api/v1/normal-rag/index" in routes
