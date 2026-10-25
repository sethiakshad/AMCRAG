# AMCRAG — Frontend Implementation Roadmap & Task Tracker (`frontend-todo.md`)

> **Module:** AMCRAG Frontend Application (React + TypeScript + Vite)  
> **Source Specification:** [`frontend/frontend-details.md`](file:///Users/kanishkchaurasia/Documents/AMCRAG/frontend/frontend-details.md)  
> **Backend Integration Gateway:** FastAPI v1 (`http://localhost:8001/api/v1`)  
> **Repository Location:** `frontend/frontend-todo.md`  
> **Status:** Fully Implemented & Live Tested ✅  

---

## 1. Progress Overview

- [x] **Milestone 1: Project Scaffolding & Development Environment**
- [x] **Milestone 2: Universal TypeScript Data Contracts & Interfaces**
- [x] **Milestone 3: Networking Layer, REST API Client & SSE Stream Reader**
- [x] **Milestone 4: Design System, App Layout & Shared UI Primitives**
- [x] **Milestone 5: Knowledge Base & Document Management Hub**
- [x] **Milestone 6: Multimodal Chat & Question-Answering Interface**
- [x] **Milestone 7: Grounded Citations & Anti-Hallucination Provenance System**
- [x] **Milestone 8: CRAG Decision Visualizer & Execution Telemetry**
- [x] **Milestone 9: Subsystem Health & Diagnostics Monitor**
- [x] **Milestone 10: Error Handling, Rate-Limit Recovery & Edge Cases**
- [x] **Milestone 11: End-to-End Testing, Polish & Verification**

---

## 2. Detailed Task Breakdown

### Milestone 1: Project Scaffolding & Development Environment
- [x] Initialize Vite application with React and TypeScript in `frontend/`.
- [x] Install core dependencies (`react`, `react-dom`, `lucide-react`, `react-markdown`, `remark-gfm`).
- [x] Configure Google Fonts in `index.html` (Inter, Outfit, JetBrains Mono).
- [x] Configure `vite.config.ts` with development server port `5173` and backend proxy for `/api` and `/static`.
- [x] Set up modular directory structure:
  ```text
  frontend/src/
  ├── components/
  │   ├── chat/
  │   ├── documents/
  │   ├── health/
  │   └── ui/
  ├── hooks/
  ├── services/
  ├── types/
  └── utils/
  ```

### Milestone 2: Universal TypeScript Data Contracts & Interfaces
- [x] Define `src/types/amcrag.ts` containing universal contracts matching backend Pydantic models:
  - [x] `ModelModality`: `'text' | 'vision'`
  - [x] `EvidenceModality`: `'text' | 'visual'`
  - [x] `CRAGDecisionLabel`: `'CORRECT' | 'AMBIGUOUS' | 'INCORRECT'`
  - [x] `DocumentStatus`: `'indexed' | 'cached' | 'failed'`
  - [x] `SystemHealthStatus`: `'healthy' | 'degraded' | 'unhealthy'`
  - [x] `SourceMetadata`: `evidence_id`, `chunk_id`, `document`, `page`, `type`, `source_ref`, `rank`
  - [x] `LatencyBreakdown`: `query_analysis_ms`, `retrieval_ms`, `crag_evaluation_ms`, `context_building_ms`, `generation_ms`, `total_ms`
  - [x] `QueryRequest`: `query`, `model_modality`, `token_budget`, `top_k`, `enable_crag`, `document_ids`
  - [x] `QueryResponse`: `query`, `answer`, `sources`, `visual_inputs`, `crag_decision`, `insufficient_evidence`, `retrieval_attempts`, `latency`
  - [x] `DocumentUploadResponse`: `document_id`, `filename`, `status`, `page_count`, `chunk_count`, `image_count`, `message`
  - [x] `DocumentSummary`: `document_id`, `filename`, `page_count`, `chunk_count`, `upload_timestamp`, `file_size_bytes`
  - [x] `DocumentDetailResponse`: `document_id`, `filename`, `page_count`, `chunk_count`, `image_count`, `status`, `metadata`, `page_images`
  - [x] `DeleteResponse`: `document_id`, `deleted`, `message`
  - [x] `HealthResponse`: `status`, `version`, `components`, `uptime_seconds`
  - [x] SSE Event Types: `SSEMetadataEvent`, `SSEDoneEvent`, `SSEErrorEvent`
  - [x] UI State Models: `ChatMessage`, `QuerySettingsConfig`

### Milestone 3: Networking Layer, REST API Client & SSE Stream Reader
- [x] Implement `src/services/api.ts` with typed asynchronous endpoints:
  - [x] `fetchRootInfo(): Promise<ApiRootInfo>` (`GET /`)
  - [x] `fetchHealth(): Promise<HealthResponse>` (`GET /api/v1/health`)
  - [x] `executeQuery(payload: QueryRequest): Promise<QueryResponse>` (`POST /api/v1/query`)
  - [x] `listDocuments(): Promise<DocumentSummary[]>` (`GET /api/v1/documents`)
  - [x] `getDocumentDetail(docId: string): Promise<DocumentDetailResponse>` (`GET /api/v1/documents/{doc_id}`)
  - [x] `uploadDocument(file: File, force?: boolean): Promise<DocumentUploadResponse>` (`POST /api/v1/documents`)
  - [x] `deleteDocument(docId: string): Promise<DeleteResponse>` (`DELETE /api/v1/documents/{doc_id}`)
- [x] Implement `src/hooks/useSSEQuery.ts` (custom hook for Server-Sent Events):
  - [x] Native `ReadableStream` reader with event boundaries parsing.
  - [x] Handling of `event: metadata`, `event: sources`, `event: token`, `event: done`, `event: error`.
  - [x] Stop stream cancellation via `AbortController.abort()`.
- [x] Implement `src/utils/imageUrl.ts`:
  - [x] Normalization of local file paths into browser-safe URLs (`/static/page_images/{doc_id}/{filename}`).
- [x] Implement `src/utils/formatters.ts`:
  - [x] `formatBytes(bytes)`, `formatUptime(seconds)`, `formatRelativeTime(isoString)`, `formatDuration(ms)`.
- [x] Implement `src/utils/citationParser.ts`:
  - [x] Regex parser decomposing markdown answer into text and `[E#]` citation tokens.

### Milestone 4: Design System, App Layout & Shared UI Primitives
- [x] Implement premium dark glassmorphism design system in `src/index.css`.
- [x] Implement shared UI components:
  - [x] `src/components/ui/Button.tsx`: Primary, secondary, danger, icon variants with loading spinner.
  - [x] `src/components/ui/Badge.tsx`: Brand, success, warning, error, neutral status badges.
  - [x] `src/components/ui/Modal.tsx`: Accessible dialog with blur backdrop and ESC handling.
  - [x] `src/components/ui/Drawer.tsx`: Slide-over panel with smooth slide-in animation.
- [x] Implement App Shell (`src/App.tsx`):
  - [x] Top Navbar with gradient logo, version tag, health pill, OpenAPI docs, and GitHub link.
  - [x] View switcher tabs (`Ask & Chat` vs `Knowledge Base`).

### Milestone 5: Knowledge Base & Document Management Hub
- [x] Implement `src/hooks/useDocuments.ts`: catalog state, search queries, upload, and deletion handlers.
- [x] Implement `src/components/documents/UploadModal.tsx`:
  - [x] Drag-and-drop PDF upload zone.
  - [x] 100 MB max size and `.pdf` extension validation.
  - [x] Force re-index toggle (`force=true`).
  - [x] Duplicate detection feedback (`cached` vs `indexed`).
- [x] Implement `src/components/documents/DocumentList.tsx`:
  - [x] Real-time search filter.
  - [x] Document cards displaying page count, chunk count, file size, relative upload time.
  - [x] Actions for querying specific doc, inspecting manifest, and deleting.
- [x] Implement `src/components/documents/DocumentDetailModal.tsx`:
  - [x] Manifest inspector displaying chunks, metadata, and 150 DPI page gallery.
  - [x] Full-screen lightbox with zoom, pan, and page navigation.
- [x] Implement `src/components/documents/DeleteConfirmModal.tsx`:
  - [x] Confirmation warning before purging vectors and images.
- [x] Implement `src/components/documents/DocumentManager.tsx` container view.

### Milestone 6: Multimodal Chat & Question-Answering Interface
- [x] Implement `src/components/chat/ChatWindow.tsx`:
  - [x] Conversational message list with auto-scroll.
  - [x] Empty state with starter questions and architecture highlights.
  - [x] Document filter scope notification banner.
- [x] Implement `src/components/chat/MessageInput.tsx`:
  - [x] Auto-expanding textarea (`Enter` to submit, `Shift+Enter` for newline).
  - [x] Stop generation button active during streaming.
  - [x] Modality toggle trigger and settings trigger.
- [x] Implement `src/components/chat/ModalitySelector.tsx`:
  - [x] 3-state segmented control: `Auto (Smart)`, `Text Only`, `Multimodal Vision`.
- [x] Implement `src/components/chat/QuerySettingsModal.tsx`:
  - [x] `top_k` slider (1 to 50), `token_budget` slider (500 to 16,000), `enable_crag` toggle, document filter multi-select.
- [x] Implement `src/components/chat/MessageItem.tsx`:
  - [x] Markdown answer with blinking cursor `▊`.
  - [x] Copy answer button with visual confirmation.

### Milestone 7: Grounded Citations & Anti-Hallucination Provenance System
- [x] Implement `src/components/chat/CitationBadge.tsx`:
  - [x] Interactive clickable `[E#]` pills with hover preview tooltips.
- [x] Implement `src/components/chat/EvidenceDrawer.tsx`:
  - [x] Slide-over drawer mapping 1-to-1 with `sources` array.
  - [x] Fusion rank, document name, page number, and chunk ID.
  - [x] 150 DPI page image previews with click-to-zoom lightbox.
- [x] Implement Zero-Hallucination Guard Card:
  - [x] Displays alert banner when `insufficient_evidence: true`.

### Milestone 8: CRAG Decision Visualizer & Execution Telemetry
- [x] Implement `src/components/chat/CRAGBadge.tsx`:
  - [x] Status pills for `CORRECT` (emerald), `AMBIGUOUS` (amber), `INCORRECT` (rose).
  - [x] Retry attempt counter when query reformulation was triggered.
- [x] Implement `src/components/chat/LatencyWaterfall.tsx`:
  - [x] Collapsible telemetry widget with waterfall bars:
    - Query Analysis
    - Parallel Retrieval & Fusion
    - CRAG Gate & Reformulation
    - Context Building & Citations
    - LLM Answer Generation
    - Total Latency badge

### Milestone 9: Subsystem Health & Diagnostics Monitor
- [x] Implement `src/hooks/useHealth.ts`:
  - [x] Background polling every 20s.
- [x] Implement `src/components/health/HealthIndicator.tsx`:
  - [x] Real-time status pill in the navbar (`System Online`, `Degraded`, `Offline`).
- [x] Implement `src/components/health/HealthModal.tsx`:
  - [x] Diagnostic matrix showing status of Qdrant, BM25, CRAG, LLM, ColPali, and service uptime.
  - [x] Manual re-check ping button.

### Milestone 10: Error Handling, Rate-Limit Recovery & Edge Cases
- [x] HTTP 503 LLM rate limit recovery banner with `Retry-After` countdown notice.
- [x] Network offline alert banner with retry trigger.
- [x] Empty and whitespace query submission guards.
- [x] Client-side 100 MB file size limit and format check.

### Milestone 11: End-to-End Testing, Polish & Verification
- [x] TypeScript compiler build check (`npm run build` passes with exit code 0).
- [x] Backend static page image mount configured in `app/main.py`.
- [x] Backend test suite passes (`pytest` passes with 17/17 tests).
- [x] Live end-to-end browser verification via browser subagent:
  - [x] Navbar brand & System Online indicator verified.
  - [x] Subsystem Health & Readiness Diagnostics modal verified.
  - [x] Knowledge Base view, catalog, and Ingest PDF modal verified.
  - [x] Ask & Chat RAG query execution verified.
  - [x] Response rendering, CRAG decision badge, and latency telemetry waterfall verified.
  - [x] Session video recorded to artifacts (`frontend_ui_test_1792922761052.webp`).
