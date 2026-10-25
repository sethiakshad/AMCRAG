# AMCRAG — Frontend Development Specification & Backend Integration Guide

> **Document Target:** Frontend Development Agent  
> **Destination File:** `frontend/frontend-details.md`  
> **Backend Reference Version:** AMCRAG v1.0.0 (FastAPI + Pydantic v2)  
> **Primary Technology Recommendation:** React 18/19 + TypeScript + Vite + Tailwind CSS / Vanilla CSS  
> **Status:** Definitive Source of Truth & Implementation Blueprint  

---

## 1. Executive Overview & System Architecture

### 1.1 What is AMCRAG?
**AMCRAG** (**A**daptive **M**ultimodal **C**orrective **R**etrieval-**A**ugmented **G**eneration) is an academic research and production-grade Question-Answering system designed to operate over complex PDF collections containing prose, multi-column layouts, tables, graphs, and visual charts.

Traditional RAG systems fail when:
1. Retrieved text lacks table or visual context (diagrams, trend graphs).
2. The initial retrieval step yields irrelevant or noisy passages, leading to LLM hallucinations.
3. Plain text extraction strips structural layout information.
4. The system cannot assess evidence quality or retry poor queries.

AMCRAG solves this through a 5-person orchestrated modular architecture:
- **Person 1 (Document Ingestion & Chunking):** Dual extraction via IBM Docling and PyMuPDF, sentence-bounded sliding-window chunking (800 chars / 150 overlap), and 150 DPI page image rasterization (`.png` files).
- **Person 2 (Hybrid Text Retrieval):** Dense semantic search using BGE-base (`BAAI/bge-base-en-v1.5`) backed by Qdrant vector store + Sparse lexical keyword search (BM25Okapi), fused via Reciprocal Rank Fusion (RRF $k=60$).
- **Person 3 (Visual Page Retrieval):** Direct visual document retrieval via ColPali vision-language multi-vector late-interaction embeddings on rendered page images.
- **Person 4 (Adaptive CRAG Gatekeeper):** Corrective RAG evaluator with dual confidence thresholds ($\beta_{upper}=0.70, \beta_{lower}=0.30$) classifying evidence into `CORRECT`, `AMBIGUOUS`, or `INCORRECT`. Performs knowledge strip sentence decomposition and bounded query reformulation retry loops (up to 2 retries).
- **Person 5 (Orchestrator, Context Builder & API Gateway):** FastAPI backend, strict 1-to-1 citation mapping (`[E1]`, `[E2]`), token budget enforcement, anti-hallucination guard (`insufficient_evidence` deterministic fallback), and multi-provider generation (Ollama Cloud `gemma4:31b`, Google Gemini, OpenAI, Mock).

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                               React Frontend Client                                │
│          (Chat UI, Document Hub, Evidence Drawer, Telemetry Dashboard)            │
└───────────────────────────────┬───────────────────────────────────▲───────────────┘
                                │                                   │
              HTTP POST /query  │                 SSE Stream Tokens │ JSON Metadata
              Multipart Upload  │                                   │ Citations [E#]
                                ▼                                   │
┌───────────────────────────────────────────────────────────────────┴───────────────┐
│                                FastAPI Gateway                                    │
│       • POST /api/v1/query (Standard)       • POST /api/v1/documents (Upload)     │
│       • POST /api/v1/query/stream (SSE)     • GET /api/v1/documents (Catalog)     │
│       • GET /api/v1/health (Probe)          • DELETE /api/v1/documents/{id}       │
└───────────────────────────────────────┬───────────────────────────────────────────┘
                                        │
                         RAG Orchestrator Pipeline
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
  Hybrid Retrieval               ColPali Visual                 CRAG Evaluator
(Dense BGE + Sparse BM25)      (150 DPI Page PNGs)            (T5-Large Quality Gate)
```

---

## 2. Backend Environment, Server & Connectivity

### 2.1 Server Host & Endpoints
- **Base URL:** `http://localhost:8000` (or `http://127.0.0.1:8000`)
- **API Version Route Prefix:** `/api/v1`
- **Interactive OpenAPI Documentation:** `http://localhost:8000/docs` (Swagger UI)
- **Alternative Documentation:** `http://localhost:8000/redoc`
- **Raw OpenAPI Schema:** `http://localhost:8000/openapi.json`

### 2.2 CORS Policy
The backend CORS middleware is already configured in `app/main.py` to allow credentials, all HTTP methods, and all headers for standard frontend development ports:
- `http://localhost:3000` (Create-React-App / Next.js)
- `http://localhost:5173` (Vite dev server)
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

> **Note for Frontend Agent:** If developing on Vite, use port `5173`. If you configure a proxy in `vite.config.ts`, you can forward `/api` requests directly to `http://127.0.0.1:8000`.

### 2.3 Global Error Handling Conventions
The backend returns standardized JSON envelopes for all error codes:

| HTTP Status | Trigger | Response Body Schema |
| :--- | :--- | :--- |
| **400 Bad Request** | Non-PDF file, invalid PDF header (`%PDF-`), 0-byte file, path traversal (`..`), corrupted PDF | `{"error": string, "detail": string, "status_code": 400}` |
| **404 Not Found** | Querying or deleting unknown `doc_id` | `{"error": string, "detail": string, "status_code": 404}` |
| **413 Content Too Large** | Uploading file exceeding 100 MB | `{"error": string, "detail": "Uploaded file exceeds maximum limit of 100 MB.", "status_code": 413}` |
| **422 Validation Error** | Schema violation (e.g. empty `query`, invalid `top_k`, invalid `token_budget`) | `{"error": "Request validation failed", "details": [{"field": string, "message": string, "type": string}], "status_code": 422}` |
| **503 Service Unavailable** | LLM provider rate limit exceeded | `{"error": string, "detail": string, "status_code": 503}` + Header `Retry-After: <seconds>` |
| **500 Internal Error** | Unhandled server exception | `{"error": "Internal Server Error", "detail": string, "status_code": 500}` |

---

## 3. Complete API Contract & Endpoint Reference

### 3.1 `GET /` — Root Diagnostic Probe
Probe service status and verify discovery links.
- **Method:** `GET`
- **Path:** `/`
- **Response (200 OK):**
```json
{
  "service": "AMCRAG — Adaptive Multimodal Corrective RAG",
  "version": "1.0.0",
  "status": "online",
  "docs_url": "/docs",
  "health_url": "/api/v1/health",
  "query_url": "/api/v1/query",
  "documents_url": "/api/v1/documents"
}
```

---

### 3.2 `GET /api/v1/health` — Subsystem Health & Readiness Probe
Checks operational status across underlying services.
- **Method:** `GET`
- **Path:** `/api/v1/health`
- **Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "vector_db": true,
    "bm25": true,
    "crag": true,
    "llm": true,
    "colpali": true
  },
  "uptime_seconds": 142.85
}
```
- **Status Enum:** `"healthy"` (all critical components ready), `"degraded"` (non-critical fallback active), `"unhealthy"`.

---

### 3.3 `POST /api/v1/query` — Standard RAG Query
Executes the full pipeline: adaptive routing, retrieval, CRAG gate, grounding synthesis, and LLM answer generation.
- **Method:** `POST`
- **Path:** `/api/v1/query`
- **Headers:** `Content-Type: application/json`
- **Request Body (`QueryRequest`):**
```json
{
  "query": "What is the lock-in period and tax deduction rule for ELSS mutual funds?",
  "model_modality": "text",
  "token_budget": 4096,
  "top_k": 5,
  "enable_crag": true,
  "document_ids": null
}
```
- **Field Details:**
  - `query` (*string, required*): Min 1 char, non-whitespace.
  - `model_modality` (*string, optional*): `"text"` or `"vision"`. If `null`, backend auto-detects based on visual keywords (`chart`, `graph`, `table`, etc.).
  - `token_budget` (*integer, optional*): Default `4096` (min `500`, max `128000`). Maximum tokens allocated for prompt context.
  - `top_k` (*integer, optional*): Default `5` (min `1`, max `50`). Number of evidence chunks to retrieve.
  - `enable_crag` (*boolean, optional*): Default `true`. Enables T5-Large evaluator, confidence thresholds, and reformulation loop.
  - `document_ids` (*array of strings, optional*): Filter retrieval to specific indexed document IDs. If `null`, searches the entire knowledge base.

- **Response Body (200 OK, `QueryResponse`):**
```json
{
  "query": "What is the lock-in period and tax deduction rule for ELSS mutual funds?",
  "answer": "According to the statutory guidelines [E1], Equity Linked Savings Schemes (ELSS) carry a mandatory lock-in period of 3 years from the date of allotment. Furthermore, investments up to ₹1,50,000 qualify for tax deduction under Section 80C [E2].",
  "sources": [
    {
      "evidence_id": "E1",
      "chunk_id": "doc_a1b2c3d4_chunk_12",
      "document": "investment_handbook.pdf",
      "page": 14,
      "type": "text",
      "source_ref": "investment_handbook.pdf",
      "rank": 1
    },
    {
      "evidence_id": "E2",
      "chunk_id": "doc_a1b2c3d4_chunk_13",
      "document": "investment_handbook.pdf",
      "page": 15,
      "type": "text",
      "source_ref": "investment_handbook.pdf",
      "rank": 2
    }
  ],
  "visual_inputs": [
    "/Users/kanishkchaurasia/Documents/AMCRAG/data/page_images/doc_a1b2c3d4/page_14.png"
  ],
  "crag_decision": "CORRECT",
  "insufficient_evidence": false,
  "retrieval_attempts": 1,
  "latency": {
    "query_analysis_ms": 1.25,
    "retrieval_ms": 34.12,
    "crag_evaluation_ms": 88.40,
    "context_building_ms": 4.15,
    "generation_ms": 520.30,
    "total_ms": 648.22
  }
}
```

---

### 3.4 `POST /api/v1/query/stream` — Streaming RAG Query (Server-Sent Events)
Token-by-token streaming output with real-time citation metadata and pipeline latency.
- **Method:** `POST`
- **Path:** `/api/v1/query/stream`
- **Headers:** `Content-Type: application/json`
- **Request Body:** Same as `POST /api/v1/query` (`QueryRequest`).
- **Response Headers:**
  - `Content-Type: text/event-stream; charset=utf-8`
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`
  - `X-Accel-Buffering: no`
