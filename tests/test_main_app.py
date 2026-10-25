"""test_main_app.py — Tests for FastAPI application factory, lifespan, CORS, and error handlers."""

import pytest
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def test_app(tmp_path: Path):
    """Create test application with initialize_models=False to test lifespan and factory."""
    settings = Settings(
        base_dir=tmp_path,
        uploads_dir=tmp_path / "data" / "uploads",
        processed_dir=tmp_path / "data" / "processed",
        page_images_dir=tmp_path / "data" / "page_images",
    )
    # Instantiate without heavy models for speed and isolation
    app = create_app(settings=settings, initialize_models=False)
    return app


def test_root_diagnostic_endpoint(test_app):
    """Test GET / returns service information and OpenAPI doc links."""
    with TestClient(test_app) as client:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "AMCRAG — Adaptive Multimodal Corrective RAG"
        assert data["version"] == "1.0.0"
        assert data["status"] == "online"
        assert data["docs_url"] == "/docs"
        assert data["health_url"] == "/api/v1/health"
        assert data["query_url"] == "/api/v1/query"
        assert data["documents_url"] == "/api/v1/documents"


def test_cors_headers(test_app):
    """Test CORS headers are returned for allowed frontend origins."""
    with TestClient(test_app) as client:
        response = client.get(
            "/",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert response.headers.get("access-control-allow-credentials") == "true"


def test_validation_error_handler(test_app):
    """Test global 422 validation exception handler formats JSON response."""
    with TestClient(test_app) as client:
        # Send invalid query request (empty query string)
        response = client.post("/api/v1/query", json={"query": ""})
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "Request validation failed"
        assert "details" in data
        assert isinstance(data["details"], list)
        assert data["status_code"] == 422


def test_not_found_error_handler(test_app):
    """Test global 404 exception handler returns standardized JSON."""
    with TestClient(test_app) as client:
        response = client.get("/api/v1/nonexistent_route_404")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["status_code"] == 404


def test_unhandled_exception_handler(test_app):
    """Test global 500 error handler intercepts uncaught exceptions gracefully."""
    # Add a route that raises an unhandled error
    @test_app.get("/test-unhandled-error")
    def buggy_route():
        raise RuntimeError("Simulated unhandled system crash")

    with TestClient(test_app, raise_server_exceptions=False) as client:
        response = client.get("/test-unhandled-error")
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "Internal Server Error"
        assert "Simulated unhandled system crash" in data["detail"]
        assert data["status_code"] == 500


def test_lifespan_startup_and_shutdown(tmp_path: Path):
    """Verify lifespan context properly tracks start_time and completes shutdown cleanly."""
    settings = Settings(
        base_dir=tmp_path,
        uploads_dir=tmp_path / "data" / "uploads",
        processed_dir=tmp_path / "data" / "processed",
        page_images_dir=tmp_path / "data" / "page_images",
    )
    app = create_app(settings=settings, initialize_models=False)

    with TestClient(app) as client:
        # Server is started inside context
        assert hasattr(app.state, "start_time")
        assert app.state.start_time is not None
        res = client.get("/")
        assert res.status_code == 200
    # Clean exit without exceptions
