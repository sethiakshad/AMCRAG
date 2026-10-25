"""test_api_v1_endpoints.py — End-to-end integration and robustness tests for FastAPI v1 API."""

import io
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import api_router
from app.config import Settings
from app.schemas.api import QueryRequest, QueryResponse, HealthResponse
from app.schemas.crag import EvidenceDecision, CRAGResult
from app.schemas.retrieval import RetrievalCandidate
from app.services.generator import AnswerGenerator, GeneratorConfig
from app.services.orchestrator import OrchestratorConfig, RAGOrchestrator
from app.services.pipeline import DocumentProcessingPipeline
from app.services.duplicate_detector import DuplicateDetector


@pytest.fixture
def mock_app_client(tmp_path: Path):
    """Create a test FastAPI app with isolated settings and mocked backend services."""
    settings = Settings(
        base_dir=tmp_path,
        uploads_dir=tmp_path / "data" / "uploads",
        processed_dir=tmp_path / "data" / "processed",
        page_images_dir=tmp_path / "data" / "page_images",
    )
    # Ensure dirs exist
    settings.get_uploads_path()
    settings.get_processed_path()
    settings.get_page_images_path()

    app = FastAPI(title="AMCRAG Test App")
    app.include_router(api_router, prefix="/api/v1")

    # Mock Person 2 retriever
    mock_retriever = MagicMock()
    mock_candidate = RetrievalCandidate(
        candidate_id="chunk_test_1",
        document_id="doc_test_1",
        source_filename="test_manual.pdf",
        page_start=1,
        page_end=1,
        candidate_type="text_chunk",
        text="The statutory lock-in period for ELSS mutual funds is strictly 3 years under Section 80C.",
        page_reference="Page 1",
        retrieval_method="hybrid",
        retrieval_rank=1,
        retrieval_score=0.95,
    )
    mock_retriever.retrieve.return_value = [mock_candidate]
    mock_retriever.index_knowledge_base.return_value = 1

    # Mock Person 4 CRAG controller
    mock_crag = MagicMock()
    mock_crag.process_candidates.return_value = CRAGResult(
        decision=EvidenceDecision(
            label="CORRECT",
            score=0.92,
            explanation="Candidate provides exact factual answer.",
            needs_correction=False,
        ),
        reformulated_query=None,
        accepted_candidates=[mock_candidate],
        can_proceed_to_generation=True,
        insufficient_evidence=False,
    )


    # Person 5 Generator (Mock provider)
    generator = AnswerGenerator(GeneratorConfig(provider="mock"))

    # Orchestrator
    orchestrator = RAGOrchestrator(
        config=OrchestratorConfig(enable_crag=True),
        retriever=mock_retriever,
        visual_bridge=None,
        crag_controller=mock_crag,
        generator=generator,
    )

    # Mock Person 1 Pipeline
    mock_pipeline = MagicMock(spec=DocumentProcessingPipeline)
    mock_output = MagicMock()
    mock_output.document_id = "doc_test_1"
    mock_output.status = "success"
    mock_output.error_message = None
    mock_output.metadata.page_count = 2
    mock_output.total_chunks = 4
    mock_output.chunks = [mock_candidate]
    mock_output.rendered_pages = []
    mock_pipeline.process_file.return_value = mock_output

    duplicate_detector = DuplicateDetector(settings=settings)

    # Attach to app.state
    app.state.settings = settings
    app.state.orchestrator = orchestrator
    app.state.pipeline = mock_pipeline
    app.state.duplicate_detector = duplicate_detector
    app.state.retriever = mock_retriever
    app.state.visual_bridge = None
    app.state.start_time = 1000000.0

    client = TestClient(app)
    return client, settings, orchestrator, mock_pipeline


# =============================================================================
# 1. Health Probe Endpoint Tests
# =============================================================================

def test_health_probe(mock_app_client):
    """Test GET /api/v1/health returns healthy subsystem matrix."""
    client, settings, _, _ = mock_app_client
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "components" in data
    assert "vector_db" in data["components"]
    assert "bm25" in data["components"]
    assert "crag" in data["components"]
    assert "llm" in data["components"]
    assert data["version"] == "1.0.0"


# =============================================================================
# 2. Query Execution & Validation Tests
# =============================================================================

