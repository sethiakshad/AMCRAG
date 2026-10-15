# AMCRAG Person 4: CRAG Evaluator & Corrective Retrieval
## Comprehensive Report & Integration Guide

**Module:** Person 4 — CRAG (Corrective Retrieval-Augmented Generation)  
**Author:** Meghraj (`meghraj-crag`)  
**Status:** ✅ Fully Implemented, Validated, and Tested (16/16 tests pass)  
**Target Audience:** Person 3 (Retrieval), Person 5 (FastAPI & Generation), Person 1 & 2 (Ingestion & Indexing)

---

## 1. Executive Summary & Architecture Role

Person 4 acts as the **runtime evidence quality gatekeeper** between Person 3's hybrid retrieval/reranker and Person 5's context builder/generation orchestrator.

```
                   [ User Query ]
                         │
                         ▼
          [ Person 5: FastAPI Orchestrator ]
                         │  (active_query, attempt_number)
                         ▼
          [ Person 3: Hybrid Retrieval & Reranker ]
                         │  list[RetrievalCandidate]
                         ▼
        [ Person 4: CRAGController.process_candidates() ]
                         │
        ┌────────────────┼────────────────┐
        │                │                │
needs_correction=True    │      insufficient_evidence=True
        │                │                │
        ▼                ▼                ▼
[ Retry Person 3 with   [ can_proceed=True ]  [ Abort Generation ]
  reformulated_query ]           │            (Prevents Hallucination)
                                 ▼
                     [ Person 5: Context Builder ]
                                 │
                                 ▼
                     [ LLM Generation (Gemini) ]
```

---

## 2. Person 4 Implementation Overview

All components are implemented under [`backend/app/crag/`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/crag/) and [`backend/app/schemas/`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/schemas/):

| Component | File | Responsibilities |
|---|---|---|
| **Retrieval Candidate Contract** | [`retrieval.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/schemas/retrieval.py) | Unified schema for text chunks and visual page candidates with fallback evaluable content. |
| **CRAG Decision Contract** | [`crag.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/schemas/crag.py) | `CandidateEvaluation`, `EvidenceDecision`, and `CRAGResult` with `needs_correction` property. |
| **Decision Engine** | [`decisions.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/crag/decisions.py) | Dynamic thresholds ($\delta_{upper}=0.65, \delta_{lower}=0.30$), policies (`retry_once`, `accept_with_qualification`, `strict_correction`), noise filtering. |
| **Query Reformulator** | [`correction.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/crag/correction.py) | Conversational prefix stripping, visual intent detection, query expansion, and **loop/cycle avoidance**. |
| **Evaluator Engines** | [`evaluator.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/crag/evaluator.py) | `T5CRAGEvaluator` (fine-tuned `Mindie/CRAG-Evaluator` with adaptive calibration) + `HeuristicCRAGEvaluator` (offline fallback). |
| **CRAG Controller** | [`controller.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/crag/controller.py) | Unified pipeline coordinator: Candidate Evaluation $\rightarrow$ Decision $\rightarrow$ Refinement / Reformulation. |
| **Unit Tests (16/16 Pass)** | [`test_crag.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/tests/crag/test_crag.py) | Comprehensive test coverage across all schemas, decisions, reformulations, controller, and evaluators. |
| **Benchmark Suite** | [`crag_benchmark.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/evaluation/crag_benchmark.py) | 5 retrieval scenarios measuring recovery rate, hallucination prevention, and latency. |

---

## 3. Real T5-Large Checkpoint Validation Findings

We loaded and validated the actual `Mindie/CRAG-Evaluator` checkpoint on CPU. Key discoveries:

| Property | Value | Notes |
|---|---|---|
| **Base Model** | `google-t5/t5-large` | ~770M parameters |
| **Architecture** | `T5ForSequenceClassification` | Sequence classification / regression head |
| **Problem Type** | `regression` (`num_labels = 1`) | Outputs continuous regression score |
| **Input Format** | `f"{query} [SEP] {document}"` | Delimited sequence format specified by author |
| **Target Scale** | $[-1.0, +1.0]$ | $-1.0 = \text{no relevance}$, $+1.0 = \text{high relevance}$ |
| **CPU Latency** | ~970ms – 1100ms per passage | Evaluating 5 chunks takes ~5.5s on CPU |

### Adaptive Batch Calibration
Because the checkpoint was trained on NQ hard negatives with MSE loss, raw scores are compressed near $-1.0$ (e.g., relevant = $-0.9625$, distractor = $-1.0158$).  
We implemented **adaptive batch calibration** in [`evaluator.py`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/crag/evaluator.py): across a retrieved set, scores are normalized across $[0.15, 0.90]$, allowing the standard decision thresholds ($0.65$ / $0.30$) to work accurately out-of-the-box.

---

## 4. Benchmark & Test Verification Results

### Unit Tests
```
python -m pytest backend/tests/crag/test_crag.py -v
============================= 16 passed in 0.22s =============================
```

### Benchmark Summary ([`crag_benchmark_report.json`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/evaluation/reports/crag_benchmark_report.json))
* **Scenarios evaluated:** 5 diverse query/evidence types (prose, visual, ambiguous, unrecoverable).
* **Recovery Success Rate:** **66.67%** (poor retrievals successfully recovered after query reformulation).
* **Hallucination Prevention Rate:** **100%** (unrecoverable queries correctly flagged with `insufficient_evidence=True` instead of hallucinating).
* **Heuristic Evaluation Latency:** **0.2 ms**.

---

## 5. Interface Contract for Person 3 (Retrieval & Reranking)

### Input Contract: `RetrievalCandidate`
Person 3 must return retrieved and reranked passages as a `list[RetrievalCandidate]`:

