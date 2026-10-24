# 🖼️ Multimodal Retrieval & Reranking with ColPali — Plan for AMCRAG

> **Written in simple language for the whole team**  
> **Project:** AMCRAG (Adaptive Multimodal Corrective RAG)  
> **Feature:** Visual page retrieval + reranking using ColPali

---

## 📖 What is this about? (In plain words)

Imagine you have a PDF that has a **chart**, a **table**, and some **diagrams**. If someone asks a question about that chart, a normal text-based search will **fail** — because charts don't have text!

**ColPali** solves this by looking at the **entire PDF page as an image** and understanding it visually. Instead of converting the image to text (OCR), it asks: *"Does this page visually look relevant to the question?"*

So in AMCRAG, ColPali is our **"eyes"** — it finds pages that contain visual information our text system can't find.

---

## 🤔 What is ColPali? (Simply explained)

| Concept | Simple Explanation |
|---|---|
| **ColPali** | A vision-language model that converts PDF pages into "visual fingerprints" (embeddings) |
| **Page Embedding** | A list of numbers that describes what a page *looks* like visually |
| **Query Embedding** | A list of numbers that describes what the *question* means |
| **Similarity** | We compare these two lists of numbers — if they're close, the page is relevant |
| **Multi-vector** | Instead of 1 number per page, ColPali produces ~1000 small vectors (one per image patch), making it much smarter |

**ColPali Model:** `vidore/colpali-v1.2` (based on PaliGemma from Google)

---

## 🏗️ Where does ColPali fit in AMCRAG?

Here is the full AMCRAG pipeline with ColPali highlighted:

```
PDFs
  │
  ▼
[Person 1] Document Processing
  ├── Text Extraction (PyMuPDF/Docling)
  ├── Text Chunks ──────────────────────────────────────────────────────┐
  └── 🖼️ PDF Page Images (render_pdf_pages.py) ──────────────────────┐  │
                                                                      │  │
                                                                      ▼  ▼
                                                          ┌─────────────────────────┐
                                                          │  [Person 3 - YOU]       │
                                                          │  ColPali Visual Index   │  ← WE BUILD THIS
                                                          │  (Qdrant collection)    │
                                                          └───────────┬─────────────┘
                                                                      │
User Query                                                            │
  │                                                                   │
  ▼                                                                   │
[Person 4] Adaptive Retrieval Selector                                │
  ├── Dense Search (BGE + Qdrant) ─────────────────────────┐         │
  ├── Sparse Search (BM25) ────────────────────────────────┤         │
  └── 🖼️ Visual Search (ColPali) ──────────────────────────┤ ◄───────┘
                                                            │
                                                            ▼
                                                    RRF Fusion
                                                            │
                                                            ▼
                                              🔄 BGE Reranker ← ALSO ENHANCED
                                                            │
                                                            ▼
                                                  T5 CRAG Evaluator
                                                            │
                                                            ▼
                                                    Answer Generation
```

---

## 📦 What We Need to Build (The 5 Modules)

### Module 1: ColPali Model Wrapper (`colpali_model.py`)
**What it does:** Loads ColPali and converts images/text into embeddings.

```
Input:  A PDF page image (PNG file)
Output: A list of ~1024 vectors (multi-vector embedding)

Input:  A text query ("What does the graph show?")
Output: A list of vectors representing the question
```

### Module 2: ColPali Indexer (`colpali_indexer.py`)
**What it does:** Takes all page images from Person 1's manifest and stores their embeddings in Qdrant.

```
Input:  manifest.json from render_pdf_pages.py
Output: Qdrant collection called "colpali_pages" with all page embeddings
```

### Module 3: ColPali Retriever (`colpali_retriever.py`)
**What it does:** Given a query, finds the most visually relevant pages.

```
Input:  A user question ("Show me the accuracy comparison chart")
Output: Top-K pages ranked by visual similarity (as ScoredCandidate objects)
```

