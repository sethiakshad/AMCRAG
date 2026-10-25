# AMCRAG — FastAPI Pipeline Integration & Orchestration Tracker (`todo.md`)

> **Module:** Person 5 — Adaptive Workflow, Pipeline Orchestration, Generation & API Gateway  
> **Source Blueprint:** [`backend/integration-plan.md`](file:///Users/kanishkchaurasia/Documents/AMCRAG/backend/integration-plan.md)  
> **Robustness Framework:** [`backend/test.md`](file:///Users/kanishkchaurasia/Documents/AMCRAG/backend/test.md)  
> **Package Root:** `app/`  
> **Test Suite:** `tests/test_api_orchestrator.py`  

---

## Progress Overview

- [x] **Milestone 1: API Schemas & Data Contracts** (`app/schemas/api.py`)
- [x] **Milestone 2: Answer Generation LLM Service** (`app/services/generator.py`)
- [x] **Milestone 3: End-to-End RAG Orchestrator** (`app/services/orchestrator.py`)
- [x] **Milestone 4: FastAPI Router & Endpoints** (`app/api/v1/`)
- [x] **Milestone 5: Main Application Lifespan & Singleton Management** (`app/main.py`)
- [x] **Milestone 6: Automated Integration & Orchestration Tests** (`tests/test_api_orchestrator.py`)

---

## Detailed Task Breakdown

### Milestone 1: API Schemas & Data Contracts (`app/schemas/api.py`)
- [x] Define `QueryRequest` with validation (`query`, `model_modality`, `token_budget`, `top_k`, `enable_crag`, `document_ids`).
- [x] Define `LatencyBreakdown` tracking milliseconds per pipeline stage (`query_analysis_ms`, `retrieval_ms`, `crag_evaluation_ms`, `context_building_ms`, `generation_ms`, `total_ms`).
- [x] Define `QueryResponse` canonical contract with `answer`, `sources` (`List[SourceMetadata]`), `visual_inputs`, `crag_decision`, `insufficient_evidence`, `retrieval_attempts`, and `latency`.
- [x] Define `DocumentUploadResponse` (`document_id`, `filename`, `status`, `page_count`, `chunk_count`, `image_count`, `message`).
- [x] Define `DocumentSummary` and `DocumentDetailResponse` for knowledge base catalog endpoints.
- [x] Define `DeleteResponse` for document removal.
- [x] Define `HealthResponse` inspecting system readiness across all components.
- [x] Export API schemas in `app/schemas/__init__.py`.

### Milestone 2: Answer Generation LLM Service (`app/services/generator.py`)
- [x] Define `GeneratorConfig` with model provider selection, API keys, temperature, and fallback behavior.
- [x] Implement `AnswerGenerator` class:
  - [x] Ollama Cloud (`https://ollama.com`) integration via official `ollama` SDK (`Client` & `AsyncClient`), model `gemma4:31b`, Bearer token authentication via `OLLAMA_API_KEY` from `.env`.
  - [x] Google Gemini 1.5 Pro / Flash integration via `google.genai` SDK.
  - [x] OpenAI GPT-4o integration via `openai` SDK.
  - [x] High-fidelity Mock Generator for offline evaluation, zero-key development, and automated CI unit tests.
- [x] Implement synchronous / non-streaming generation: `generate(prompt, visual_inputs) -> str`.
- [x] Implement asynchronous streaming generator: `generate_stream(prompt, visual_inputs) -> AsyncIterator[str]`.
- [x] Zero-Hallucination Safe Halt: Detect `insufficient_evidence` or empty context and emit a deterministic non-hallucinatory notice.
- [x] Unit tests for `AnswerGenerator` verifying provider routing, fallback, and streaming (`tests/test_ollama_integration.py`).

### Milestone 3: End-to-End RAG Orchestrator (`app/services/orchestrator.py`)
- [x] Implement `RAGOrchestrator` service coordinator.
- [x] Wire `HybridTextRetriever` (Person 2) and `ColPaliVisualBridge` (Person 3).
- [x] Wire `CRAGController` (Person 4) with bounded reformulation retry loop (`max_retries=2`, cycle avoidance).
- [x] Wire `ContextBuilder` (Person 5) for prompt synthesis and 1-to-1 citation mapping.
- [x] Wire `AnswerGenerator` (Person 5) for final response generation.
- [x] Implement granular latency instrumentation across all pipeline stages.

### Milestone 4: FastAPI Router & Endpoints (`app/api/v1/`)
- [x] Implement `app/api/v1/endpoints/query.py`:
  - [x] `POST /api/v1/query`: Standard end-to-end question answering.
  - [x] `POST /api/v1/query/stream`: Server-Sent Events (SSE) token streaming.
- [x] Implement `app/api/v1/endpoints/documents.py`:
  - [x] `POST /api/v1/documents`: PDF upload, duplicate check, chunking, 150 DPI page rendering, and dual indexing.
  - [x] `GET /api/v1/documents`: List indexed documents.
  - [x] `GET /api/v1/documents/{doc_id}`: Document detail & manifest.
  - [x] `DELETE /api/v1/documents/{doc_id}`: Remove document from vector and BM25 stores.
- [x] Implement `app/api/v1/endpoints/health.py`:
  - [x] `GET /api/v1/health`: System health check.
- [x] Aggregate routers in `app/api/v1/router.py`.

### Milestone 5: Main Application Lifespan & Singleton Management (`app/main.py`)
- [x] Implement FastAPI application factory `create_app()`.
- [x] Implement async Lifespan context manager:
  - [x] Initialize heavy models on startup (CRAG evaluator, BGE embedder, ContextBuilder, Generator).
  - [x] Gracefully release connections and thread pools on shutdown.
- [x] Configure CORS middleware for local React development.
- [x] Implement global exception handlers for clean HTTP 422, 404, 400, and 500 JSON responses.

### Milestone 6: Automated Integration & Orchestration Tests (`tests/test_api_orchestrator.py`)
- [x] Implement FastAPI test client suite.
- [x] Test `POST /api/v1/query` with mock retrievers and mock LLM generator.
- [x] Test `POST /api/v1/documents` PDF upload flow.
- [x] Verify CRAG loop retry limits and insufficient evidence handling.
- [x] Verify 1-to-1 citation mapping in final API response.
- [x] Run full regression test suite across all AMCRAG components.

---

## Post-Test Report Remediation & Production Hardening

- [x] **Fix 1: CRAG Retry Loop Parity in Streaming** (`app/services/orchestrator.py`)
  - [x] Implement bounded reformulation retry loop and cycle avoidance in `query_stream()`.
  - [x] Handle `insufficient_evidence=True` with deterministic safe halt in streaming.
- [x] **Fix 2: LLM Rate-Limit Handling & HTTP 503 Retry-After** (`app/services/generator.py`, `app/api/v1/endpoints/query.py`)
  - [x] Detect HTTP 422/429 rate limit errors from Gemini and OpenAI.
  - [x] Implement exponential backoff retry loop (up to 3 retries).
  - [x] Raise `LLMRateLimitError` mapping to HTTP 503 with `Retry-After: 30` header.
- [x] **Fix 3: CRAG Evaluator 5.0s Timeout Guard** (`app/services/orchestrator.py`)
  - [x] Wrap `process_candidates()` with a 5.0-second timeout guard (`asyncio.wait_for`).
  - [x] Fall back gracefully to heuristic candidate acceptance on timeout or evaluator exceptions.
- [x] **Fix 4: 100 MB Upload Limit & Streaming Chunk Intake** (`app/api/v1/endpoints/documents.py`)
  - [x] Read multipart upload in 1 MB streaming chunks; enforce 100 MB maximum threshold (HTTP 413).
  - [x] Enforce 0-byte upload rejection with HTTP 400.
  - [x] Prevent full in-memory buffering of large files.
- [x] **Fix 5: Upload Path Traversal Sanitization & Collision Isolation** (`app/api/v1/endpoints/documents.py`)
  - [x] Sanitize filename using `Path(filename).name` and reject `..`, `/`, `\` traversal attempts with HTTP 400.
  - [x] Store files under `{doc_id}_{safe_filename}` content-hash isolation to avoid same-name overwrites.
- [x] **Fix 6: Complete Text & Vector Store Purge on Document Deletion** (`app/api/v1/endpoints/documents.py`, `app/retrieval/`)
  - [x] Inject `retriever` in `delete_document`.
  - [x] Purge Qdrant points by `document_id` filter in `BGEDenseEngine` and remove from BM25 storage in `BM25SparseEngine`.
  - [x] Purge ColPali visual records and remove disk artifacts.
- [x] **Fix 7: SSE Citation Event Contract Parity & Client Disconnect** (`app/api/v1/endpoints/query.py`, `app/services/orchestrator.py`)
  - [x] Emit both `event: metadata` and explicit `event: sources` SSE events for frontend compatibility.
  - [x] Monitor `await request.is_disconnected()` and abort generation stream immediately on disconnect.
- [x] **Fix 8: Classify Corrupt PDFs as Client Input Errors (HTTP 400)** (`app/api/v1/endpoints/documents.py`)
  - [x] Map PyMuPDF/extraction failures on corrupt PDFs to HTTP 400 with diagnostic detail.
- [x] **Fix 9: Verification of Previously Skipped Retrieval Tests** (`tests/test_hybrid_retriever.py`, `tests/test_dense_engine.py`)
  - [x] Install `qdrant-client` and execute all 5 retrieval unit/integration tests successfully.
- [x] **Fix 10: Expanded Stress & Robustness Tests** (`tests/test_api_orchestrator.py`)
  - [x] Test 50-query concurrent burst with thread isolation (passed with 0 errors).
  - [x] Test 10-PDF parallel upload collision safety (passed with 10 distinct document IDs).
  - [x] Test LLM 429 rate limit with `Retry-After: 30` header (passed HTTP 503 and SSE error).
  - [x] Test CRAG evaluator timeout with automatic heuristic fallback (passed).
  - [x] Test 100 MB overflow rejection with HTTP 413 (passed).
  - [x] Test path traversal filename rejection (passed).
  - [x] Test text/vector index purge on deletion (passed).
  - [x] Test SSE disconnect handling (passed).


