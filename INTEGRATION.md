# AMCRAG Integration Guide: Consuming Document Processing Outputs

> **Author:** Person 1 (Document Processing and Knowledge Base Preparation)  
> **Project:** AMCRAG (Adaptive Multimodal Corrective RAG) — B.Tech Research Project  
> **Target Audience:** Person 2 (Dense & Sparse Hybrid Retrieval Subsystem), Person 3 (ColPali Visual Retrieval & Reranker), Person 4 (CRAG Evaluator & Citations), and Person 5 (FastAPI Orchestrator)

---

## 1. Executive Architecture Role & Subsystem Interfaces

Person 1 is responsible for **Document Ingestion, Text Extraction, Layout Normalization, Chunking, and Visual Page Rendering**. It serves as the upstream foundation for the entire AMCRAG pipeline:

```
[ PDF Upload / Ingestion ]
            │
            ▼
┌───────────────────────────────────────────┐
│ Person 1: Document Processing             │
│ • PyMuPDF / IBM Docling Text Extraction   │
│ • Sentence-Bounded Sliding Window Chunker │
│ • 150 DPI Visual Page Rasterizer          │
└─────┬───────────────────────────────┬─────┘
      │                               │
      │ list[DocumentChunk]           │ Rendered Images (.png)
      ▼ (Plug 1)                      ▼ & Manifest (.json)
┌──────────────────────────┐    ┌──────────────────────────┐
│ Person 2: Hybrid Text    │    │ Person 3: ColPali        │
│ Retriever                │    │ Visual Retrieval         │
│ • Qdrant Dense (BGE-base)│    │ • Multi-vector embeddings│
│ • BM25Okapi Sparse Index │    │ • Layout/Chart Retrieval │
└─────────────┬────────────┘    └────────────┬─────────────┘
              │                              │
              │ dense & sparse candidates    │ visual candidates
              └──────────────┬───────────────┘
                             ▼
              ┌─────────────────────────────┐
              │ Person 2: RRF Fusion Engine │
              │ • Reciprocal Rank (k=60)    │
              └──────────────┬──────────────┘
                             ▼ list[RetrievalResult / RetrievalCandidate]
              ┌─────────────────────────────┐
              │ Person 4: CRAG Evaluator    │
              │ • Mindie/T5-Large Quality   │
              │ • Source-Page Citations     │
              └─────────────────────────────┘
```

---

## 2. Universal Schema Contracts (`schemas.py`)