- **Event Lifecycle Flow:**
```
  Client POST /query/stream
            │
            ├─► event: metadata   (Carries query info, initial sources, CRAG decision)
            │
            ├─► event: sources    (Explicit array of SourceMetadata items)
            │
            ├─► event: token      (Streamed token fragment 1)
            ├─► event: token      (Streamed token fragment 2)
            ├─► event: token      (Streamed token fragment N...)
            │
            └─► event: done       (Total latency, retrieval attempts, termination)
```
- **Event Payloads:**
  1. **`event: metadata`**
     ```json
     data: {"query": "...", "sources": [...], "visual_inputs": [...], "crag_decision": "CORRECT", "insufficient_evidence": false, "retrieval_attempts": 1}
     ```
  2. **`event: sources`**
     ```json
     data: [{"evidence_id": "E1", "chunk_id": "...", "document": "...", "page": 1, "type": "text", "source_ref": "...", "rank": 1}]
     ```
  3. **`event: token`**
     ```
     data: According
     data:  to the
     data:  statutory guidelines [E1]...
     ```
  4. **`event: done`**
     ```json
     data: {"total_ms": 782.4, "retrieval_attempts": 1, "insufficient_evidence": false}
     ```
  5. **`event: error` (Emitted if an exception occurs mid-stream)**
     ```json
     data: {"error": "LLM provider rate limit exceeded", "retry_after": 20}
     ```