```python
from app.schemas.retrieval import RetrievalCandidate

candidate = RetrievalCandidate(
    candidate_id="chunk_102",                      # Unique ID
    document_id="annual_report_2025",              # Parent document ID
    source_filename="annual_report_2025.pdf",
    page_start=12,                                 # 1-indexed page number
    page_end=12,
    candidate_type="text_chunk",                   # "text_chunk" or "visual_page"
    text="Net profit increased by 14%...",         # Required for text_chunk
    page_reference="artifacts/pages/doc_p12.png",  # Required for visual_page
    retrieval_method="dense",                      # "dense" | "bm25" | "colpali" | "rrf"
    retrieval_rank=1,                              # 1-indexed rank from reranker
    retrieval_score=0.88,                          # Reranker / retriever score
    metadata={"section": "Financial Results"}      # Extra metadata
)
```

#### Multimodal / Visual Page Rule:
If `candidate_type="visual_page"` and `text=None`:
* Person 4's `candidate.get_evaluable_content()` automatically falls back to `metadata["caption"]`, `metadata["description"]`, or `metadata["title"]`.
* **Person 3 / Person 1 must ensure:** visual pages include at least one descriptive metadata field.

### Output Contract: Query Reformulation Loop
When evidence is judged inadequate, Person 4 emits `result.reformulated_query`:
* Conversational filler is stripped (`"can you tell me"`, `"what is"`, etc.).
* Visual keywords (`figure`, `table`, `chart`) are reinforced.
* **Guaranteed cycle avoidance:** Person 4 will never emit a query that was already executed in the current session.

---

## 6. Interface Contract for Person 5 (FastAPI & Context Builder)

### Controller Initialization & Call
```python
from app.crag import CRAGController

# Initialize once at FastAPI startup (loads settings from .env)
crag_controller = CRAGController()

# During request execution:
crag_result = crag_controller.process_candidates(
    query=active_query,
    candidates=ranked_candidates,
    attempt_number=current_attempt  # 0 for initial retrieval, 1 for retry, etc.
)
```

### Person 5 Orchestrator State Machine (Copy-Paste Implementation)
```python
MAX_RETRIES = 2
attempt = 0
current_query = user_query

while attempt <= MAX_RETRIES:
    # 1. Person 3 retrieves candidates
    candidates = retriever.search_and_rerank(current_query)
    
    # 2. Person 4 evaluates candidates
    crag_result = crag_controller.process_candidates(
        query=current_query,
        candidates=candidates,
        attempt_number=attempt
    )
    
    # State A: Evidence is inadequate -> Retry retrieval with reformulated query
    if crag_result.needs_correction:
        current_query = crag_result.reformulated_query
        attempt += 1
        continue
        
    # State B: Retries exhausted and evidence remains inadequate -> Stop hallucination
    if crag_result.insufficient_evidence:
        return {
            "answer": "The provided documents do not contain sufficient evidence to answer your question.",
            "decision": crag_result.decision.label,
            "can_generate": False
        }
        
    # State C: Evidence is accepted -> Proceed to Generation
    if crag_result.can_proceed_to_generation:
        # Knowledge Refinement: noise candidates below lower threshold are filtered out
        final_context = context_builder.build(crag_result.accepted_candidates)
        answer = llm_generator.generate(user_query, final_context)
        return {
            "answer": answer,
            "decision": crag_result.decision.label,
            "accepted_candidates": crag_result.accepted_candidates
        }
```

### Knowledge Refinement for Context Builder
* `crag_result.accepted_candidates`: Only contains candidates meeting the relevance threshold (noise filtered).
* `crag_result.decision.candidate_evaluations[i].extracted_strips`: Extracted key sentence strips for fine-grained prompt injection.

---

## 7. Upstream Dependencies (Person 1 & Person 2)

| Teammate | Dependency / Expectation | Why it matters |
|---|---|---|
| **Person 1 (Ingestion & Chunking)** | Provide `metadata["caption"]` or `metadata["title"]` for visual pages | Allows the CRAG evaluator to score visual pages without runtime OCR |
| **Person 1 (Ingestion & Chunking)** | 1-indexed `page_start` and `source_filename` populated | Needed for citation verification and qualification messages |
| **Person 2 (Vector Indexing)** | Support search queries with multi-token keyword expansions | Person 4's reformulator strips conversational filler to create keyword-dense queries |

---

## 8. Deployment Environment Configuration (`.env`)

Template provided in [`.env.example`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/.env.example):

```bash
# Model checkpoint: Mindie/CRAG-Evaluator or local path
# Automatically falls back to HeuristicCRAGEvaluator if offline/no GPU
CRAG_EVALUATOR_PATH=Mindie/CRAG-Evaluator

# Device override ("cpu", "cuda", or leave blank for auto-detect)
CRAG_DEVICE=

# Decision thresholds
CRAG_UPPER_THRESHOLD=0.65
CRAG_LOWER_THRESHOLD=0.30

# Ambiguous policy: retry_once | accept_with_qualification | strict_correction
CRAG_AMBIGUOUS_POLICY=retry_once

# Maximum corrective retrieval attempts before stopping
CRAG_MAX_ATTEMPTS=2

# Query reformulation flags
CRAG_STRIP_PREFIXES=true
CRAG_DETECT_VISUAL=true
```

---

## 9. Dependency Requirements

Specified in [`backend/requirements.txt`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/requirements.txt):
* `pydantic>=2.0.0`
* `torch>=2.0.0` (optional for T5; heuristic runs without PyTorch)
* `transformers>=4.35.0` (optional for T5)
* `pytest>=8.0.0`
