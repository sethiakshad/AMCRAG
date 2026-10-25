# AMCRAG — FastAPI Pipeline Integration & Orchestration Architecture Plan (`integration-plan.md`)

> **Module:** Person 5 — Adaptive Workflow, Pipeline Orchestration, Generation & API Layer  
> **Target Subsystem:** `app/main.py`, `app/api/`, `app/services/orchestrator.py`, `app/services/generator.py`  
> **Status:** Implementation Blueprint  
> **Author/Maintainer:** Person 5 (Kanishk Chaurasia)  
> **Repository Location:** `backend/integration-plan.md`  

---

## 1. Executive Summary & Orchestration Role

In the AMC-RAG (Adaptive Multimodal Corrective RAG) architecture, **Person 5** serves as the central integration conductor and API gateway. While Persons 1 through 4 own individual specialized stages (Ingestion/Chunking, Hybrid Dense/Sparse Retrieval, ColPali Visual Retrieval, and CRAG Quality Evaluation), **Person 5 is responsible for wiring these modules into a single, cohesive, production-grade FastAPI application**.

```
                           [ User / React Frontend ]
                                       │
                                       │ HTTP POST /api/v1/query
                                       ▼
    ╔═════════════════════════════════════════════════════════════════════╗
    ║                 PERSON 5: FASTAPI ORCHESTRATOR                      ║
    ║                                                                     ║
    ║  1. Request Validation & Query Preprocessing                       ║
    ║  2. Adaptive Routing: Modality & Intent Classifier                 ║
    ║                                                                     ║
    ║  ┌───────────────────────────────────────────────────────────────┐  ║
    ║  │ 3. Parallel Upstream Retrieval Integration                    │  ║
    ║  │    • Person 2: HybridTextRetriever (Dense BGE + Sparse BM25)  │  ║
    ║  │    • Person 3: ColPaliVisualBridge (Rendered Page Vectors)    │  ║
    ║  └───────────────────────────────────────────────────────────────┘  ║
    ║                                  │                                  ║
    ║                                  ▼                                  ║
    ║  ┌───────────────────────────────────────────────────────────────┐  ║
    ║  │ 4. Rank Fusion & Candidate Aggregation                        │  ║
    ║  │    • Reciprocal Rank Fusion (RRF) & Cross-Encoder Reranker    │  ║
    ║  └───────────────────────────────────────────────────────────────┘  ║
    ║                                  │ list[RetrievalCandidate]         ║
    ║                                  ▼                                  ║
    ║  ┌───────────────────────────────────────────────────────────────┐  ║
    ║  │ 5. Person 4: CRAG Evaluator & Bounded Retry Loop              │  ║
    ║  │    • T5-Large Quality Gate (0.65 / 0.30)                      │  ║
    ║  │    • CORRECT: Proceed directly                                │  ║
    ║  │    • AMBIGUOUS: Filter noise & re-query if budget permits     │  ║
    ║  │    • INCORRECT: Trigger query reformulation & retry           │  ║
    ║  └───────────────────────────────────────────────────────────────┘  ║
    ║                                  │                                  ║
    ║         ┌────────────────────────┴────────────────────────┐         ║
    ║         │ can_proceed_to_generation=True                  │         ║
    ║         ▼                                                 ▼         ║
    ║  ┌──────────────────────────────┐              ┌──────────────────┐ ║
    ║  │ 6. Person 5: Context Builder │              │ Early Stop       │ ║
    ║  │    (Provenance, Grounding,   │              │ (Insufficient    │ ║
    ║  │     [E#] labels, Modality)   │              │  Evidence)       │ ║
    ║  └──────────────────────────────┘              └──────────────────┘ ║
    ║                 │ ContextResponse                         │         ║
    ║                 ▼                                         │         ║
    ║  ┌──────────────────────────────┐                         │         ║
    ║  │ 7. Answer Generation LLM     │                         │         ║
    ║  │    (Gemini 1.5 / GPT-4o)     │                         │         ║
    ║  └──────────────────────────────┘                         │         ║
    ║                 │                                         │         ║
    ║                 ▼                                         ▼         ║
    ║  8. Synthesize Structured API Response (Answer + [E#] Citations)   ║
    ╚═════════════════════════════════════════════════════════════════════╝
                                       │
                                       │ JSON Response
                                       ▼
                           [ User / React Frontend ]
```

---

## 2. Upstream Module Integration Matrix

To prevent interface drift, Person 5 interfaces strictly with the established and tested contracts of teammates:

| Upstream Subsystem | Module Owner | Primary Entry Point | Input Contract | Emitted Output Contract |
| :--- | :--- | :--- | :--- | :--- |
| **PDF Ingestion & Chunking** | Person 1 | [`DocumentProcessingPipeline`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/services/pipeline.py) | PDF File Path / Upload | [`ProcessedDocumentOutput`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/schemas/chunk.py) |
| **Dense & Sparse Hybrid Retrieval** | Person 2 | [`HybridTextRetriever`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/retrieval/hybrid_retriever.py) | `query: str`, `top_k: int` | `List[RetrievalCandidate]` |
| **ColPali Visual Page Retrieval** | Person 3 | [`ColPaliVisualBridge`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/services/retrieval_bridge.py) | `query: str`, `top_k: int` | `List[RetrievalCandidate]` (`type="visual_page"`) |
| **CRAG Evaluator & Gatekeeper** | Person 4 | [`CRAGController`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/crag/controller.py) | `query`, `candidates`, `attempt` | [`CRAGResult`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/schemas/crag.py) |
| **Context Builder & Citations** | Person 5 | [`ContextBuilder`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/context_builder/builder.py) | `query: str`, `crag_result` | [`ContextResponse`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/context_builder/schemas.py) |
| **Answer Generation LLM** | Person 5 | `AnswerGenerator` (to create) | `prompt: str`, `visual_inputs` | `GeneratedAnswer` |

---

## 3. End-to-End Orchestration Workflows

### A. The Query Workflow (`POST /api/v1/query`)

1. **Request Intake & Validation:**
   - Parse `QueryRequest` (query text, optional token budget override, optional model modality preference, optional metadata filters).
   - Reject empty or whitespace-only queries with HTTP 422.

2. **Adaptive Query Analysis (Routing Gate):**
   - Classify query intent using keyword/structural heuristics:
     - **Visual/Tabular Intent:** Keywords like *"chart"*, *"graph"*, *"trend"*, *"figure"*, *"table"*, *"diagram"*, *"timeline"*. Modality $\rightarrow$ `VISION` or Hybrid.
     - **Textual Intent:** Standard factual/conceptual questions. Modality $\rightarrow$ `TEXT` or Hybrid.

3. **Multi-Store Retrieval & Fusion:**
   - Fetch top-$k$ text candidates from Person 2's `HybridTextRetriever`.
   - Fetch top-$k$ visual candidates from Person 3's `ColPaliVisualBridge`.
   - Fuse and deduplicate using Reciprocal Rank Fusion (RRF) to produce a combined ranked list of `RetrievalCandidate` objects.

4. **CRAG Evaluation & Bounded Retry Loop (Person 4):**
   - Initialize attempt counter `attempt = 0`, max retries $= 2$.
   - Pass candidate list to `CRAGController.process_candidates(active_query, candidates, attempt_number)`.
   - **Case 1: CORRECT** $\rightarrow$ High confidence. Proceed immediately to Context Builder with `crag_result.accepted_candidates`.
   - **Case 2: AMBIGUOUS** $\rightarrow$ Medium confidence. Filter noisy candidates, keep qualified evidence, and proceed.
   - **Case 3: INCORRECT** $\rightarrow$ Low confidence. If `attempt < max_retries`:
     - Retrieve reformulator query from `crag_result.reformulated_query`.
     - Re-trigger retrieval on the reformulated query with loop detection.
     - Increment attempt and re-evaluate.
   - **Termination Condition:** If retries are exhausted and `insufficient_evidence=True`, halt generation to prevent hallucination. Emit an explicit *"insufficient evidence in indexed documents"* message.

5. **Context Building & Grounding Synthesis (Person 5):**
   - Execute `ContextBuilder.build(query=active_query, accepted_evidence=crag_result)`.
   - Ensures strict 1-to-1 mapping of prompt labels (`[E1]`, `[E2]`) to `SourceMetadata` citations.
   - Restricts total tokens strictly within budget.
   - Routes image paths to `visual_inputs` for multimodal LLMs or text descriptions for text-only models.

6. **Answer Generation (Person 5):**
   - Dispatch synthesized prompt (`response.context`) and `response.visual_inputs` to the `AnswerGenerator`.
   - Support model backends:
     - Primary: Google Gemini 1.5 Pro / Flash (`google-genai` / `langchain-google-genai`).
     - Secondary: OpenAI GPT-4o (`openai`).
     - Local Fallback: HuggingFace / Mock generator for offline evaluation.