---

### 3.5 `POST /api/v1/documents` — PDF Document Ingestion & Indexing
Uploads, parses, chunks, rasters 150 DPI page PNGs, and indexes into Qdrant & BM25.
- **Method:** `POST`
- **Path:** `/api/v1/documents`
- **Headers:** `Content-Type: multipart/form-data`
- **Form Data Parameters:**
  - `file` (*File, required*): The `.pdf` file binary (up to 100 MB). Must begin with `%PDF-` magic bytes.
  - `force` (*boolean string, optional*): Default `"false"`. If `"true"`, forces re-processing and overwriting even if the document hash was already indexed.
- **Response (201 Created — Fresh Document):**
```json
{
  "document_id": "doc_e4c83d10f8a92b11",
  "filename": "Q3_Financial_Report.pdf",
  "status": "indexed",
  "page_count": 18,
  "chunk_count": 42,
  "image_count": 18,
  "message": "Successfully indexed 42 chunks and 18 pages."
}
```
- **Response (201 Created — Duplicate Detected & Cached):**
```json
{
  "document_id": "doc_e4c83d10f8a92b11",
  "filename": "Q3_Financial_Report.pdf",
  "status": "cached",
  "page_count": 18,
  "chunk_count": 42,
  "image_count": 18,
  "message": "Document already indexed. Use force=true to re-process and re-index."
}
```

---

### 3.6 `GET /api/v1/documents` — List Indexed Document Catalog
Returns a list of all documents present in the knowledge base.
- **Method:** `GET`
- **Path:** `/api/v1/documents`
- **Response (200 OK):**
```json
[
  {
    "document_id": "doc_e4c83d10f8a92b11",
    "filename": "Q3_Financial_Report.pdf",
    "page_count": 18,
    "chunk_count": 42,
    "upload_timestamp": "2026-10-25T08:14:22Z",
    "file_size_bytes": 4829104
  },
  {
    "document_id": "doc_99182aa10bcde89f",
    "filename": "Technical_Specification.pdf",
    "page_count": 5,
    "chunk_count": 14,
    "upload_timestamp": "2026-10-25T09:00:10Z",
    "file_size_bytes": 1048576
  }
]
```

---

### 3.7 `GET /api/v1/documents/{doc_id}` — Document Manifest & Page Images
Retrieves full manifest metadata, chunk counts, and all rendered page images.
- **Method:** `GET`
- **Path:** `/api/v1/documents/{doc_id}`
- **Response (200 OK):**
```json
{
  "document_id": "doc_e4c83d10f8a92b11",
  "filename": "Q3_Financial_Report.pdf",
  "page_count": 18,
  "chunk_count": 42,
  "image_count": 18,
  "status": "indexed",
  "metadata": {
    "document_id": "doc_e4c83d10f8a92b11",
    "document_name": "Q3_Financial_Report.pdf",
    "page_count": 18,
    "file_size_bytes": 4829104,
    "upload_timestamp": "2026-10-25T08:14:22Z"
  },
  "page_images": [
    "/Users/kanishkchaurasia/Documents/AMCRAG/data/page_images/doc_e4c83d10f8a92b11/page_1.png",
    "/Users/kanishkchaurasia/Documents/AMCRAG/data/page_images/doc_e4c83d10f8a92b11/page_2.png",
    "/Users/kanishkchaurasia/Documents/AMCRAG/data/page_images/doc_e4c83d10f8a92b11/page_18.png"
  ]
}
```
- **Error (404 Not Found):** If `doc_id` is not indexed.

---

### 3.8 `DELETE /api/v1/documents/{doc_id}` — Purge Document from Knowledge Base
Deletes the uploaded PDF, processed JSON chunks, rendered page images, and purges entries from both Qdrant dense vector store and the BM25 sparse index.
- **Method:** `DELETE`
- **Path:** `/api/v1/documents/{doc_id}`
- **Response (200 OK):**
```json
{
  "document_id": "doc_e4c83d10f8a92b11",
  "deleted": true,
  "message": "Document 'doc_e4c83d10f8a92b11' deleted successfully from knowledge base."
}
```
- **Error (404 Not Found):** If document does not exist.