All AMCRAG modules share common Pydantic v2 schemas defined in [`schemas.py`](file:///e:/AMC%20RAG/schemas.py) and [`app/schemas/`](file:///e:/AMC%20RAG/app/schemas/):

| Schema Name | Primary Location | Consumed By | Purpose |
|---|---|---|---|
| `DocumentChunk` | [`schemas.py`](file:///e:/AMC%20RAG/schemas.py) / [`app.schemas`](file:///e:/AMC%20RAG/app/schemas/chunk.py) | **Person 2 (Plug 1)** | Universal text chunk contract with 1-indexed page provenance, text, and layout metadata. |
| `ChunkMetadata` | [`schemas.py`](file:///e:/AMC%20RAG/schemas.py) / [`app.schemas`](file:///e:/AMC%20RAG/app/schemas/chunk.py) | Person 2, Person 4 | Preserves section headings, citations, character counts, and bounding boxes. |
| `PageRenderInfo` | [`schemas.py`](file:///e:/AMC%20RAG/schemas.py) / [`app.schemas`](file:///e:/AMC%20RAG/app/schemas/document.py) | **Person 3 (ColPali)**, Person 4 | Rendered page image paths, resolutions, DPI, and fallback captions/titles. |
| `ProcessedDocumentOutput` | [`schemas.py`](file:///e:/AMC%20RAG/schemas.py) / [`app.schemas`](file:///e:/AMC%20RAG/app/schemas/chunk.py) | Person 5 (FastAPI) | Complete structured JSON ledger emitted at `data/processed/{doc_id}.json`. |
| `ScoredCandidate` | [`schemas.py`](file:///e:/AMC%20RAG/schemas.py) | Person 2, Person 3 | Single-channel scored passage candidate representation. |
| `RetrievalResult` | [`schemas.py`](file:///e:/AMC%20RAG/schemas.py) | Person 3, Person 4, Person 5 | RRF-fused candidate aliased as `RetrievalCandidate` (Section 10.1). |

---

## 3. Teammate Integration Guide

### A. For Person 2: Dense & Sparse Text Retrieval Subsystem (Om Khapekar)

Person 2 indexes text chunks ingested by Person 1 into Qdrant (`BAAI/bge-base-en-v1.5`) and BM25Okapi.

#### Plug 1: Ingestion via `index_knowledge_base()`
Person 1 chunks can be passed directly to Person 2's retriever:

```python
from schemas import DocumentChunk
from app.services.pipeline import DocumentProcessingPipeline
from hybrid_retriever import HybridTextRetriever

# 1. Ingest and chunk PDF document via Person 1
pipeline = DocumentProcessingPipeline()
output = pipeline.process_file("data/uploads/annual_report_2025.pdf")

# 2. Hand off chunks directly to Person 2
retriever = HybridTextRetriever()
retriever.index_knowledge_base(chunks=output.chunks)
# or using helper method:
# retriever.index_knowledge_base(chunks=output.to_retriever_chunks())
```

#### Reading Chunks from Disk (`data/processed/<name>_chunks.json`):
```python
import json
from pathlib import Path
from schemas import DocumentChunk
from hybrid_retriever import HybridTextRetriever

with open("data/processed/sample_chunks.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Deserialize directly into Person 2 DocumentChunk instances
chunks = [DocumentChunk(**item) for item in data["chunks"]]

retriever = HybridTextRetriever()
retriever.index_knowledge_base(chunks=chunks)
```

#### Guarantees Provided by Person 1 to Person 2:
1. **Deterministic Fields:** `chunk.chunk_id`, `chunk.document_id`, `chunk.page_number` (1-indexed), `chunk.text`, `chunk.source_filename`, `chunk.page_start`, and `chunk.page_end` are always populated.
2. **Deterministic UUIDv5 Compatibility:** `chunk_id` strings (e.g. `doc_abc123_c0001` or `sample_chunk_0001`) are stable across pipeline reruns.
3. **Payload Preservation:** `chunk.metadata` preserves `"section"`, `"headings"`, `"table"`, `"source_citation"`, and `"char_count"` verbatim.
4. **Backward-Compatibility:** `chunk.chunk_text` and `chunk.document_name` remain accessible as properties.

---

### B. For Person 3: Multimodal Visual Retrieval & Reranker (ColPali)

**Consume manifest:** `data/page_images/<stem>/<stem>_manifest.json`

Person 3 does **not** need to open or parse PDFs. Person 1 pre-renders all pages at 150 DPI with memory-efficient pixmap streaming:

```python
import json
from pathlib import Path
from PIL import Image

manifest_path = Path("data/page_images/sample/sample_manifest.json")
with manifest_path.open("r", encoding="utf-8") as f:
    manifest = json.load(f)

print(f"Document: {manifest['source_filename']} ({manifest['total_pages']} pages)")

for page_info in manifest["pages"]:
    page_num = page_info["page_number"]    # 1-indexed page number
    img_path = page_info["image_path"]      # Absolute path to PNG
    width, height = page_info["width"], page_info["height"]
    title = page_info.get("title")          # Descriptive fallback for CRAG
    caption = page_info.get("caption")

    # Load PIL image for ColPali vision encoder
    page_image = Image.open(img_path)

    # Person 3: Generate visual multi-vector embedding and upsert to Qdrant visual collection
    # visual_embedding = colpali_model.process_images([page_image])
    # qdrant_client.upsert(collection_name="colpali_pages", points=[...])
```

---

### C. For Person 4: Adaptive Corrective Retrieval (CRAG) & Citations

Person 4's `CRAGController` evaluates retrieved candidates before answer generation:

1. **Page Provenance for Answers:**
   Every chunk carries `source_citation` (e.g. `report.pdf, Pages 2-3`), enabling LLM prompts to cite the exact source pages.
2. **Visual Candidate Fallback Content:**
   In accordance with Section 7 of Person 4's integration guide, visual pages without OCR text expose `title` and `caption` via `result.get_evaluable_content()`, enabling T5-Large to score visual pages without runtime OCR.
3. **Property Aliases Supported:**
   - `candidate.candidate_id` $\rightarrow$ maps to `chunk_id`
   - `candidate.candidate_type` $\rightarrow$ `"visual_page"` or `"text_chunk"`
   - `candidate.retrieval_score` $\rightarrow$ maps to `fused_score`

---

### D. For Person 5: FastAPI Orchestrator

Initialize the ingestion and retrieval subsystems during FastAPI startup:

```python
from fastapi import FastAPI, UploadFile, File
from pathlib import Path
import shutil

from app.services.pipeline import DocumentProcessingPipeline
from app.services.retrieval_bridge import index_document_chunks
from hybrid_retriever import HybridTextRetriever

app = FastAPI(title="AMCRAG API")

pipeline = DocumentProcessingPipeline()
retriever = HybridTextRetriever()

@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    # Save upload
    dest = Path("data/uploads") / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 1. Person 1: Extract, Chunk, Render
    output = pipeline.process_file(dest)

    # 2. Person 2: Index into Qdrant & BM25
    indexed_count = retriever.index_knowledge_base(chunks=output.chunks)

    return {
        "status": output.status,
        "document_id": output.document_id,
        "total_chunks": output.total_chunks,
        "indexed_chunks": indexed_count,
        "is_scanned": output.is_scanned,
        "ocr_needed": output.ocr_needed,
        "rendered_pages": len(output.rendered_pages),
    }
```

---

## 4. Realistic Output Schema Examples

### A. Chunks Output (`data/processed/sample_chunks.json`)
```json
{
  "source_file": "sample.pdf",
  "source_filename": "sample.pdf",
  "total_pages": 3,
  "chunk_size": 500,
  "chunk_overlap": 100,
  "total_chunks": 2,
  "chunks": [
    {
      "chunk_id": "sample_chunk_0001",
      "chunk_index": 0,
      "document_id": "sample",
      "document_name": "sample.pdf",
      "source_file": "sample.pdf",
      "source_filename": "sample.pdf",
      "page_number": 1,
      "start_page": 1,
      "end_page": 2,
      "page_start": 1,
      "page_end": 2,
      "page_numbers": [1, 2],
      "text": "Adaptive Multimodal Corrective RAG (AMCRAG) Abstract: Large Language Models frequently suffer from hallucinations when reasoning over complex documents...",
      "chunk_text": "Adaptive Multimodal Corrective RAG (AMCRAG) Abstract: Large Language Models frequently suffer from hallucinations when reasoning over complex documents...",
      "source_citation": "sample.pdf, Pages 1-2",
      "section_heading": "Adaptive Multimodal Corrective RAG (AMCRAG)",
      "char_count": 495,
      "word_count": 65,
      "metadata": {
        "section": "Adaptive Multimodal Corrective RAG (AMCRAG)",
        "headings": ["Adaptive Multimodal Corrective RAG (AMCRAG)"],
        "section_heading": "Adaptive Multimodal Corrective RAG (AMCRAG)",
        "document_id": "sample",
        "document_name": "sample.pdf",
        "source_filename": "sample.pdf",
        "page_number": 1,
        "page_start": 1,
        "page_end": 2,
        "page_numbers": [1, 2],
        "source_citation": "sample.pdf, Pages 1-2",
        "char_count": 495,
        "word_count": 65,
        "table": false
      }
    }
  ]
}
```

### B. Visual Manifest Output (`data/page_images/sample/sample_manifest.json`)
```json
{
  "source_file": "sample.pdf",
  "source_filename": "sample.pdf",
  "document_id": "sample",
  "total_pages": 3,
  "render_settings": {
    "dpi": 150,
    "image_format": "png"
  },
  "output_directory": "E:\\AMC RAG\\data\\page_images\\sample",
  "total_rendered_images": 3,
  "pages": [
    {
      "page_number": 1,
      "image_filename": "sample_page_0001.png",
      "image_path": "E:\\AMC RAG\\data\\page_images\\sample\\sample_page_0001.png",
      "width": 1240,
      "height": 1755,
      "dpi": 150,
      "title": "sample.pdf - Page 1",
      "caption": "Rendered visual representation of sample.pdf (Page 1)"
    }
  ]
}
```

---

## 5. Known Limitations & OCR Requirements

1. **Scanned Raster PDFs:**
   - Image-only scanned PDFs have 0 native digital characters.
   - **Behavior:** The module accurately flags `is_scanned: true`, `ocr_needed: true`, and `status: "warning_ocr_needed"`.
   - **OCR Requirement:** In accordance with module boundaries, Person 1 does not run OCR. Full-text indexing for scanned papers requires an upstream OCR preprocessor (e.g. Tesseract or Docling OCR).
2. **Mathematical Formulas:**
   - Complex LaTeX equations are serialized as Unicode characters. Downstream retrieval of visual formulas should rely on Person 3's ColPali visual embeddings.
3. **Encrypted PDFs:**
   - Encrypted PDFs raise an explicit `ValueError` requesting decryption prior to ingestion.

---

## 6. Commands to Run & Verify

### Install Dependencies:
```bash
pip install -r requirements.txt
```

### Run Test Suite (68 Tests, 100% Passing):
```bash
python -m pytest -v
```

### Process Sample PDF:
```bash
# Full pipeline CLI execution:
python -m app.cli --file data/sample.pdf

# Standalone scripts:
python extract_pdf.py data/sample.pdf --overwrite
python chunk_text.py data/sample.pdf --chunk-size 500 --chunk-overlap 100 --overwrite
python render_pdf_pages.py data/sample.pdf --dpi 150 --overwrite
```