7. **Structured Response Synthesis:**
   - Assemble `QueryResponse`:
     - `query`: Original user query.
     - `answer`: Generated answer text citing `[E#]` labels.
     - `sources`: Complete list of `SourceMetadata` (document, 1-indexed page, chunk ID, modality, source path).
     - `visual_inputs`: Image paths referenced by the answer.
     - `crag_decision`: Final decision label (`CORRECT`, `AMBIGUOUS`, `INCORRECT`).
     - `retrieval_attempts`: Total attempts executed.
     - `latency_breakdown_ms`: Granular timing for retrieval, CRAG, context builder, and generation.

---

### B. The Document Ingestion Workflow (`POST /api/v1/documents`)

1. **Upload Handling:**
   - Accept PDF file through `UploadFile`.
   - Save file securely to `data/uploads/{filename}`.
   - Validate PDF magic bytes and content integrity.

2. **Deduplication Check:**
   - Execute `DuplicateDetector.check_duplicate(pdf_path)`.
   - If document content hash already exists and `force=False`, return cached document metadata immediately.

3. **Extraction & Chunking (Person 1):**
   - Run `DocumentProcessingPipeline.process_file(pdf_path)`.
   - Generates section-aware `DocumentChunk` records with 1-indexed page numbers and table metadata.
   - Emits structured ledger in `data/processed/{doc_id}.json`.

4. **Page Image Rendering (Person 1):**
   - Render PDF pages at 150 DPI to `data/page_images/{doc_id}/page_{page_num}.png`.
   - Build image manifest in `data/page_images/{doc_id}/manifest.json`.

5. **Dual Downstream Indexing (Person 2 & Person 3):**
   - Index text chunks into Qdrant dense vector collection and sparse BM25 index via `retrieval_bridge.index_document_chunks()`.
   - Index rendered page images into ColPali multi-vector Qdrant collection via `retrieval_bridge.index_colpali_pages()`.

6. **Response:**
   - Return `DocumentUploadResponse` with document ID, page count, chunk count, and indexing status.

---

## 4. API Endpoints Specification

### Routing Architecture: `/api/v1`

| HTTP Method | Route | Description | Request Model | Response Model |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/query` | Primary RAG query execution | `QueryRequest` | `QueryResponse` |
| `POST` | `/api/v1/query/stream` | Server-Sent Events (SSE) streaming query response | `QueryRequest` | `EventSource` |
| `POST` | `/api/v1/documents` | Upload PDF and execute ingestion + indexing | `UploadFile` (Multipart) | `DocumentUploadResponse` |
| `GET` | `/api/v1/documents` | List all indexed documents in knowledge base | — | `List[DocumentSummary]` |
| `GET` | `/api/v1/documents/{doc_id}` | Retrieve processing status and manifest for document | — | `DocumentDetailResponse` |
| `DELETE` | `/api/v1/documents/{doc_id}` | Delete document and remove entries from vector/BM25 stores | — | `DeleteResponse` |
| `GET` | `/api/v1/health` | Subsystem readiness and health check | — | `HealthResponse` |

---

## 5. Detailed Pydantic API Schemas (`app/schemas/api.py`)

```python
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from app.context_builder.schemas import SourceMetadata, ModelModality

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="User's natural language question")
    model_modality: Optional[ModelModality] = Field(
        default=ModelModality.TEXT,
        description="Target model capability (TEXT or VISION)"
    )
    token_budget: Optional[int] = Field(
        default=4096,
        ge=500,
        le=128000,
        description="Max token budget for context prompt"
    )
    top_k: Optional[int] = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of evidence passages to retrieve"
    )
    enable_crag: bool = Field(
        default=True,
        description="Whether to run CRAG evaluation and correction"
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional filter for specific documents"
    )

class LatencyBreakdown(BaseModel):
    query_analysis_ms: float = 0.0
    retrieval_ms: float = 0.0
    crag_evaluation_ms: float = 0.0
    context_building_ms: float = 0.0
    generation_ms: float = 0.0
    total_ms: float = 0.0

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceMetadata] = Field(default_factory=list)
    visual_inputs: List[str] = Field(default_factory=list)
    crag_decision: Optional[str] = None
    insufficient_evidence: bool = False
    retrieval_attempts: int = 1
    latency: LatencyBreakdown

class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: Literal["indexed", "cached", "failed"]
    page_count: int
    chunk_count: int
    image_count: int
    message: str