### Module 4: ColPali Reranker (`colpali_reranker.py`)
**What it does:** After RRF fusion gives us mixed text + visual results, reranks them specifically using ColPali's visual score.

```
Input:  Mixed list of text chunks + visual pages (from RRF)
Output: Reranked list where visual pages get properly scored by ColPali
```

### Module 5: Integration Glue (`retrieval_bridge.py` update)
**What it does:** Plugs ColPali retriever into the existing AMCRAG hybrid retrieval pipeline.

---

## 🗂️ Proposed File Structure

```
AMCRAG/
│
├── app/
│   ├── services/
│   │   ├── pipeline.py                  (existing - no change)
│   │   ├── retrieval_bridge.py          (MODIFY - add colpali path)
│   │   └── page_renderer.py             (existing - no change)
│   │
│   └── colpali/                         ← NEW FOLDER
│       ├── __init__.py
│       ├── colpali_model.py             ← Loads ColPali model
│       ├── colpali_indexer.py           ← Indexes pages into Qdrant
│       ├── colpali_retriever.py         ← Retrieves by visual query
│       └── colpali_reranker.py          ← Reranks with visual scores
│
├── tests/
│   └── test_colpali/                    ← NEW TEST FOLDER
│       ├── test_colpali_model.py
│       ├── test_colpali_indexer.py
│       └── test_colpali_retriever.py
│
└── COLPALI_MULTIMODAL_PLAN.md          ← THIS FILE
```

---

## 🔧 How Each Module Works (Step-by-Step)

### Step 1: Indexing Phase (Done once when a PDF is uploaded)

```
render_pdf_pages.py
     │
     ▼
sample_manifest.json   ← Person 1 already produces this!
     │
     ▼
colpali_indexer.py
     │
     ├── Read manifest → get list of image paths
     │
     ├── For each page image:
     │     ├── Load PNG image from disk
     │     ├── Pass to ColPali model → get multi-vector embedding
     │     └── Store in Qdrant with metadata:
     │           {page_number, source_file, image_path, ...}
     │
     └── Done! Qdrant now has all pages indexed visually.
```

### Step 2: Query Phase (Done for every user question)

```
User Question: "Show me the performance comparison table"
     │
     ▼
colpali_retriever.py
     │
     ├── Convert query text → query embedding (using ColPali's text encoder)
     │
     ├── Search Qdrant "colpali_pages" collection
     │     → MaxSim score (special multi-vector similarity)
     │
     └── Return top-K pages as ScoredCandidate(modality="visual_page")
     
     Output example:
     [
       ScoredCandidate(chunk_id="sample_page_3", score=0.92, page_number=3, modality="visual_page"),
       ScoredCandidate(chunk_id="sample_page_7", score=0.87, page_number=7, modality="visual_page"),
     ]
```

### Step 3: Fusion & Reranking

```
Dense Results:   [chunk_42, chunk_15, chunk_67, ...]    (text)
Sparse Results:  [chunk_15, chunk_42, chunk_89, ...]    (text)  
Visual Results:  [page_3,   page_7,   page_12, ...]     (visual) ← ColPali

         │
         ▼
    RRF Fusion
    (combines all 3 lists using rank positions)
         │
         ▼
    Combined list: [chunk_42, page_3, chunk_15, page_7, ...]
         │
         ▼
    BGE Reranker (text candidates)
    ColPali Reranker (visual candidates)  ← applies ColPali score
         │
         ▼
    Final top-K candidates → CRAG Evaluator
```

---

## 📐 The Scoring Math (Simplified)

### What is MaxSim?

ColPali doesn't just produce **1 number** per page. It produces **N vectors** (one per image patch — like puzzle pieces of the page).

For a query, it also produces M vectors.

**MaxSim score** = For each query vector, find the best matching page vector, then average them all.

```
Query vectors:   [q1, q2, q3, q4]
Page vectors:    [p1, p2, p3, ... p1024]

Score = average(
    max_similarity(q1, all_page_vectors),
    max_similarity(q2, all_page_vectors),
    max_similarity(q3, all_page_vectors),
    max_similarity(q4, all_page_vectors),
)
```

