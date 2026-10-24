# AMCRAG: Adaptive Multimodal Corrective Retrieval-Augmented Generation

[![Tests](https://img.shields.io/badge/pytest-117%20passed-brightgreen.svg)](#running-tests)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#)

> **B.Tech Research Project:** AMCRAG combines **dense semantic vector retrieval**, **sparse lexical search (BM25)**, and **direct visual page retrieval (ColPali)**, gated by an **Adaptive Corrective RAG (CRAG) decision policy** to deliver hallucination-resistant, multimodal question answering over research papers and complex PDF reports.

---

## 1. System Architecture & End-to-End Flow

```
[ User Query ]
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Upstream Document Ingestion (Person 1)                   │
│    • PyMuPDF / IBM Docling Text & Table Extractor           │
│    • Sentence-Bounded Sliding Window Chunker                │
│    • 150 DPI Visual Page Rasterizer (PNGs + Manifest)       │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               │ list[DocumentChunk]          │ Page PNG Images
               ▼                              ▼
┌──────────────────────────────┐┌─────────────────────────────┐
│ 2. Text Retrieval (Person 2) ││ 3. Visual Search (Person 3) │
│    • Dense: BGE-base (Qdrant)││    • ColPali VLM Multi-     │
│    • Sparse: BM25Okapi       ││      vector late-interaction│
└──────────────┬───────────────┘└─────────────┬───────────────┘
               │                              │
               │ dense & sparse candidates    │ visual candidates
               └──────────────┬───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Reciprocal Rank Fusion (RRF k=60) & Cross-Modal Scoring  │
│    Combined multi-channel candidates: list[RetrievalResult] │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. CRAG Quality Gatekeeper & Query Correction (Person 4)    │
│    • Mindie/T5-Large CRAG Evaluator (Heuristic fallback)    │
│    • Dual Confidence Thresholds (β_upper=0.7, β_lower=0.3)  │
│    • Knowledge Strip Sentence Decomposer                    │
│    • Corrective Query Reformulator (Retry Loop)             │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
   needs_correction == True                   │ can_proceed == True
   (Reformulate query & retry)                ▼
                              ┌───────────────────────────────┐
                              │ 6. Generation & API (Person 5)│
                              │    • FastAPI Orchestrator     │
                              │    • Attributed LLM Answer    │
                              └───────────────────────────────┘
```

---

## 2. Repository Layout & Module Directory

All core source code is cleanly packaged under `app/`:

```text
AMCRAG/
├── app/                                # Core Application Package (Single Source of Truth)
│   ├── chunking/                       # [Person 1] Text chunking & token windowing
│   │   └── text_chunker.py
│   ├── colpali/                        # [Person 3] ColPali multi-vector VLM indexer & retriever
│   │   ├── colpali_indexer.py
│   │   ├── colpali_model.py
│   │   ├── colpali_reranker.py
│   │   └── colpali_retriever.py
│   ├── crag/                           # [Person 4] CRAG evaluation, decisions, & correction
│   │   ├── controller.py
│   │   ├── correction.py
│   │   ├── decisions.py
│   │   └── evaluator.py
│   ├── extractors/                     # [Person 1] PyMuPDF & Docling PDF parsers
│   │   ├── base.py
│   │   ├── docling_extractor.py
│   │   ├── fallback_extractor.py
│   │   └── pymupdf_extractor.py
│   ├── retrieval/                      # [Person 2] Dense (BGE), Sparse (BM25), & RRF Fusion
│   │   ├── dense_engine.py
│   │   ├── sparse_engine.py
│   │   ├── fusion_engine.py
│   │   ├── hybrid_retriever.py
│   │   └── multimodal_bridge.py
│   ├── schemas/                        # Universal Pydantic v2 data models
│   │   ├── chunk.py
│   │   ├── crag.py
│   │   ├── document.py
│   │   └── retrieval.py
│   └── services/                       # Ingestion pipeline & retrieval bridges
│       ├── page_renderer.py
│       ├── pipeline.py
│       └── retrieval_bridge.py
│
├── docs/                               # Teammate Reports & Technical Specifications
│   ├── AMCRAG_Central_Project_Documentation.md
│   ├── COLPALI_MULTIMODAL_PLAN.md
│   ├── CRAG_PERSON_4_REPORT_AND_INTEGRATION_GUIDE.md
│   ├── INTEGRATION_PERSON_1.md
│   ├── OM_WORK_PERSON_2.md
│   ├── PERSON_4_INTEGRATION_GUIDE.md
│   └── TEXT_RETRIEVAL_HYBRID_FUSION_SPEC.md
│
├── evaluation/                         # Benchmarking & Metrics
│   ├── crag_benchmark.py               # CRAG recovery & latency evaluation
│   └── reports/
│       └── crag_benchmark_report.json
│
├── tests/                              # Comprehensive Automated Test Suite
│   ├── test_chunking.py / test_chunk_text.py
│   ├── test_colpali.py
│   ├── test_crag.py
│   ├── test_dense_engine.py / test_sparse_engine.py / test_fusion_engine.py
│   ├── test_docling_extractor.py / test_extractors.py
│   └── test_pipeline.py / test_end_to_end_integration.py
│
├── data/                               # Data directories (uploads, processed, page_images)
├── requirements.txt                    # Unified dependency specification
├── pytest.ini                          # Pytest configuration
└── schemas.py                          # Canonical root contract re-exports
```

---

## 3. Quickstart & Usage

### Installation
```bash
# Clone and enter workspace
git clone https://github.com/sethiakshad/AMCRAG.git
cd AMCRAG

# Install dependencies
pip install -r requirements.txt
```

### 1. Ingest & Process a PDF (Person 1)
```bash
# Process a PDF into chunks and 150 DPI page images
python extract_pdf.py data/sample.pdf
python chunk_text.py data/sample.pdf --chunk-size 500 --chunk-overlap 100
python render_pdf_pages.py data/sample.pdf --dpi 150
```

### 2. Run Hybrid Text Retrieval Simulation (Person 2)
```bash
python verify_pipeline.py
```

### 3. Run CRAG Evaluator & Correction Benchmark (Person 4)
```bash
python evaluation/crag_benchmark.py
```

---

## 4. Running Tests

Run the complete automated test suite (117+ tests):
```bash
pytest
```

Run specific subsystem tests:
```bash
# Person 1: Document processing & chunking
pytest tests/test_chunk_text.py tests/test_extract_pdf.py

# Person 2: Dense & sparse retrieval, RRF fusion
pytest tests/test_fusion_engine.py tests/test_person2_integration.py

# Person 3: ColPali visual retrieval & MaxSim scoring
pytest tests/test_colpali.py

# Person 4: CRAG evaluator, decision engine, & query correction
pytest tests/test_crag.py
```

---

## 5. Teammate Documentation Index

| Teammate | Focus Area | Report / Specification |
| :--- | :--- | :--- |
| **Person 1** | Document Ingestion, PyMuPDF, Docling, & Chunking | [`docs/INTEGRATION_PERSON_1.md`](docs/INTEGRATION_PERSON_1.md) |
| **Person 2** | Dense (BGE), Sparse (BM25), Qdrant, & RRF Fusion | [`docs/OM_WORK_PERSON_2.md`](docs/OM_WORK_PERSON_2.md) |
| **Person 3** | ColPali Multimodal Retrieval & MaxSim Reranking | [`docs/COLPALI_MULTIMODAL_PLAN.md`](docs/COLPALI_MULTIMODAL_PLAN.md) |
| **Person 4** | CRAG Evaluation, Decision Engine, & Reformulation | [`docs/CRAG_PERSON_4_REPORT_AND_INTEGRATION_GUIDE.md`](docs/CRAG_PERSON_4_REPORT_AND_INTEGRATION_GUIDE.md) |
| **Central** | Complete System Architecture & Contracts Specification | [`docs/AMCRAG_Central_Project_Documentation.md`](docs/AMCRAG_Central_Project_Documentation.md) |
