# AMCRAG Integration Handoff Guide: Person 4 (CRAG Module)

**Author:** Person 4 (Meghraj — `meghraj-crag`)  
**Target Audience:** Person 3 (Retrieval & Reranking), Person 5 (FastAPI & Context Builder), and upstream teammates (Person 1 & 2)

---

## 1. Quick Architecture Overview

Person 4 acts as the **runtime evidence quality gatekeeper** sitting directly between Person 3's retrieval engine and Person 5's generation orchestrator:

```
[User Query]
      │
      ▼
[Person 5: FastAPI Orchestrator]
      │ (query, attempt_number)
      ▼
[Person 3: Hybrid Retrieval & Reranker]
      │ list[RetrievalCandidate]
      ▼
[Person 4: CRAGController.process_candidates()]
      │
      ├──> needs_correction == True  ──> Loop back to Person 3 with reformulated_query
      ├──> can_proceed_to_generation == True  ──> Pass accepted_candidates to Person 5 Context Builder
      └──> insufficient_evidence == True  ──> Person 5 aborts LLM generation (hallucination prevention)
```

---

## 2. Interface Contract for Person 3 (Retrieval & Reranking)

### Input Contract: `RetrievalCandidate`
Person 3 must return candidates conforming to [`app.schemas.retrieval.RetrievalCandidate`](file:///d:/a_code%20vs/btp/BTPsem5/AMCRAG/backend/app/schemas/retrieval.py#L12-L51):

```python
from app.schemas.retrieval import RetrievalCandidate

candidate = RetrievalCandidate(
    candidate_id="chunk_102",                      # Unique identifier
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
    metadata={"section": "Financial Results"}      # Optional extra context
)
```

#### Multimodal / Visual Pages Fallback:
If Person 3 returns a `visual_page` candidate where `text` is `None`:
* Person 4's `candidate.get_evaluable_content()` automatically falls back to reading `metadata["caption"]`, `metadata["description"]`, or `metadata["title"]`.
* **Requirement for Person 1 / Person 3:** Please ensure visual page candidates include at least a basic `caption` or `title` in `metadata`.

### Output Contract: Query Reformulation
When retrieval is inadequate, Person 4 reformulates the query:
* Strips conversational fillers (`"can you tell me"`, `"what is"`, etc.).
* Detects and reinforces visual keywords (`figure`, `table`, `chart`) for visual queries.
* **Guarantees cycle avoidance:** Never repeats a query within the same session.

---

## 3. Interface Contract for Person 5 (FastAPI & Context Builder)

### Calling Person 4 from FastAPI
```python
from app.crag import CRAGController

# Initialize once at app startup
crag_controller = CRAGController()

# Execute per user request
crag_result = crag_controller.process_candidates(
    query=active_query,
    candidates=ranked_candidates,
    attempt_number=current_attempt  # 0 for initial, 1 for retry, etc.
)
```

### Complete Orchestration State Machine
Person 5 should implement this exact dispatch loop:

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
        # Knowledge Refinement: noise chunks strictly below lower threshold are already filtered out
        final_context = context_builder.build(crag_result.accepted_candidates)
        answer = llm_generator.generate(user_query, final_context)
        return {
            "answer": answer,
            "decision": crag_result.decision.label,
            "accepted_candidates": crag_result.accepted_candidates
        }
```

---

## 4. Upstream Dependencies (Person 1 & 2)

| Teammate | Dependency / Expectation | Why it matters |
|---|---|---|
| **Person 1 (Ingestion & Chunking)** | Provide `metadata["caption"]` or `metadata["title"]` for visual pages | Allows the CRAG evaluator to score visual pages without runtime OCR |
| **Person 1 (Ingestion & Chunking)** | 1-indexed `page_start` and `source_filename` populated | Needed for citation verification and qualification messages |
| **Person 2 (Vector Indexing)** | Support search queries with multi-token keyword expansions | Person 4's reformulator strips conversational filler to create keyword-dense queries |

---

## 5. Environment Variables (`.env`)

Template provided in `.env.example`:

```bash
# Evaluator checkpoint (Mindie/CRAG-Evaluator or local path)
CRAG_EVALUATOR_PATH=Mindie/CRAG-Evaluator

# Device override ("cpu", "cuda", or leave blank for auto-detect)
CRAG_DEVICE=

# Confidence thresholds
CRAG_UPPER_THRESHOLD=0.65
CRAG_LOWER_THRESHOLD=0.30

# Ambiguous policy: retry_once | accept_with_qualification | strict_correction
CRAG_AMBIGUOUS_POLICY=retry_once

# Maximum corrective retrieval attempts
CRAG_MAX_ATTEMPTS=2
```