---

## 4. Complete TypeScript Data Models & Contracts

Save this file as `src/types/amcrag.ts` in the React frontend:

```typescript
/**
 * src/types/amcrag.ts
 * Universal TypeScript contracts matching AMCRAG FastAPI v1 models.
 */

export type ModelModality = 'text' | 'vision';
export type EvidenceModality = 'text' | 'visual';
export type CRAGDecisionLabel = 'CORRECT' | 'AMBIGUOUS' | 'INCORRECT';
export type DocumentStatus = 'indexed' | 'cached' | 'failed';
export type SystemHealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface SourceMetadata {
  evidence_id: string;        // e.g. "E1", "E2"
  chunk_id: string;           // Underlying chunk identifier
  document: string;           // Human-readable filename
  page: number | null;        // 1-indexed page number
  type: EvidenceModality;     // "text" or "visual"
  source_ref: string | null;  // Relative path or document URI
  rank: number | null;        // Rank position in retrieved list
}

export interface LatencyBreakdown {
  query_analysis_ms: number;
  retrieval_ms: number;
  crag_evaluation_ms: number;
  context_building_ms: number;
  generation_ms: number;
  total_ms: number;
}

export interface QueryRequest {
  query: string;
  model_modality?: ModelModality | null;
  token_budget?: number;       // default 4096 (500 to 128000)
  top_k?: number;              // default 5 (1 to 50)
  enable_crag?: boolean;       // default true
  document_ids?: string[] | null;
}

export interface QueryResponse {
  query: string;
  answer: string;
  sources: SourceMetadata[];
  visual_inputs: string[];
  crag_decision: CRAGDecisionLabel | null;
  insufficient_evidence: boolean;
  retrieval_attempts: number;
  latency: LatencyBreakdown;
}

// Server-Sent Event Payloads
export interface SSEMetadataEvent {
  query: string;
  sources: SourceMetadata[];
  visual_inputs: string[];
  crag_decision: CRAGDecisionLabel | null;
  insufficient_evidence: boolean;
  retrieval_attempts: number;
}

export interface SSEDoneEvent {
  total_ms: number;
  retrieval_attempts: number;
  insufficient_evidence: boolean;
}

export interface SSEErrorEvent {
  error: string;
  retry_after?: number;
}

// Document Management
export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: DocumentStatus;
  page_count: number;
  chunk_count: number;
  image_count: number;
  message: string;
}

export interface DocumentSummary {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  upload_timestamp: string | null;
  file_size_bytes: number | null;
}

export interface DocumentDetailResponse {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  image_count: number;
  status: string;
  metadata: Record<string, any>;
  page_images: string[];
}

export interface DeleteResponse {
  document_id: string;
  deleted: boolean;
  message: string;
}

// Health & System Information
export interface HealthResponse {
  status: SystemHealthStatus;
  version: string;
  components: {
    vector_db: boolean;
    bm25: boolean;
    crag: boolean;
    llm: boolean;
    colpali?: boolean;
    [key: string]: boolean | undefined;
  };
  uptime_seconds: number | null;
}

export interface ApiRootInfo {
  service: string;
  version: string;
  status: string;
  docs_url: string;
  health_url: string;
  query_url: string;
  documents_url: string;
}

export interface ApiErrorDetail {
  field?: string;
  message: string;
  type?: string;
}

export interface ApiErrorResponse {
  error: string;
  detail?: string;
  details?: ApiErrorDetail[];
  status_code: number;
}
```

---

## 5. Critical Image Serving Architecture (Browser Limitation & Resolution)

### 5.1 The Issue
The backend renders 150 DPI page PNGs to disk at:
`data/page_images/{doc_id}/page_{page_num}.png`

Currently, `GET /api/v1/documents/{doc_id}` returns local absolute filesystem paths, such as:
`"/Users/kanishkchaurasia/Documents/AMCRAG/data/page_images/doc_12345/page_1.png"`

Because modern browsers block loading local `file:///` URLs due to security sandboxing, the frontend **cannot directly pass these absolute strings into `<img src="..." />`**.

### 5.2 Resolution Strategy
1. **URL Path Normalizer Helper:**
Create a utility function `src/utils/imageUrl.ts`:
```typescript
/**
 * Transforms an absolute or relative backend image path into a browser-resolvable URL.
 */
export function resolvePageImageUrl(rawPath: string, backendBaseUrl: string = 'http://localhost:8000'): string {
  if (!rawPath) return '';
  if (rawPath.startsWith('http://') || rawPath.startsWith('https://')) {
    return rawPath;
  }
  
  // Extract doc_id and page_x.png from path pattern .../page_images/{doc_id}/{page_filename}
  const match = rawPath.match(/page_images[\/\\]([^\/\\]+)[\/\\]([^\/\\]+)$/);
  if (match) {
    const [, docId, pageFilename] = match;
    return `${backendBaseUrl}/static/page_images/${docId}/${pageFilename}`;
  }
  
  return rawPath;
}
```

2. **Backend Static Files Mount Note:**
The frontend agent should ensure the backend mounts the static folder (or use a simple FastAPI route if not mounted yet):
```python
# In app/main.py:
from fastapi.staticfiles import StaticFiles
app.mount("/static/page_images", StaticFiles(directory=settings.get_page_images_path()), name="page_images")
```
*If this mount is in place, any image is directly loadable at `http://localhost:8000/static/page_images/{doc_id}/page_{page_num}.png`.*

