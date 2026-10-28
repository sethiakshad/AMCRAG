# Visual Orchestrator (Ollama Cloud Gemma 4 Vision) — Implementation Plan

This roadmap tracks the development of the experimental visual retrieval, indexing, and reranking module replacing ColPali with Ollama Cloud's Gemma 4 Vision (`gemma4:31b`), fully isolated within `app/visual_orchestrator/`.

---

## Todo List

- [x] **Step 1: Configuration & Client Layer (`client.py`)**
  - Read `OLLAMA_VISUAL_API_KEY`, `OLLAMA_VISUAL_BASE_URL` (`https://ollama.com`), and `OLLAMA_VISUAL_MODEL` (`gemma4:31b`) from `.env`.
  - Implement `OllamaVisualClient` with multimodal chat support (`images` parameter with base64/file path).
  - Add robust error handling (handling 402 payment/quota errors gracefully with deterministic fallback).

- [x] **Step 2: Visual Model Wrapper (`model.py`)**
  - Replicate `ColPaliModel` public interface (`embed_image`, `embed_images`, `embed_query`, `score`).
  - Generate dense visual semantic representations from page images via Gemma 4 visual understanding.

- [x] **Step 3: Visual Indexer (`indexer.py`)**
  - Replicate `ColPaliIndexer` public interface (`index_page`, `index_document`, `delete_document`).
  - Manage Qdrant collection `gemma_visual_pages` (with embedded local storage fallback).
  - Store rich visual metadata (tables, diagrams, captions, semantic tags) alongside page images.

- [x] **Step 4: Visual Retriever (`retriever.py`)**
  - Replicate `ColPaliRetriever` public interface (`retrieve`).
  - Return exact `ScoredCandidate` / `RetrievalCandidate` format with `modality="visual_page"` and `retrieval_method="visual_gemma"`.

- [x] **Step 5: Visual Reranker (`reranker.py`)**
  - Replicate `ColPaliReranker` public interface (`rerank`, supporting `visual_only` and `full_blend`).
  - Score query-to-image relevance using Gemma 4 multimodal vision prompts.

- [x] **Step 6: High-Level Bridge (`bridge.py`)**
  - Replicate `ColPaliVisualBridge` public interface (`index_pages`, `retrieve`, `rerank`, `delete_document`, `count_document_pages`, `is_ready`).

- [x] **Step 7: Module Exports & Documentation (`__init__.py`, `README.md`)**
  - Clean `__all__` exports matching ColPali's structure.
  - Comprehensive documentation on how to instantiate and benchmark this visual engine.

- [x] **Step 8: Unit Test Suite (`test_visual_orchestrator.py`)**
  - Validate schema compatibility with Person 4 (CRAG) and Person 5 (Context Builder).
  - 100% tests passing in `.venv` (6/6 unit tests passed).

- [x] **Step 9: Targeted Verification on Target PDF (`test_on_svc_pdf.py`)**
  - Tested exclusively on `6-Support+Vector+Classifier.pdf` (3 pages).
  - Successfully rendered 150 DPI page PNGs, indexed into Qdrant `gemma_visual_pages`, and executed multimodal queries.