This is much smarter than a single-vector comparison because it matches specific *parts* of the query to specific *regions* of the page.

---

## 🗄️ Qdrant Collection Design

We will create a **new Qdrant collection** specifically for ColPali:

```
Collection Name: "colpali_pages"

Each point (document page):
  ├── id: "document_id_page_3"
  ├── vectors: [[v1, v2, ...], [v1, v2, ...], ...]  ← multi-vector (list of 128-dim vectors)
  └── payload:
        ├── page_number: 3
        ├── source_filename: "paper.pdf"
        ├── document_id: "doc_abc123"
        ├── image_path: "data/page_images/paper/paper_page_0003.png"
        └── modality: "visual_page"
```

> **Why a separate collection?**  
> The existing Qdrant collection uses single-vector BGE embeddings (768-dim).  
> ColPali needs multi-vector storage (N × 128 dim per page). Qdrant supports this  
> natively with `MultiVectorConfig`.

---

## ⚙️ Configuration Settings

Add these to `app/config.py`:

```python
# ColPali Settings
COLPALI_MODEL_NAME: str = "vidore/colpali-v1.2"
COLPALI_COLLECTION_NAME: str = "colpali_pages"
COLPALI_TOP_K: int = 5           # How many visual pages to retrieve
COLPALI_BATCH_SIZE: int = 4      # Images to process at once (memory control)
COLPALI_DEVICE: str = "cuda"     # "cuda" for GPU, "cpu" for CPU (slow)
COLPALI_ENABLED: bool = True     # Toggle visual retrieval on/off
```

---

## 🔗 How ColPali Connects to Existing Schemas

ColPali retrieval results must conform to the existing `ScoredCandidate` schema in `schemas.py`:

```python
# A ColPali result looks like this:
ScoredCandidate(
    chunk_id    = "paper_page_0003",       # unique page ID
    score       = 0.921,                   # MaxSim similarity score
    rank        = 1,                       # rank in visual results
    modality    = "visual_page",           # ← marks it as visual!
    document_id = "doc_abc123",
    page_number = 3,
    text        = "",                      # no text (it's visual)
    source_filename = "paper.pdf",
    metadata    = {
        "image_path": "data/page_images/paper/paper_page_0003.png",
        "colpali_score": 0.921,
    }
)
```

After RRF fusion, it becomes a `RetrievalResult` with `modality="visual_page"` — Person 4 already handles this!

---

## 📋 Implementation Milestones

### Milestone 5: ColPali Model Wrapper
**Goal:** Load ColPali model and run basic image + text embedding  
**Files:** `app/colpali/colpali_model.py`  
**Test:** Embed 1 image + 1 query, check score > 0  
**Estimated time:** 1-2 days  

### Milestone 6: ColPali Page Indexer  
**Goal:** Index all pages from a manifest into Qdrant  
**Files:** `app/colpali/colpali_indexer.py`  
**Test:** Index 3 pages, verify they appear in Qdrant  
**Estimated time:** 1-2 days  

### Milestone 7: ColPali Visual Retriever  
**Goal:** Given a query, return top-K visually relevant pages  
**Files:** `app/colpali/colpali_retriever.py`  
**Test:** Query "bar chart", verify page with chart ranks #1  
**Estimated time:** 1 day  

### Milestone 8: ColPali Reranker  
**Goal:** Rerank a mixed list (text + visual) using ColPali scores  
**Files:** `app/colpali/colpali_reranker.py`  
**Test:** Pass mixed list, verify visual pages are correctly scored  
**Estimated time:** 1 day  

### Milestone 9: Integration & Testing  
**Goal:** Plug ColPali into the hybrid retrieval bridge  
**Files:** `app/services/retrieval_bridge.py`  
**Test:** End-to-end query returns both text and visual results  
**Estimated time:** 1-2 days  

---

## 📦 New Dependencies

Add these to `requirements.txt`:

```txt
# ColPali - Visual Page Retrieval
colpali-engine>=0.3.0         # ColPali model and utilities
transformers>=4.40.0          # HuggingFace model loading
torch>=2.1.0                  # PyTorch backend
pillow>=10.0.0                # Image loading
qdrant-client>=1.9.0          # Already used, update if needed

# Optional: for faster inference
einops>=0.7.0
```

> **GPU Requirement:**  
> ColPali (`colpali-v1.2`) is based on PaliGemma (3B parameters).  
> It needs approximately 6GB VRAM for inference.  
> On CPU it will work but will be very slow (10-30 seconds per page).  
> For indexing large document sets, GPU is strongly recommended.

---

## 🤝 Team Responsibilities

| Person | Role | ColPali Task |
|---|---|---|
| **Person 1** | Document Processing | Already done: `render_pdf_pages.py` produces images + manifest |
| **Person 2** | Qdrant + BM25 | Help create `colpali_pages` Qdrant collection (multi-vector config) |
| **Person 3** | Visual Retrieval | **Build ColPali modules** (Milestones 5-8) |
| **Person 4** | Adaptive Retrieval + CRAG | Wire ColPali into retrieval selector; schemas already support `visual_page` |
| **Person 5** | FastAPI + Orchestration | Add ColPali indexing step to document upload endpoint |

---

## 🔄 Data Flow Summary (One-page cheat sheet)

```
PDF Upload
     │
     ├─ Person 1 → text chunks + page images + manifest.json
     │
     └─ Person 3 (ColPali):
           ├── READ manifest.json
           ├── LOAD each PNG image
           ├── EMBED with ColPali → multi-vector per page
           └── STORE in Qdrant "colpali_pages"

User Query
     │
     ├─ Person 2 → Dense (BGE) + Sparse (BM25) text results
     │
     ├─ Person 3 (ColPali) → Visual page results
     │
     └─ Person 4 → RRF Fusion → Rerank → CRAG → Answer
```

---

## 🚦 Decision Points

| Question | Decision |
|---|---|
| Use ColPali for all queries or only visual ones? | Use query classifier: if query mentions "chart", "figure", "table", "graph", "image" → enable ColPali |
| How many visual results to retrieve? | Top-5 (configurable via `COLPALI_TOP_K`) |
| What if GPU is unavailable? | Graceful fallback: skip ColPali, return only text results |
| When to re-index ColPali? | On every new document upload (same trigger as BGE indexing) |
| Image resolution for ColPali? | Use existing 150 DPI from Person 1; 300 DPI for higher accuracy if needed |

---

## ✅ Definition of Done

- [ ] `colpali_model.py` — loads model, embeds images and queries
- [ ] `colpali_indexer.py` — indexes all pages from manifest into Qdrant
- [ ] `colpali_retriever.py` — retrieves top-K pages for a query
- [ ] `colpali_reranker.py` — reranks using visual MaxSim scores
- [ ] `retrieval_bridge.py` updated — ColPali results flow into RRF
- [ ] All ColPali results use `ScoredCandidate` with `modality="visual_page"`
- [ ] New Qdrant collection `colpali_pages` created with multi-vector config
- [ ] Tests: 10+ test cases covering indexing, retrieval, schema compliance
- [ ] Graceful fallback when `COLPALI_ENABLED=False` or GPU unavailable
- [ ] Configuration exposed in `app/config.py`

---

## 📚 Key References

| Resource | Link |
|---|---|
| ColPali Paper | arxiv.org/abs/2407.01449 |
| ColPali Engine (Python package) | github.com/illuin-tech/colpali |
| vidore/colpali-v1.2 Model | huggingface.co/vidore/colpali-v1.2 |
| Qdrant Multi-vector Docs | qdrant.tech/documentation/concepts/vectors/#multivectors |
| AMCRAG Central Docs | `AMCRAG_Central_Project_Documentation.md` |

---

*Last updated: October 2026 | AMCRAG Team | Person 3 owns implementation of this plan.*