---

## 6. Detailed Frontend Feature Specifications

To completely and properly serve the AMCRAG backend, the frontend must implement the following 7 core feature modules:

---

### Feature 1: Modern Multimodal Chat & Question-Answering Interface
The primary operational interface for users interacting with the knowledge base.

- **Prompt Input & Controls:**
  - Auto-growing multiline `textarea` with `Shift + Enter` for newlines and `Enter` to submit.
  - Submit Button with loading/streaming spinner.
  - **Stop Generation Button:** An active `AbortController.abort()` button that halts the SSE token stream immediately.
  - Character counter & whitespace validation (prevents submitting empty queries).

- **Modality Switcher:**
  - A 3-state segmented toggle:
    1. **Auto (Default):** Leaves `model_modality = null`. Backend uses its keyword intent classifier (`chart`, `graph`, `table`, `trend`, etc.) to auto-route between text and ColPali visual page retrieval.
    2. **Text Only:** Sends `model_modality = "text"`. Strips image inputs and forces text synthesis.
    3. **Multimodal Vision:** Sends `model_modality = "vision"`. Forces ColPali visual page retrieval and routes page images directly to the VLM.

- **Query Configuration Drawer / Popover:**
  - **`top_k` Slider:** Range `1` to `50` (default: `5`).
  - **`token_budget` Slider:** Range `500` to `32,000` tokens (default: `4,096`).
  - **`enable_crag` Switch:** Toggle between Adaptive CRAG enabled (default `true`) or bypassed (`false`).
  - **Document Scope Filter:** Multi-select dropdown populated from `GET /api/v1/documents`. Allows the user to restrict retrieval to specific documents (`document_ids: string[]`) or query the entire collection (`null`).
  - **Streaming Toggle:** Allows switching between real-time token streaming (`/api/v1/query/stream`) and synchronous execution (`/api/v1/query`).

- **Real-Time Streaming Output:**
  - Progressive token-by-token rendering with a blinking cursor animation `▊`.
  - Full GitHub-flavored Markdown support:
    - Code blocks with syntax highlighting and a "Copy Code" button.
    - Markdown tables, numbered lists, blockquotes, bold/italic text.
    - Mathematical notation support (LaTeX / KaTeX) if research papers contain formulas.

---

### Feature 2: Anti-Hallucination & Provenance System (`[E#]` Citations)
The defining feature of AMCRAG is 100% factual provenance and anti-hallucination guarantees.

- **Interactive Citation Badges in Answer Body:**
  - The LLM emits citations in the form `[E1]`, `[E2]`, `[E3]`.
  - The frontend must parse these tags into clickable badge components (e.g., `<CitationBadge id="E1" />`).
  - **Visual Design:** Distinct pill/chip (e.g. `[E1] Document.pdf, p. 14`) with a hover tooltip showing source preview and confidence rank.

- **Evidence Inspector / Provenance Drawer:**
  - Clicking any citation badge or clicking "View All Sources" opens a slide-over Evidence Drawer.
  - Displays each source mapped 1-to-1 with the backend `sources` array:
    - **Evidence ID:** `E1`, `E2`, etc.
    - **Document Name:** Filename with PDF icon.
    - **Page Number:** Badge displaying `Page {source.page}`.
    - **Modality Type:** `Text Passage` vs `Visual Page`.
    - **Retrieval Rank:** `Rank #1`, `Rank #2`.
    - **Text Content:** If text, shows the passage with highlighted sentence strips.
    - **Visual Preview:** If visual, displays the 150 DPI page PNG image thumbnail. Clicking opens a high-resolution lightbox modal with zoom/pan to inspect tables and charts.

- **Zero-Hallucination Safe Fallback Card:**
  - If `insufficient_evidence == true`:
    - Display a distinctive amber/warning card: *"Insufficient Evidence in Indexed Documents"*.
    - Explain that the CRAG quality gate determined the documents do not contain the answer, preventing an ungrounded hallucination.

---

### Feature 3: CRAG Gatekeeper & Retry Flow Visualizer
Visualizes the decision-making policy of the Corrective RAG engine.

- **CRAG Decision Badge:**
  - Attached to each query message:
    - `CORRECT` (Green): High confidence ($\ge 0.70$). Evidence accepted without alteration.
    - `AMBIGUOUS` (Yellow/Amber): Medium confidence ($0.30 - 0.70$). Evidence contained noise; knowledge strips extracted.
    - `INCORRECT` (Red/Orange): Low confidence ($< 0.30$). Triggered corrective query reformulation.

- **Retrieval Iterations & Reformulation Tracker:**
  - If `retrieval_attempts > 1`:
    - Show an informative badge: *"Answer synthesized after {attempts} retrieval iterations"*.
    - Tooltip or expandable details showing that the query was reformulated to broaden or correct search terms.

---

### Feature 4: Granular Latency & Observability Dashboard
Displays the per-stage execution times returned in `latency: LatencyBreakdown`.

