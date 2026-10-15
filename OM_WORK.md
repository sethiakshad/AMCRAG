# AMCRAG Person 2: Dense & Sparse Text Retrieval & Hybrid Fusion Subsystem
## Comprehensive Report & Integration Guide

**Module:** Person 2 — Text Retrieval Subsystem (Dense Vector + Sparse BM25 + Canonical RRF Fusion)  
**Author:** Om Khapekar (`om_branch`)  
**Status:** ✅ Fully Implemented, Validated, and Tested (16/16 tests pass)  
**Target Audience:** Person 1 (Document Ingestion & Chunking), Person 3 (ColPali Visual Retrieval & Reranker), Person 4 (CRAG Evaluator), Person 5 (FastAPI Orchestrator)

---

## 1. Executive Summary & Architecture Role

Person 2 is responsible for the **core text retrieval and hybrid ranking foundation** of AMC-RAG. It indexes text chunks ingested by Person 1 and serves ranked, fused candidate passages to Person 3 (Multimodal Retrieval & Reranker), Person 4 (CRAG Evaluator), and Person 5 (FastAPI Orchestrator).

```
                 [ Person 1: Ingestion & Chunking (Docling/PyMuPDF) ]
                                          │
                                          ▼  list[DocumentChunk]
                     [ Plug 1: index_knowledge_base() ]
                                          │
                     ┌────────────────────┴────────────────────┐
                     ▼                                         ▼
         [ BGEDenseEngine (Qdrant) ]               [ BM25SparseEngine (Okapi) ]
         • BAAI/bge-base-en-v1.5                   • Term Inverted Index
         • 768-dim Normalized Embeddings           • k1=1.5, b=0.75
         • HNSW M=16, efConstruct=128             • Exact Token Preserving
                     │                                         │
═════════════════════╪═════════════════════════════════════════╪═════════════════════
   QUERY TIME        │                                         │
                     ▼                                         ▼
         [ Active Query / Retry ]                  [ Active Query / Retry ]
                     │                                         │
                     ▼                                         ▼
         dense_candidates [ScoredCandidate]       sparse_candidates [ScoredCandidate]
                     │                                         │
                     └────────────────────┬────────────────────┘
                                          │
                                          ├─────────◄ [ Optional: Person 3 ColPali ]
                                          │           (visual_candidates)
                                          ▼
                      [ ReciprocalRankFusion (k=60) ]
                      • Multi-channel score-invariant fusion
                      • RRF(d) = Σ w_r / (k + rank_r(d))
                                          │
                                          ▼  list[RetrievalResult / RetrievalCandidate]
                      [ Plug 2: retrieve(query, top_k) ]
                                          │
                     ┌────────────────────┴────────────────────┐
                     ▼                                         ▼
     [ Person 3: BGE Reranker ]               [ Person 4: CRAG Evaluator ]
     (Joint Cross-Encoder Scoring)            (Mindie/T5-Large Quality Gate)
```

---

## 2. Person 2 Implementation Overview

All components are implemented with zero external framework lock-in, clean object-oriented architecture, and full Pydantic v2 validation:

