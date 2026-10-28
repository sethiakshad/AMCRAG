# Visual Orchestrator — Ollama Cloud Gemma 4 Vision

An isolated experimental module that replicates the multimodal visual retrieval, indexing, and reranking capabilities of **ColPali** using **Ollama Cloud's Gemma 4 Vision** (`gemma4:31b`).

---

## Architecture Overview

```
                      Rendered PDF Pages (150 DPI PNG)
                                     │
                                     ▼
                ┌────────────────────────────────────────┐
                │        OllamaVisualClient              │
                │  - Uses OLLAMA_VISUAL_API_KEY          │
                │  - Connects to https://ollama.com      │
                │  - Multimodal Vision: gemma4:31b       │
                └───────────────────┬────────────────────┘
                                    │
                                    ▼
                ┌────────────────────────────────────────┐
                │        GemmaVisualModel                │
                │  - embed_image() -> Patch Vectors      │
                │  - embed_query() -> Token Vectors      │
                │  - score()       -> Late-Action MaxSim │
                └───────────────────┬────────────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│     GemmaVisualIndexer        │               │     GemmaVisualRetriever      │
│ - Indexes into Qdrant         │               │ - Late-Interaction MaxSim     │
│ - Collection:                 │               │ - Emits: ScoredCandidate &    │
│   'gemma_visual_pages'        │               │   RetrievalCandidate          │
└───────────────────────────────┘               └───────────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │  GemmaVisualReranker  │
                        │ - Strategy:           │
                        │   visual_only / blend │
                        └───────────────────────┘
```

---

## Configuration (`.env`)

Add the following to your `.env` file:

```ini
# Ollama Cloud API Key for Gemma 4 Visual Processing
OLLAMA_VISUAL_API_KEY="your_api_key_here"
OLLAMA_VISUAL_MODEL="gemma4:31b"
OLLAMA_VISUAL_BASE_URL="https://ollama.com"
```

---

## Quick Usage Example

```python
from app.visual_orchestrator import GemmaVisualBridge

# Initialize the bridge
bridge = GemmaVisualBridge()

# 1. Index pages
count = bridge.index_pages(
    rendered_pages=rendered_pages,
    document_id="doc_123",
    source_filename="sample.pdf"
)

# 2. Retrieve visual candidates
results = bridge.retrieve(
    query="Show me the revenue bar chart",
    top_k=5
)

# 3. Rerank mixed candidate lists
reranked = bridge.rerank(
    query="Show me the revenue bar chart",
    candidates=results,
    strategy="visual_only"
)
```

---

## Interface Parity with ColPali

| Feature | ColPali (`app/colpali/`) | Visual Orchestrator (`app/visual_orchestrator/`) |
| :--- | :--- | :--- |
| **Model** | Local `vidore/colpali-v1.2` (~6.4 GB) | Cloud `gemma4:31b` via Ollama Cloud API |
| **Indexing Method** | `ColPaliIndexer.index_rendered_pages()` | `GemmaVisualIndexer.index_rendered_pages()` |
| **Retrieval Method** | `ColPaliRetriever.retrieve()` | `GemmaVisualRetriever.retrieve()` |
| **Reranking Method** | `ColPaliReranker.rerank()` | `GemmaVisualReranker.rerank()` |
| **High-level Facade** | `ColPaliVisualBridge` | `GemmaVisualBridge` |
| **Output Schema** | `ScoredCandidate` / `RetrievalCandidate` | `ScoredCandidate` / `RetrievalCandidate` |
| **Memory Footprint** | ~6-8 GB VRAM / RAM | Minimal (runs on cloud API) |