- **Collapsible "Pipeline Telemetry" Widget:**
  - Displays a clean visual waterfall or stacked progress bar:
    1. **Query Analysis:** `{query_analysis_ms} ms`
    2. **Parallel Hybrid Retrieval:** `{retrieval_ms} ms`
    3. **CRAG Evaluation & Retry:** `{crag_evaluation_ms} ms`
    4. **Context Building:** `{context_building_ms} ms`
    5. **Answer Generation (LLM):** `{generation_ms} ms`
    6. **Total Latency:** `{total_ms} ms`
  - Quick summary badge next to message timestamp: `⚡ 1.24s`.

---

### Feature 5: Knowledge Base & Document Management Hub
A dedicated view or sidebar for managing the PDF document catalog.

- **Document Catalog View:**
  - Table or grid view populated via `GET /api/v1/documents`.
  - Columns:
    - **Filename:** Document title with PDF icon.
    - **Document ID:** Monospace ID with copy button.
    - **Pages:** Total extracted pages.
    - **Chunks:** Total generated text chunks.
    - **File Size:** Formatted in KB or MB.
    - **Upload Date:** Relative time (e.g. *"2 hours ago"*).
    - **Actions:**
      - *Inspect Details* (opens modal).
      - *Chat with this Doc* (populates `document_ids` filter in chat).
      - *Delete* (with confirmation dialog).
  - Search bar to filter catalog by document name.

- **Drag-and-Drop PDF Upload Zone:**
  - Drag-and-drop file target accepting `.pdf` files.
  - Client-side pre-validation:
    - Rejects non-PDF extensions.
    - Rejects files larger than 100 MB (`413 Content Too Large` guard).
    - Rejects 0-byte files.
  - **"Force Re-index" Checkbox:** When checked, passes `force=true` to re-process even if cached.
  - **Upload Progress & Status Banner:**
    - Displays progress during upload.
    - On completion, shows:
      - If `status == "indexed"`: Green success toast *"Indexed {chunk_count} chunks across {page_count} pages."*
      - If `status == "cached"`: Blue informational banner *"Document already indexed (cached). Check 'Force Re-index' to overwrite."*

- **Document Detail & Page Image Gallery Modal:**
  - Triggered by `GET /api/v1/documents/{doc_id}`.
  - Displays:
    - Full metadata JSON (file size, timestamp, extraction engine).
    - Page Image Gallery: A carousel or grid of all rendered 150 DPI page PNGs.
    - Lightbox modal allowing zoom, pan, and download of any page image.

- **Document Deletion Dialog:**
  - Modal prompt: *"Are you sure you want to delete {filename}? This will purge all text chunks, vector embeddings, and page images from Qdrant and BM25."*
  - Calls `DELETE /api/v1/documents/{doc_id}` with optimistic UI removal.

---

### Feature 6: Subsystem Health & Hardware Readiness Monitor
Observability into the operational state of the backend components.

- **Status Indicator Pill (Navbar / Header):**
  - Displays live health status:
    - `Healthy` (Green dot): All critical subsystems online.
    - `Degraded` (Yellow dot): Running on CPU fallback or mock provider.
    - `Disconnected` (Red dot): Backend unreachable.
- **System Diagnostics Modal:**
  - Polled periodically via `GET /api/v1/health`.
  - Component status checklist:
    - **Qdrant Vector DB:** Connected / Disconnected
    - **BM25 Lexical Index:** Ready / Empty
    - **CRAG Evaluator:** Online / Unavailable
    - **LLM Generator:** Ready (Ollama Cloud / Gemini)
    - **ColPali Visual Bridge:** Enabled / Disabled
    - **Uptime:** Formatted in hours, minutes, seconds.
  - "Test Connection" button to manually trigger a re-poll.

---

### Feature 7: Resilient Error & Edge-Case Handling

- **LLM Rate-Limit Handling (HTTP 503):**
  - When the backend encounters an `LLMRateLimitError`, it responds with HTTP 503 and a `Retry-After: <seconds>` header.
  - In the SSE stream, it emits `event: error` with `{"error": "...", "retry_after": 20}`.
  - Frontend must display a prominent rate-limit card with a live countdown timer: *"Rate limit reached. Auto-retrying in {countdown}s..."*.

- **Validation Errors (HTTP 422):**
  - Format field errors returned in `details` array (e.g. *"Query cannot be empty"*, *"Token budget must be at least 500"*).

- **Network Disconnects & Stream Cancellation:**
  - If the user clicks "Stop" or navigates away, call `abortController.abort()` to close the HTTP stream. The backend handles `request.is_disconnected()` cleanly.

---