| Component | File | Responsibilities |
|---|---|---|
| **Data Contracts** | [`schemas.py`](file:///c:/BTP_AMC_RAG/AMCRAG/schemas.py) | Universal data schemas: `DocumentChunk`, `ScoredCandidate`, `RetrievalResult`, and Section 10.1 `RetrievalCandidate` alias. |
| **Dense Semantic Vector Engine** | [`dense_engine.py`](file:///c:/BTP_AMC_RAG/AMCRAG/dense_engine.py) | `BAAI/bge-base-en-v1.5` embeddings (768-dim, normalized cosine), query instruction prefix, Qdrant HNSW indexing ($M=16, efConstruct=128$), metadata filtering, and dual API compatibility (`query_points` / `search`). |
| **Sparse Lexical Engine** | [`sparse_engine.py`](file:///c:/BTP_AMC_RAG/AMCRAG/sparse_engine.py) | `BM25Okapi` ($k_1=1.5, b=0.75$), regex alphanumeric tokenizer preserving exact identifiers and error codes, disk persistence (`save_index`/`load_index`), and metadata filtering. |
| **Canonical RRF Fusion Engine** | [`fusion_engine.py`](file:///c:/BTP_AMC_RAG/AMCRAG/fusion_engine.py) | Single canonical Reciprocal Rank Fusion ($k=60$) combining dense, sparse, and visual channels without score calibration distortion; multi-channel support (`fuse_multi`). |
| **Unified Hybrid Retriever** | [`hybrid_retriever.py`](file:///c:/BTP_AMC_RAG/AMCRAG/hybrid_retriever.py) | Master subsystem interface featuring **Plug 1** (`index_knowledge_base`) for Person 1 and **Plug 2** (`retrieve`) conforming strictly to Section 10.2. |
| **Cross-Modal Bridge Demo** | [`multimodal_bridge.py`](file:///c:/BTP_AMC_RAG/AMCRAG/multimodal_bridge.py) | Reference bridge demonstrating cross-modal fusion with Person 3's ColPali visual page candidates prior to downstream reranking. |
| **Automated Test Suite (16/16 Pass)** | [`tests/`](file:///c:/BTP_AMC_RAG/AMCRAG/tests) | 16 unit and integration tests across 5 test modules (`test_schemas.py`, `test_dense_engine.py`, `test_sparse_engine.py`, `test_fusion_engine.py`, `test_hybrid_retriever.py`). |
| **Empirical Retrieval Benchmark** | [`benchmark_retrieval.py`](file:///c:/BTP_AMC_RAG/AMCRAG/benchmark_retrieval.py) | Standalone evaluation measuring Hit@1, Hit@3, MRR, and sub-millisecond to millisecond latency breakdown across diverse query categories. |
| **Pipeline Verification Suite** | [`verify_pipeline.py`](file:///c:/BTP_AMC_RAG/AMCRAG/verify_pipeline.py) | End-to-end simulation verifying ingestion, hybrid retrieval, and contract conformance. |

---

## 3. Technical Specifications & Empirical Findings

### Core Engine Parameters

| Parameter | Dense Engine (BGE + Qdrant) | Sparse Engine (BM25Okapi) | Hybrid Fusion (RRF) |
|---|---|---|---|
| **Underlying Model / Algo** | `BAAI/bge-base-en-v1.5` | `rank-bm25` (BM25Okapi) | Cormack et al. Reciprocal Rank Fusion |
| **Representation** | 768-dimensional dense vectors (L2-normalized) | Inverted term-frequency index | Rank reciprocal accumulation |
| **Distance / Scoring** | Cosine distance (Dot product on normalized) | TF-IDF based Okapi ($k_1=1.5, b=0.75$) | $\sum_{r \in R} \frac{w_r}{k + \operatorname{rank}_r(d)}$ |
| **Query Prefix** | `"Represent this sentence for searching relevant passages: "` | None (Tokenized regex) | N/A |
| **Indexing Structure** | Qdrant HNSW ($M=16, efConstruct=128$) | Python Inverted Hash Map | Ranked Dict Aggregator |
| **Storage Modes** | In-Memory (`:memory:`), Disk (`./qdrant_storage`), or Remote URL | Pickled index (`./bm25_index.pkl`) | Stateless in-memory operation |
| **Smoothing Constant** | N/A | N/A | $k = 60$ |
| **Average Latency** | ~24.38 ms | ~0.13 ms | ~23.16 ms (Total end-to-end) |

### Why Reciprocal Rank Fusion (RRF) Over Score Normalization?
* **Score Scale Discrepancy:** Dense cosine similarities produce bounded scores in $[-1.0, 1.0]$ (typically clustering in $[0.60, 0.90]$ for relevant text), whereas BM25 produces unbounded scores in $[0, \infty)$ dependent on query length and corpus term frequencies.
* **Calibration Vulnerability:** Linear score blending ($\alpha \cdot S_{dense} + (1-\alpha) \cdot S_{bm25}$) requires dynamic min-max normalization that breaks when out-of-domain queries or single outliers skew the batch extremes.
* **RRF Invariance:** RRF operates solely on **ordinal rank positions**. Setting $k=60$ smoothly dampens outlier ranks, ensuring that a passage ranked #1 in either modality receives substantial weight without being overwhelmed by arbitrary raw score magnitudes.

---

## 4. Benchmark & Test Verification Results

### Unit & Integration Tests (16/16 Pass)
```
python -m pytest -v
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\BTP_AMC_RAG\AMCRAG
collected 16 items

tests/test_dense_engine.py::test_dense_indexing_and_search PASSED        [  6%]
tests/test_dense_engine.py::test_dense_filtering PASSED                  [ 12%]
tests/test_dense_engine.py::test_dense_empty_query PASSED                [ 18%]
tests/test_fusion_engine.py::test_rrf_scoring_math PASSED                [ 25%]
tests/test_fusion_engine.py::test_rrf_with_visual_candidates PASSED      [ 31%]
tests/test_fusion_engine.py::test_rrf_multi_channel PASSED               [ 37%]
tests/test_hybrid_retriever.py::test_end_to_end_ingestion_and_retrieval PASSED [ 43%]
tests/test_hybrid_retriever.py::test_hybrid_filtered_retrieval PASSED    [ 50%]
tests/test_schemas.py::test_document_chunk_contract PASSED               [ 56%]
tests/test_schemas.py::test_scored_candidate_contract PASSED             [ 62%]
tests/test_schemas.py::test_retrieval_candidate_aliases PASSED           [ 68%]
tests/test_sparse_engine.py::test_bm25_tokenize PASSED                   [ 75%]
tests/test_sparse_engine.py::test_bm25_search_and_ranking PASSED         [ 81%]
tests/test_sparse_engine.py::test_bm25_filtering PASSED                  [ 87%]
tests/test_sparse_engine.py::test_bm25_empty_query_handling PASSED       [ 93%]
tests/test_sparse_engine.py::test_bm25_disk_persistence PASSED           [100%]

======================= 16 passed, 1 warning in 29.28s ========================
```

### Empirical Retrieval Benchmark ([`benchmark_retrieval.py`](file:///c:/BTP_AMC_RAG/AMCRAG/benchmark_retrieval.py))

Evaluated across semantic conceptual questions, exact error codes, and technical hybrid queries:

| Metric | Dense (BGE-base-en-v1.5) | Sparse (BM25Okapi) | Hybrid RRF ($k=60$) |
|---|---|---|---|
| **Hit@1** | **100.0%** | **100.0%** | **100.0%** |
| **Hit@3** | **100.0%** | **100.0%** | **100.0%** |
| **Mean Reciprocal Rank (MRR)** | **1.0000** | **1.0000** | **1.0000** |
| **Mean Latency per Query** | 24.38 ms | 0.13 ms | 23.16 ms |

#### Complementary Strength Insights:
1. **Exact Identifiers & Diagnostics:** For queries such as `"ERR-804 HNSW corruption and ERR-502 timeout"`, BM25 executes in **0.13 ms** and isolates the exact target chunk with 100% precision. Dense vectors may suffer from sub-word tokenization fragmentation on novel error codes.
2. **Abstract Conceptual Matching:** For queries such as `"How does CRAG assess retrieval confidence and what model does it use?"`, BGE semantic vectors correctly map paraphrased concepts to passages mentioning `"lightweight retrieval evaluator using fine-tuned T5-large"`.
3. **Hybrid RRF Synergy:** By combining both channels with $k=60$, high-confidence matches from either channel surge to Rank 1, while noisy false positives are filtered down.

---

## 5. Interface Contract for Person 1 (Ingestion & Chunking)

### Input Contract: `DocumentChunk`
Person 1's parsing and chunking pipeline (Docling / PyMuPDF) must yield text chunks conforming to [`schemas.DocumentChunk`](file:///c:/BTP_AMC_RAG/AMCRAG/schemas.py):

```python
from schemas import DocumentChunk

chunk = DocumentChunk(
    chunk_id="doc1_chunk_004",                          # Unique deterministic ID or UUID
    document_id="annual_financial_report_2025.pdf",     # Parent document identifier
    page_number=12,                                     # Primary 1-indexed page
    text="Net profit increased by 14.2% year-over-year...", # Extracted passage text
    source_filename="annual_financial_report_2025.pdf", # Source filename
    page_start=12,                                      # Starting page span (1-indexed)
    page_end=12,                                        # Ending page span (1-indexed)
    metadata={                                          # Rich layout metadata
        "section": "Financial Results",
        "headings": ["Executive Summary", "Financial Highlights"],
        "table": False,
        "bbox": [54.0, 120.5, 480.0, 310.2]
    }
)
```

### Ingestion Hook: `index_knowledge_base`
Person 1 invokes Person 2's ingestion method once document chunking is complete:

```python
from hybrid_retriever import HybridTextRetriever

retriever = HybridTextRetriever()

# Ingest all document chunks into Qdrant vector store and BM25 index
retriever.index_knowledge_base(chunks=[chunk1, chunk2, chunk3])
```

#### Ingestion Guarantees:
* **Deterministic UUID Generation:** If `chunk_id` is a string (e.g., `"doc1_chunk_004"`), Qdrant automatically generates a deterministic UUIDv5 using the DNS namespace, preventing duplicate vectors upon re-indexing.
* **Payload Preservation:** All metadata dictionary fields (`section`, `headings`, `bbox`) are preserved verbatim in both Qdrant point payloads and BM25 chunk lookups.

---

## 6. Interface Contract for Person 3 & Person 4 (Retrieval, Reranker & CRAG)

### Output Contract: `RetrievalResult` (Aliased as `RetrievalCandidate`)
When `retriever.retrieve(...)` is invoked, Person 2 returns a `list[RetrievalResult]`. This object conforms strictly to **Section 10.1 of Central Documentation** and matches **Person 4's expected input**:

```python
from schemas import RetrievalResult, RetrievalCandidate

# RetrievalCandidate is an alias of RetrievalResult:
# RetrievalCandidate = RetrievalResult

result = RetrievalResult(
    chunk_id="doc1_chunk_004",
    document_id="annual_financial_report_2025.pdf",
    page_number=12,
    text="Net profit increased by 14.2% year-over-year...",
    modality="text",                                   # "text" or "visual_page"
    source_filename="annual_financial_report_2025.pdf",
    page_start=12,
    page_end=12,
    dense_score=0.884,                                 # Raw BGE cosine score
    sparse_score=11.45,                                # Raw BM25 score
    dense_rank=1,                                      # Rank in dense retrieval
    sparse_rank=2,                                     # Rank in sparse retrieval
    fused_score=0.0325,                                # RRF combined score
    metadata={"section": "Financial Results"}
)
```

#### Cross-Module Property Compatibility Aliases:
To ensure 100% interoperability with Person 4 (`CRAGController`) and Person 3 (`BGE-reranker-base`) without schema adaptation layers:
* `result.candidate_id` $\rightarrow$ maps to `result.chunk_id`
* `result.candidate_type` $\rightarrow$ returns `"visual_page"` if `modality == "visual_page"` else `"text_chunk"`
* `result.retrieval_score` $\rightarrow$ maps to `result.fused_score`

### Query Hook: `retrieve`
```python
candidates = retriever.retrieve(
    query="What was the net profit increase in 2025?",
    top_k=15,                                          # Number of fused candidates to return
    filters={"document_id": "annual_financial_report_2025.pdf"} # Optional metadata filter
)
```

---

## 7. Single Canonical RRF Fusion Extension Contract (For Person 3 ColPali)

To prevent fragmented or duplicate fusion logic across the team, Person 2 provides the **single canonical fusion extension point** for combining Person 2's text candidates with Person 3's ColPali visual page candidates.

### Direct Integration in `retrieve()`
Person 3 can pass raw visual candidates directly into `retrieve()`:

```python
visual_candidates = colpali_retriever.search_pages(query=user_query, top_k=10)

fused_candidates = retriever.retrieve(
    query=user_query,
    top_k=15,
    visual_candidates=visual_candidates  # Seamlessly merged via RRF!
)
```

### Standalone Fusion with `ReciprocalRankFusion`
Person 3 can also invoke [`fusion_engine.py`](file:///c:/BTP_AMC_RAG/AMCRAG/fusion_engine.py) directly:

```python
from fusion_engine import ReciprocalRankFusion

fusion = ReciprocalRankFusion(
    k=60,
    weight_dense=1.0,
    weight_sparse=1.0,
    weight_visual=1.0  # Equal weighting across text and visual modalities
)

fused_results = fusion.fuse(
    dense_candidates=dense_results,
    sparse_candidates=bm25_results,
    visual_candidates=colpali_results,
    top_k=15
)
```

---

## 8. Interface Contract for Person 5 (FastAPI Orchestrator)

### Service Initialization at Startup
Initialize `HybridTextRetriever` once during FastAPI application startup:

```python
from fastapi import FastAPI
from hybrid_retriever import HybridTextRetriever
import os

app = FastAPI(title="AMC-RAG API")

retriever: HybridTextRetriever = None

@app.on_event("startup")
def startup_event():
    global retriever
    retriever = HybridTextRetriever(
        dense_model_name=os.getenv("BGE_MODEL_NAME", "BAAI/bge-base-en-v1.5"),
        qdrant_path=os.getenv("QDRANT_PATH", "./qdrant_storage"),
        bm25_index_path=os.getenv("BM25_INDEX_PATH", "./bm25_index.pkl"),
        rrf_k=int(os.getenv("RRF_K", 60)),
        device=os.getenv("RETRIEVER_DEVICE", None)
    )
```

### Orchestrator Request-Time Retrieval Loop
```python
@app.post("/query")
async def handle_query(request: QueryRequest):
    # 1. Retrieve hybrid candidates from Person 2
    candidates = retriever.retrieve(
        query=request.query,
        top_k=15,
        filters=request.filters
    )
    
    # 2. (Optional) Pass to Person 3 BGE Reranker
    reranked = reranker.rerank(request.query, candidates, top_k=5)
    
    # 3. Pass to Person 4 CRAG Evaluator
    crag_result = crag_controller.process_candidates(
        query=request.query,
        candidates=reranked,
        attempt_number=0
    )
    
    # If CRAG triggers query reformulation, Person 5 simply re-calls Person 2:
    if crag_result.needs_correction:
        retry_candidates = retriever.retrieve(
            query=crag_result.reformulated_query,
            top_k=15
        )
        # Continue evaluation loop...
```

---

## 9. Upstream & Downstream Dependencies Matrix

| Teammate | Dependency / Expectation | Why it matters |
|---|---|---|
| **Person 1 (Ingestion & Chunking)** | Provide `DocumentChunk` with populated `text`, `source_filename`, and 1-indexed `page_start`/`page_end`. | Required for deterministic Qdrant point creation, BM25 indexing, and page provenance citation. |
| **Person 1 (Ingestion & Chunking)** | Preserve section headings and tags in `metadata` dictionary. | Enables metadata-filtered retrieval (e.g. searching only `"Financial Results"`). |
| **Person 3 (ColPali Visual Retrieval)** | Provide visual candidates with `chunk_id` (or `candidate_id`), `rank`, and `page_number`. | Enables seamless multi-modal RRF fusion using Person 2's canonical `fusion_engine.py`. |
| **Person 3 (BGE Reranker)** | Accept `list[RetrievalResult]` (aliased as `RetrievalCandidate`). | Candidate outputs contain `text` and `metadata` ready for joint cross-encoder scoring. |
| **Person 4 (CRAG Evaluator)** | Rely on `candidate.candidate_id`, `candidate.candidate_type`, and `candidate.retrieval_score`. | Property aliases in `schemas.py` allow direct consumption by `CRAGController.process_candidates()`. |
| **Person 5 (FastAPI Orchestrator)** | Support `retriever.retrieve(query, top_k, filters)`. | Implements the standardized Section 10.2 query interface for production serving. |

---

## 10. Deployment Environment Configuration (`.env`)

Add the following environment variables to `.env` (configured with sensible production defaults):

```bash
# -----------------------------------------------------------------------------
# Person 2: Dense & Sparse Text Retrieval Configuration
# -----------------------------------------------------------------------------

# Embedding Model for Dense Vector Search
BGE_MODEL_NAME=BAAI/bge-base-en-v1.5

# Device override ("cpu", "cuda", or leave blank for auto-detect)
RETRIEVER_DEVICE=

# Qdrant Vector Store Configuration:
# - Set to empty string "" for in-memory mode (:memory:)
# - Set to a folder path (e.g. "./qdrant_storage") for embedded disk persistence
# - Set to an HTTP URL (e.g. "http://localhost:6333") for remote Qdrant server
QDRANT_PATH=./qdrant_storage

# BM25 Inverted Index File Path for Disk Persistence
BM25_INDEX_PATH=./bm25_index.pkl

# Reciprocal Rank Fusion (RRF) Parameters
RRF_K=60
WEIGHT_DENSE=1.0
WEIGHT_SPARSE=1.0
WEIGHT_VISUAL=1.0

# Retrieval Candidate Limits
RETRIEVAL_DENSE_TOP_K=25
RETRIEVAL_SPARSE_TOP_K=25
RETRIEVAL_FINAL_TOP_K=15
```

---

## 11. Dependency Requirements

Person 2 dependencies are lightweight, production-grade, and free of heavy framework bloat:

```text
fastembed>=0.2.7          # Lightweight, fast BGE embedding generation without full PyTorch bloat
qdrant-client>=1.7.0      # Official Qdrant vector database client (in-memory, local, or remote)
rank-bm25>=0.2.2          # Industrial standard BM25Okapi inverted index implementation
pydantic>=2.0.0           # Universal data validation and contract enforcement
pytest>=8.0.0             # Automated unit and integration testing suite
```

---

## 12. Verification & Quickstart Runbook

To verify the entire Person 2 subsystem locally:

1. **Run Full Test Suite:**
   ```bash
   python -m pytest -v
   ```
   *(Expected: 16 passed)*

2. **Run Pipeline Integration Verification:**
   ```bash
   python verify_pipeline.py
   ```
   *(Expected: Ingestion, dense search, sparse search, and hybrid RRF all execute successfully)*

3. **Run Performance Benchmark:**
   ```bash
   python benchmark_retrieval.py
   ```
   *(Expected: 100% Hit@1, 100% Hit@3, 1.0 MRR, sub-30ms latency)*
