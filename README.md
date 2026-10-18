# AMCRAG - Document Processing & Knowledge Base Preparation

> **Module:** Person 1 — Document Processing and Knowledge Base Preparation  
> **Project:** AMCRAG (Adaptive Multimodal Corrective RAG)

---

## 1. Overview & Architecture

Person 1's module prepares clean, structured knowledge representations from input PDF research papers for downstream AMCRAG teammates:
- **Milestone 1 (`extract_pdf.py`):** Page-wise text extraction using PyMuPDF (`fitz`), preserving 1-based page order, detecting empty/whitespace pages without inventing text.
- **Milestone 2 (`chunk_text.py`):** Configurable sliding-window text chunking with overlap, preserving word boundaries, provenance, stable unique IDs, and start/end page numbers.
- **Milestone 3 (`docling_extractor.py`):** Optional structured document extraction using IBM Docling for headings, paragraphs, and tables, with automatic, transparent fallback to PyMuPDF.
- **Milestone 4 (`render_pdf_pages.py`):** High-resolution PDF page rendering into PNG images at configurable DPI with structured JSON manifests for downstream visual retrieval (ColPali).

All modules are completely decoupled, lightweight, and memory-efficient.

---

## 2. Setup & Installation

### Core Dependencies (Fast & Lightweight)
```bash
pip install -r requirements.txt
```
*(Installs `pymupdf>=1.24.0` and `pytest>=8.0.0`)*

### Optional: IBM Docling for Deep Layout Parsing
If you want to use the optional deep-learning structured extraction backend:
```bash
pip install docling
```
*(If Docling is not installed, the pipeline automatically falls back to PyMuPDF without failing).*

---

## 3. How to Run

### Milestone 1: PDF Text Extraction (`extract_pdf.py`)
```bash
# Default fast extraction
python extract_pdf.py data/sample.pdf

# Overwrite existing extracted output
python extract_pdf.py data/sample.pdf --overwrite
```
Outputs: `data/processed/<name>_extracted.json`

---

### Milestone 2: Text Chunking (`chunk_text.py`)
```bash
# Chunk directly from PDF
python chunk_text.py data/sample.pdf

# Custom chunk size and overlap
python chunk_text.py data/sample.pdf --chunk-size 300 --chunk-overlap 50

# Chunk an already extracted JSON file
python chunk_text.py data/processed/sample_extracted.json --overwrite
```
Outputs: `data/processed/<name>_chunks.json`

---

### Milestone 3: Structured Extraction with Fallback (`extract_pdf.py`)
```bash
# Automatic Docling with PyMuPDF fallback
python extract_pdf.py data/sample.pdf --backend auto --overwrite

# Strict Docling backend
python extract_pdf.py data/sample.pdf --backend docling
```

---

### Milestone 4: PDF Page Rendering (`render_pdf_pages.py`)
Render PDF pages into high-resolution images for visual retrieval:

```bash
# Render with default settings (150 DPI, PNG)
python render_pdf_pages.py data/sample.pdf

# Custom DPI and destination directory
python render_pdf_pages.py data/sample.pdf --dpi 200 --output-dir my_images/

# Overwrite existing rendered images and manifest
python render_pdf_pages.py data/sample.pdf --overwrite
```
Outputs: `data/page_images/<pdf_stem>/<pdf_stem>_page_0001.png` and `data/page_images/<pdf_stem>/<pdf_stem>_manifest.json`

---

## 4. How Teammate Consumes Rendered Images & Manifest

The visual retrieval teammate (Person 3) only needs to read the manifest JSON to access rendered images:

### Manifest Schema (`data/page_images/<pdf_stem>/<pdf_stem>_manifest.json`)
```json
{
  "source_file": "sample.pdf",
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
      "dpi": 150
    },
    {
      "page_number": 2,
      "image_filename": "sample_page_0002.png",
      "image_path": "E:\\AMC RAG\\data\\page_images\\sample\\sample_page_0002.png",
      "width": 1240,
      "height": 1755,
      "dpi": 150
    }
  ]
}
```

### Python Consumption Example (For Person 3 / ColPali Module)
```python
import json
from pathlib import Path
from PIL import Image

manifest_path = Path("data/page_images/sample/sample_manifest.json")
with manifest_path.open("r", encoding="utf-8") as f:
    manifest = json.load(f)

print(f"Document: {manifest['source_filename']}, Total pages: {manifest['total_pages']}")

# Iterate through rendered pages and feed into vision models
for page_info in manifest["pages"]:
    page_num = page_info["page_number"]
    image_path = page_info["image_path"]

    # Load image directly for embedding / visual indexing
    image = Image.open(image_path)
    print(f"Loaded Page {page_num}: {image.size} ({page_info['dpi']} DPI)")

    # Teammate's ColPali indexing logic goes here:
    # visual_embedding = colpali_model.process_image(image)
```

> **Note on Boundaries:**  
> - Image rendering produces clean raster representations of document pages. It **does not perform OCR**.  
> - Multi-vector ColPali indexing, embeddings, and retrieval are handled in Person 3's module.

---

## 5. Teammate Interoperability & Integration

Person 1 output conforms strictly to the cross-module contracts defined in `schemas.py`:

- **Person 2 (Qdrant & BM25 Text Retrieval):**
  Pass chunks directly to Person 2's `HybridTextRetriever`:
  ```python
  from schemas import DocumentChunk
  from hybrid_retriever import HybridTextRetriever
  from app.services.pipeline import DocumentProcessingPipeline

  pipeline = DocumentProcessingPipeline()
  output = pipeline.process_file("data/sample.pdf")

  retriever = HybridTextRetriever()
  retriever.index_knowledge_base(chunks=output.chunks)
  ```
- **Person 4 (Adaptive Retrieval & CRAG Evaluator):**
  Chunks preserve 1-indexed `page_start`, `page_end`, and `source_citation` for verified answer citations. Visual page records expose `title` and `caption` for evaluation without runtime OCR.
- **Person 5 (FastAPI Orchestrator):**
  Import `DocumentProcessingPipeline` or `index_document_chunks` for synchronous or background ingestion.

---

## 6. Automated Tests (68 Tests, 100% Passing)

Run the full automated test suite covering all modules, schemas, and teammate integration contracts:

```bash
# Run all 68 tests
python -m pytest -v

# Run Milestone 1 tests (15 extraction tests)
python -m pytest tests/test_extract_pdf.py -v

# Run Milestone 2 tests (11 chunking tests)
python -m pytest tests/test_chunk_text.py -v

# Run Milestone 3 tests (7 Docling normalization & fallback tests)
python -m pytest tests/test_docling_extractor.py -v

# Run Milestone 4 tests (9 page rendering tests)
python -m pytest tests/test_render_pdf_pages.py -v

# Run Central Schema & Teammate Integration tests
python -m pytest tests/test_schemas.py tests/test_person2_integration.py -v
```