## 7. Recommended Frontend Tech Stack & Architecture

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── assets/
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx            # Main chat container with message history
│   │   │   ├── MessageItem.tsx           # Individual user / assistant message
│   │   │   ├── MessageInput.tsx          # Textarea, modality toggle, submit & stop buttons
│   │   │   ├── ModalitySelector.tsx      # Auto / Text / Vision segmented control
│   │   │   ├── CitationBadge.tsx         # Clickable [E#] pill with tooltip
│   │   │   ├── EvidenceDrawer.tsx        # Slide-over panel showing all citations & images
│   │   │   ├── CRAGBadge.tsx             # CORRECT / AMBIGUOUS / INCORRECT badge
│   │   │   ├── LatencyWaterfall.tsx      # Execution time breakdown bar
│   │   │   └── QuerySettingsModal.tsx    # top_k, token_budget, document scope filter
│   │   ├── documents/
│   │   │   ├── DocumentManager.tsx       # Document hub container
│   │   │   ├── DocumentList.tsx          # Table / card catalog of indexed documents
│   │   │   ├── UploadModal.tsx           # Drag-and-drop PDF uploader with progress
│   │   │   ├── DocumentDetailModal.tsx   # Manifest & metadata inspector
│   │   │   └── PageImageGallery.tsx      # 150 DPI page image carousel / lightbox
│   │   ├── health/
│   │   │   ├── HealthIndicator.tsx       # Navbar pill (healthy/degraded/offline)
│   │   │   └── HealthModal.tsx           # Subsystem component readiness matrix
│   │   └── ui/                           # Reusable UI primitives (Button, Modal, Tooltip, Toast)
│   ├── hooks/
│   │   ├── useSSEQuery.ts                # Custom hook for Server-Sent Events query streaming
│   │   ├── useDocuments.ts               # Hook for listing, uploading, and deleting documents
│   │   └── useHealth.ts                  # Hook for polling backend readiness
│   ├── services/
│   │   ├── api.ts                        # Axios/Fetch API client functions
│   │   └── sse.ts                        # Streaming SSE fetch reader
│   ├── types/
│   │   └── amcrag.ts                     # Pydantic v2 contract TypeScript interfaces
│   ├── utils/
│   │   ├── citationParser.ts             # Regex parser for [E#] tags in markdown
│   │   ├── imageUrl.ts                   # Normalizer for backend page image URLs
│   │   └── formatters.ts                 # File size (KB/MB) and timestamp formatters
│   ├── App.tsx                           # Main app layout (Sidebar + Chat + Documents tab)
│   ├── main.tsx                          # React entrypoint
│   └── index.css                         # Tailwind CSS / Vanilla styling tokens
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### 7.1 Recommended Dependencies
```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.460.0",
    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0",
    "rehype-highlight": "^7.0.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.4"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^6.0.0",
    "tailwindcss": "^3.4.15",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49"
  }
}
```

---

## 8. Ready-to-Use Implementation Snippets

### 8.1 API Service Client (`src/services/api.ts`)
```typescript
import {
  QueryRequest,
  QueryResponse,
  DocumentUploadResponse,
  DocumentSummary,
  DocumentDetailResponse,
  DeleteResponse,
  HealthResponse,
  ApiRootInfo
} from '../types/amcrag';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function fetchRootInfo(): Promise<ApiRootInfo> {
  const res = await fetch(`${BASE_URL}/`);
  if (!res.ok) throw new Error(`Root probe failed: ${res.statusText}`);
  return res.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/health`);
  if (!res.ok) throw new Error(`Health probe failed: ${res.statusText}`);
  return res.json();
}

export async function executeQuery(payload: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || errData.error || `Query failed with status ${res.status}`);
  }
  return res.json();
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${BASE_URL}/api/v1/documents`);
  if (!res.ok) throw new Error(`Failed to list documents: ${res.statusText}`);
  return res.json();
}

export async function getDocumentDetail(docId: string): Promise<DocumentDetailResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/documents/${encodeURIComponent(docId)}`);
  if (!res.ok) throw new Error(`Failed to fetch document: ${res.statusText}`);
  return res.json();
}

export async function uploadDocument(file: File, force: boolean = false): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('force', String(force));

  const res = await fetch(`${BASE_URL}/api/v1/documents`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || errData.error || `Upload failed with status ${res.status}`);
  }
  return res.json();
}