def test_query_success(mock_app_client):
    """Test POST /api/v1/query returns structured response with citations."""
    client, _, _, _ = mock_app_client
    payload = {
        "query": "What is the lock-in period for ELSS mutual funds?",
        "model_modality": "text",
        "top_k": 3,
        "token_budget": 4096,
        "enable_crag": True,
    }
    response = client.post("/api/v1/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["query"]
    assert len(data["answer"]) > 0
    assert "[E1]" in data["answer"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["evidence_id"] == "E1"
    assert data["crag_decision"] == "CORRECT"

    assert data["insufficient_evidence"] is False
    assert "latency" in data
    assert data["latency"]["total_ms"] >= 0.0


def test_query_validation_empty_and_whitespace(mock_app_client):
    """Test POST /api/v1/query rejects empty or whitespace-only queries with HTTP 422."""
    client, _, _, _ = mock_app_client

    # Empty string
    r1 = client.post("/api/v1/query", json={"query": ""})
    assert r1.status_code == 422

    # Whitespace only
    r2 = client.post("/api/v1/query", json={"query": "    \n\t   "})
    assert r2.status_code == 422

    # Missing query field
    r3 = client.post("/api/v1/query", json={"top_k": 5})
    assert r3.status_code == 422


def test_query_boundary_values(mock_app_client):
    """Test POST /api/v1/query bounds checking on top_k and token_budget."""
    client, _, _, _ = mock_app_client

    # top_k = 0 or negative
    r1 = client.post("/api/v1/query", json={"query": "valid query", "top_k": 0})
    assert r1.status_code == 422

    r2 = client.post("/api/v1/query", json={"query": "valid query", "top_k": -5})
    assert r2.status_code == 422

    # token_budget < 500
    r3 = client.post("/api/v1/query", json={"query": "valid query", "token_budget": 200})
    assert r3.status_code == 422


def test_query_streaming_sse(mock_app_client):
    """Test POST /api/v1/query/stream produces valid Server-Sent Events stream."""
    client, _, _, _ = mock_app_client
    payload = {
        "query": "Tell me about ELSS tax deduction rules.",
        "model_modality": "text",
        "top_k": 3,
    }
    response = client.post("/api/v1/query/stream", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "event: metadata" in body
    assert "event: token" in body
    assert "event: done" in body


# =============================================================================
# 3. Document Ingestion & Validation Tests
# =============================================================================

def test_document_upload_success(mock_app_client):
    """Test POST /api/v1/documents with valid PDF stream."""
    client, settings, _, mock_pipeline = mock_app_client
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (Test) >>\nendobj\ntrailer\n<<>>\n%%EOF"

    response = client.post(
        "/api/v1/documents",
        files={"file": ("sample.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        data={"force": "true"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "sample.pdf"
    assert data["status"] == "indexed"
    assert data["document_id"] == "doc_test_1"
    assert data["chunk_count"] == 4
    mock_pipeline.process_file.assert_called()


def test_document_upload_empty_file_rejected(mock_app_client):
    """Test POST /api/v1/documents rejects 0-byte file with HTTP 400."""
    client, _, _, _ = mock_app_client
    response = client.post(
        "/api/v1/documents",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_document_upload_invalid_extension_rejected(mock_app_client):
    """Test POST /api/v1/documents rejects non-PDF file extension with HTTP 400."""
    client, _, _, _ = mock_app_client
    response = client.post(
        "/api/v1/documents",
        files={"file": ("malicious.exe", io.BytesIO(b"%PDF-1.4\nfake"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "must be a pdf" in response.json()["detail"].lower()


def test_document_upload_invalid_magic_bytes_rejected(mock_app_client):
    """Test POST /api/v1/documents rejects file lacking %PDF header with HTTP 400."""
    client, _, _, _ = mock_app_client
    response = client.post(
        "/api/v1/documents",
        files={"file": ("corrupt.pdf", io.BytesIO(b"NOT_A_PDF_DATA"), "application/pdf")},
    )
    assert response.status_code == 400
    assert "%pdf header" in response.json()["detail"].lower()


# =============================================================================
# 4. Document Catalog & Lifecycle Tests
# =============================================================================

def test_document_catalog_listing_and_detail(mock_app_client):
    """Test GET /api/v1/documents listing and GET /api/v1/documents/{doc_id} detail."""
    client, settings, _, _ = mock_app_client

    # Write a test processed json into settings.processed_dir
    processed_dir = settings.get_processed_path()
    sample_doc_id = "doc_sample_123"
    doc_json = processed_dir / f"{sample_doc_id}.json"
    doc_json.write_text(
        json.dumps({
            "document_id": sample_doc_id,
            "document_name": "annual_report.pdf",
            "metadata": {
                "document_id": sample_doc_id,
                "document_name": "annual_report.pdf",
                "page_count": 10,
                "file_size_bytes": 102400,
                "upload_timestamp": "2026-10-25T08:00:00Z",
            },
            "status": "success",
            "total_chunks": 15,
            "chunks": [],
            "rendered_pages": [],
        }),
        encoding="utf-8",
    )

    # 1. Test GET /api/v1/documents
    list_resp = client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert len(docs) >= 1
    target = next((d for d in docs if d["document_id"] == sample_doc_id), None)
    assert target is not None
    assert target["filename"] == "annual_report.pdf"
    assert target["chunk_count"] == 15

    # 2. Test GET /api/v1/documents/{doc_id}
    detail_resp = client.get(f"/api/v1/documents/{sample_doc_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["document_id"] == sample_doc_id
    assert detail["filename"] == "annual_report.pdf"
    assert detail["chunk_count"] == 15

    # 3. Test GET nonexistent document returns 404
    nonexistent_resp = client.get("/api/v1/documents/doc_nonexistent_999")
    assert nonexistent_resp.status_code == 404


def test_document_deletion(mock_app_client):
    """Test DELETE /api/v1/documents/{doc_id} removes files and manifest entry."""
    client, settings, _, _ = mock_app_client

    processed_dir = settings.get_processed_path()
    doc_id = "doc_to_delete"
    doc_json = processed_dir / f"{doc_id}.json"
    doc_json.write_text(json.dumps({"document_id": doc_id, "status": "indexed"}), encoding="utf-8")

    # Verify exists
    assert doc_json.exists()

    # Call DELETE
    del_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200
    data = del_resp.json()
    assert data["deleted"] is True
    assert data["document_id"] == doc_id
    assert not doc_json.exists()

    # Second DELETE on same ID returns 404
    del_resp2 = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp2.status_code == 404