class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    components: Dict[str, bool]
```

---

## 6. Directory Structure & File Map

To cleanly separate responsibilities and follow FastAPI best practices, the codebase will be organized as follows:

```
app/
├── main.py                          # FastAPI application factory, CORS, Lifespan context
├── config.py                        # Central settings and environment variables
├── api/
│   ├── __init__.py
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── router.py                # Aggregates /query, /documents, /health
│   │   └── endpoints/
│   │       ├── __init__.py
│   │       ├── query.py             # POST /api/v1/query & streaming endpoint
│   │       ├── documents.py         # POST, GET, DELETE /api/v1/documents
│   │       └── health.py            # GET /api/v1/health
├── schemas/
│   ├── api.py                       # HTTP API request/response contracts
│   ├── chunk.py                     # DocumentChunk and ProcessedDocumentOutput
│   ├── crag.py                      # CRAGResult, EvidenceDecision contracts
│   └── retrieval.py                 # RetrievalCandidate contracts
├── services/
│   ├── orchestrator.py              # Core RAGOrchestrator pipeline coordinator
│   ├── generator.py                 # AnswerGenerator LLM client (Gemini / OpenAI / Mock)
│   ├── pipeline.py                  # Person 1 DocumentProcessingPipeline
│   ├── duplicate_detector.py        # Person 1 hash duplicate detector
│   └── retrieval_bridge.py          # Person 2 & 3 indexing and search bridge
├── crag/                            # Person 4 CRAG Evaluator & Gatekeeper
└── context_builder/                 # Person 5 Context Builder & Citations
```

---

## 7. Implementation Roadmap & Milestones

### Milestone 1: API Schemas & Data Contracts (`app/schemas/api.py`)
- Define `QueryRequest`, `QueryResponse`, `DocumentUploadResponse`, `LatencyBreakdown`, and `HealthResponse`.
- Add Pydantic validation rules and OpenAPI schema documentation examples.

### Milestone 2: Answer Generation LLM Service (`app/services/generator.py`)
- Implement `AnswerGenerator` class supporting:
  - Google Gemini 1.5 Pro / Flash via `google-genai` SDK.
  - OpenAI GPT-4o fallback via `openai` SDK.
  - Mock generator for offline evaluation and CI unit testing.
- Support both standard completion and asynchronous streaming generators.

### Milestone 3: End-to-End RAG Orchestrator (`app/services/orchestrator.py`)
- Implement `RAGOrchestrator` service class:
  - Wire `HybridTextRetriever` (Person 2) + `ColPaliVisualBridge` (Person 3).
  - Wire `CRAGController` (Person 4) with query reformulation and retry loop.
  - Wire `ContextBuilder` (Person 5) for prompt assembly and citation mapping.
  - Wire `AnswerGenerator` (Person 5) for answer generation.
  - Measure per-stage latency breakdown.

### Milestone 4: FastAPI Router & Endpoints (`app/api/v1/`)
- Implement `endpoints/query.py` with standard and streaming endpoints.
- Implement `endpoints/documents.py` with upload, listing, and deletion.
- Implement `endpoints/health.py` inspecting component status (Vector DB, BM25, CRAG model, LLM API).
- Aggregate routes in `api/v1/router.py`.

### Milestone 5: Main Application & Lifespan Management (`app/main.py`)
- Implement `create_app()` factory with Lifespan context manager:
  - Load shared singleton models on startup (CRAG evaluator, BGE embedder, ContextBuilder).
  - Close connection pools on shutdown.
- Configure CORS middleware for local React development (`http://localhost:3000`, `http://localhost:5173`).
- Add global exception handlers for graceful HTTP 500/422/404 responses.

### Milestone 6: Automated Integration & Orchestration Tests (`tests/test_api_orchestrator.py`)
- Implement FastAPI test client suite using `httpx.AsyncClient` / `TestClient`.
- Test `POST /api/v1/query` with mock retrievers and mock LLM generator.
- Test `POST /api/v1/documents` PDF upload flow.
- Verify CRAG loop retry limits and insufficient evidence handling.
- Verify 1-to-1 citation mapping in final API response.

---

## 8. Resiliency & Non-Functional Requirements

1. **Zero Hallucination on Insufficient Evidence:**
   When CRAG signals `insufficient_evidence=True` or retries are exhausted without relevant passages, the API must return a deterministic qualified message rather than triggering an ungrounded LLM hallucination.

2. **Graceful Subsystem Degradation:**
   If GPU / ColPali dependencies are unavailable, the orchestrator must automatically fall back to Text-only Dense + BM25 retrieval without crashing the API.

3. **Latency SLA:**
   - Standard text query p95 latency: $< 2.5\text{ s}$ (excluding LLM generation time).
   - Document upload & ingestion: $< 3\text{ s}$ per 10-page document.

4. **Resource Management:**
   Heavy models (CRAG T5-Large, BGE embeddings, ColPali) must be initialized once during application lifespan startup and shared across concurrent requests.