export async function deleteDocument(docId: string): Promise<DeleteResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/documents/${encodeURIComponent(docId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.statusText}`);
  return res.json();
}
```

---

### 8.2 Streaming SSE Query Hook (`src/hooks/useSSEQuery.ts`)
Handles the `POST /api/v1/query/stream` endpoint with token buffering, metadata capture, and `AbortController` cancellation:

```typescript
import { useState, useRef, useCallback } from 'react';
import {
  QueryRequest,
  SourceMetadata,
  CRAGDecisionLabel,
  SSEMetadataEvent,
  SSEDoneEvent
} from '../types/amcrag';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface SSEQueryState {
  isStreaming: boolean;
  tokens: string;
  sources: SourceMetadata[];
  visualInputs: string[];
  cragDecision: CRAGDecisionLabel | null;
  insufficientEvidence: boolean;
  retrievalAttempts: number;
  totalMs: number | null;
  error: string | null;
}

export function useSSEQuery() {
  const [state, setState] = useState<SSEQueryState>({
    isStreaming: false,
    tokens: '',
    sources: [],
    visualInputs: [],
    cragDecision: null,
    insufficientEvidence: false,
    retrievalAttempts: 1,
    totalMs: null,
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(async (request: QueryRequest) => {
    // Reset state
    setState({
      isStreaming: true,
      tokens: '',
      sources: [],
      visualInputs: [],
      cragDecision: null,
      insufficientEvidence: false,
      retrievalAttempts: 1,
      totalMs: null,
      error: null,
    });

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(`${BASE_URL}/api/v1/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || errJson.error || `Stream request failed: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported by browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const block of lines) {
          if (!block.trim()) continue;
          const sublines = block.split('\n');
          let eventName = 'message';
          let dataStr = '';

          for (const line of sublines) {
            if (line.startsWith('event: ')) {
              eventName = line.replace('event: ', '').trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.replace('data: ', '').trim();
            }
          }

          if (eventName === 'metadata') {
            try {
              const meta: SSEMetadataEvent = JSON.parse(dataStr);
              setState(prev => ({
                ...prev,
                sources: meta.sources || [],
                visualInputs: meta.visual_inputs || [],
                cragDecision: meta.crag_decision,
                insufficientEvidence: meta.insufficient_evidence,
                retrievalAttempts: meta.retrieval_attempts,
              }));
            } catch (e) {
              console.error('Failed to parse metadata SSE event', e);
            }
          } else if (eventName === 'sources') {
            try {
              const sourcesList: SourceMetadata[] = JSON.parse(dataStr);
              setState(prev => ({ ...prev, sources: sourcesList }));
            } catch (e) {
              console.error('Failed to parse sources SSE event', e);
            }
          } else if (eventName === 'token') {
            setState(prev => ({ ...prev, tokens: prev.tokens + dataStr }));
          } else if (eventName === 'done') {
            try {
              const doneData: SSEDoneEvent = JSON.parse(dataStr);
              setState(prev => ({
                ...prev,
                totalMs: doneData.total_ms,
                retrievalAttempts: doneData.retrieval_attempts,
                insufficientEvidence: doneData.insufficient_evidence,
                isStreaming: false,
              }));
            } catch {
              setState(prev => ({ ...prev, isStreaming: false }));
            }
          } else if (eventName === 'error') {
            setState(prev => ({ ...prev, error: dataStr, isStreaming: false }));
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Stream generation aborted by user.');
      } else {
        setState(prev => ({ ...prev, error: err.message || 'Stream connection error', isStreaming: false }));
      }
    } finally {
      setState(prev => ({ ...prev, isStreaming: false }));
      abortControllerRef.current = null;
    }
  }, []);

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  return { state, startStream, stopStream };
}
```

---

### 8.3 Citation Parser & Highlight Utility (`src/utils/citationParser.tsx`)
Converts raw markdown containing `[E1]`, `[E2]` citations into styled interactive badges:

```tsx
import React from 'react';
import { SourceMetadata } from '../types/amcrag';

interface CitationParserProps {
  content: string;
  sources: SourceMetadata[];
  onSelectCitation: (evidenceId: string) => void;
}

export const GroundedAnswerView: React.FC<CitationParserProps> = ({
  content,
  sources,
  onSelectCitation,
}) => {
  // Regex matches [E1], [E2], etc.
  const regex = /\[E(\d+)\]/g;
  const parts: (string | React.ReactNode)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    const matchIndex = match.index;
    const evidenceTag = match[0]; // e.g. "[E1]"
    const evidenceId = `E${match[1]}`;

    // Push preceding text
    if (matchIndex > lastIndex) {
      parts.push(content.substring(lastIndex, matchIndex));
    }

    const matchedSource = sources.find(s => s.evidence_id === evidenceId);

    parts.push(
      <button
        key={`cite-${matchIndex}`}
        onClick={() => onSelectCitation(evidenceId)}
        title={matchedSource ? `${matchedSource.document} (Page ${matchedSource.page})` : evidenceId}
        className="inline-flex items-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-500/20 transition-colors"
      >
        {evidenceTag}
      </button>
    );

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < content.length) {
    parts.push(content.substring(lastIndex));
  }

  return <div className="leading-relaxed whitespace-pre-wrap">{parts}</div>;
};
```

---

## 9. Frontend Agent Implementation Checklist

Before declaring the frontend complete, verify each of the following criteria against the running backend:

- [ ] **Vite & Server Connection:**
  - Running on `http://localhost:5173`.
  - Can fetch `GET /` and `GET /api/v1/health` without CORS errors.
- [ ] **Document Upload Flow:**
  - Drag-and-drop PDF upload executes `POST /api/v1/documents`.
  - Correctly renders duplicate notification when backend returns `status: "cached"`.
  - Handles `force=true` re-indexing checkbox.
  - Rejects files $>100$ MB and non-PDFs before dispatching.
- [ ] **Document Catalog & Deletion:**
  - Fetches and displays documents in table with pages, chunks, and file size.
  - Deleting a document calls `DELETE /api/v1/documents/{doc_id}` and removes it from the catalog.
- [ ] **Document Inspection & Page Images:**
  - `GET /api/v1/documents/{doc_id}` loads rendered 150 DPI page PNGs in a responsive gallery or modal.
- [ ] **Query Execution & SSE Streaming:**
  - Natural language questions stream token-by-token using `POST /api/v1/query/stream`.
  - "Stop" button aborts the stream cleanly without client or server warnings.
- [ ] **Citation Mapping:**
  - Generated answers render clickable `[E#]` pills.
  - Clicking `[E#]` highlights the exact page and source passage in the Evidence Drawer.
- [ ] **CRAG Quality Gate Indicator:**
  - Shows `CORRECT`, `AMBIGUOUS`, or `INCORRECT` badge on every answer.
  - Displays retrieval attempt count when reformulation retry was triggered.
- [ ] **Zero-Hallucination Guard:**
  - When `insufficient_evidence: true`, shows a warning card explaining that the indexed documents lack facts for the query.
- [ ] **Telemetry & Latency Waterfall:**
  - Collapsible widget displays time spent in retrieval, CRAG evaluation, context building, and LLM generation.
- [ ] **Health Monitor:**
  - Live status indicator in the navbar showing Vector DB, BM25, CRAG, and LLM health.
