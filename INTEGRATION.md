# AMCRAG Integration Guide: Consuming Document Processing Outputs

> **Author:** Person 1 (Document Processing and Knowledge Base Preparation)  
> **Project:** AMCRAG (Adaptive Multimodal Corrective RAG) — B.Tech Research Project  
> **Target Audience:** Person 2 (Dense/Sparse Indexing), Person 3 (ColPali Visual Indexing), Person 4 (Retrieval & CRAG Evaluation), and Person 5 (Orchestration & API)

---

## 1. Module Deliverables & Directory Layout

Person 1's module ingests PDF research papers and produces **four distinct types of artifacts**:

| Artifact Category | Primary File Location | Format | Intended Consumer |
|---|---|---|---|
| **1. Page-wise Extracted Text** | `data/processed/<name>_extracted.json` | JSON (UTF-8) | Person 4, Person 5 |
| **2. Text Chunks & Metadata** | `data/processed/<name>_chunks.json` | JSON (UTF-8) | **Person 2 (BGE & BM25)**, Person 4 |
| **3. Structured Elements** | Embedded in `_extracted.json` (`tables`, `headings`) | Markdown / JSON | Person 2, Person 4 |
| **4. Rendered Page Images** | `data/page_images/<name>/<name>_page_XXXX.png` | Lossless PNG (150 DPI) | **Person 3 (ColPali)** |
| **5. Visual Manifest** | `data/page_images/<name>/<name>_manifest.json` | JSON (UTF-8) | **Person 3 (ColPali)**, Person 4 |

```
AMC RAG/
├── data/
│   ├── uploads/                              # Place raw PDF papers here
│   │   └── sample.pdf
│   ├── processed/                            # JSON metadata and text outputs
│   │   ├── sample_extracted.json             # Page-by-page text & structure
│   │   └── sample_chunks.json                # Sliding-window chunks with page citations
│   └── page_images/                          # High-DPI rendered page images
│       └── sample/
│           ├── sample_page_0001.png
│           ├── sample_page_0002.png
│           ├── sample_page_0003.png
│           └── sample_manifest.json          # Index of images, DPI, and dimensions
```

---

## 2. Distinction Between Artifacts

To prevent confusion across team modules, each artifact serves a distinct purpose:
- **Extracted Text (`_extracted.json`):** Full, un-chunked text preserved exactly page-by-page. Contains 1-based `page_number`, `char_count`, `is_empty`, and optional Docling `headings`, `paragraphs`, and `tables`.
- **Text Chunks (`_chunks.json`):** Word-bounded sliding-window segments (`chunk_size=500`, `chunk_overlap=100`) designed specifically for embedding token budgets and lexical search engines.
- **Structured Elements (`tables`):** Clean markdown tables extracted from document pages (`| Col1 | Col2 |`), enabling tabular reasoning without layout destruction.
- **Rendered Images (`.png`):** High-fidelity visual rasterizations at 150 DPI. Used by multimodal vision encoders (ColPali) to "see" diagrams, formulas, charts, and font formatting.

---

## 3. Integration Guide by Teammate

### For Person 2: Dense & Sparse Indexing (BGE, BM25, Qdrant)

**Consume file:** `data/processed/<name>_chunks.json`

Each chunk in `chunks` provides all required vector payloads and metadata for dense and sparse indexing:

```python
import json
from pathlib import Path

# Load chunks produced by Person 1
chunks_file = Path("data/processed/sample_chunks.json")
with chunks_file.open("r", encoding="utf-8") as f:
    chunk_payload = json.load(f)

for chunk in chunk_payload["chunks"]:
    chunk_id = chunk["chunk_id"]            # Unique stable ID, e.g. "sample_chunk_0001"
    text_to_embed = chunk["chunk_text"]      # Clean text bounded to chunk_size

    # Qdrant payload metadata
    payload = {
        "chunk_id": chunk_id,
        "source_file": chunk["source_file"],
        "start_page": chunk["start_page"],
        "end_page": chunk["end_page"],
        "page_numbers": chunk["page_numbers"],
        "source_citation": chunk["source_citation"],   # e.g. "sample.pdf, Pages 1-2"
        "section_heading": chunk.get("section_heading"), # e.g. "Abstract"
        "char_count": chunk["char_count"],
        "word_count": chunk["word_count"],
    }

    # Person 2: Generate embedding and upsert to Qdrant / BM25
    # dense_vector = bge_embedder.encode(text_to_embed)
    # qdrant_client.upsert(collection_name="amcrag_dense", points=[...])
    # bm25_index.add_document(doc_id=chunk_id, text=text_to_embed)
```

---

### For Person 3: Multimodal Visual Retrieval (ColPali)

**Consume file:** `data/page_images/<name>/<name>_manifest.json`

Person 3 does **not** need to parse PDFs. Read the manifest to get pre-rendered image paths at 150 DPI:

```python
import json
from pathlib import Path
from PIL import Image

manifest_file = Path("data/page_images/sample/sample_manifest.json")
with manifest_file.open("r", encoding="utf-8") as f:
    manifest = json.load(f)

print(f"Indexing document: {manifest['source_file']} ({manifest['total_pages']} pages)")

for page in manifest["pages"]:
    page_number = page["page_number"]   # 1-based page index
    image_path = page["image_path"]       # Absolute path to rendered PNG
    width, height = page["width"], page["height"]
    dpi = page["dpi"]

    # Load image directly into PIL
    page_image = Image.open(image_path)

    # Person 3: Pass image into ColPali multi-vector vision encoder
    # visual_embedding = colpali_model.process_images([page_image])
    # qdrant_client.upsert_visual(page_number=page_number, embedding=visual_embedding)
```

---

### For Person 4: Retrieval, Corrective Loop (CRAG) & Final Citations

**Consume files:** `data/processed/<name>_chunks.json` and `data/page_images/<name>/<name>_manifest.json`

Person 4 uses chunk metadata to attribute facts to exact page numbers in final answers, and uses page images for visual cross-verification:

```python
# Formatting verified citations in LLM responses:
def format_rag_citation(chunk_record: dict) -> str:
    """Format citation tag for final synthesized answer."""
    return f"[{chunk_record['source_citation']}]"
    # Example output: "[sample.pdf, Page 1]" or "[sample.pdf, Pages 1-2]"
```

---

### For Person 5: Orchestration & End-to-End Execution

Person 5 can trigger Person 1's pipeline via command line or Python functions:

#### Programmatic Python Pipeline:
```python
from pathlib import Path
from extract_pdf import extract_page_text, save_json_output
from chunk_text import chunk_extracted_document, save_chunk_output
from render_pdf_pages import render_pdf_pages

pdf_path = Path("data/uploads/research_paper.pdf")

# 1. Extract text page-by-page
extraction = extract_page_text(pdf_path)
save_json_output(extraction, Path("data/processed/research_paper_extracted.json"), overwrite=True)

# 2. Chunk text with page provenance
chunks = chunk_extracted_document(extraction, chunk_size=500, chunk_overlap=100)
save_chunk_output(chunks, Path("data/processed/research_paper_chunks.json"), overwrite=True)

# 3. Render page images for ColPali
manifest = render_pdf_pages(pdf_path, dpi=150, overwrite=True)
print(f"Rendered {manifest['total_rendered_images']} images to {manifest['output_directory']}")
```

---

## 4. Output Schemas with Realistic Examples

### A. Extraction Schema (`data/processed/sample_extracted.json`)
```json
{
  "source_file": "sample.pdf",
  "total_pages": 3,
  "empty_pages": [3],
  "has_empty_pages": true,
  "backend_used": "pymupdf",
  "fallback_occurred": false,
  "fallback_reason": null,
  "tables": [],
  "pages": [
    {
      "page_number": 1,
      "text": "Adaptive Multimodal Corrective RAG (AMCRAG)\nAbstract: Large Language Models frequently suffer from hallucinations when reasoning over complex documents. In this paper, we propose AMCRAG...",
      "char_count": 312,
      "is_empty": false,
      "headings": [
        "Adaptive Multimodal Corrective RAG (AMCRAG)"
      ],
      "paragraphs": [
        "Abstract: Large Language Models frequently suffer from hallucinations..."
      ],
      "tables": []
    },
    {
      "page_number": 3,
      "text": "",
      "char_count": 0,
      "is_empty": true,
      "headings": [],
      "paragraphs": [],
      "tables": []
    }
  ]
}
```

### B. Chunks Schema (`data/processed/sample_chunks.json`)
```json
{
  "source_file": "sample.pdf",
  "total_pages": 3,
  "chunk_size": 500,
  "chunk_overlap": 100,
  "total_chunks": 2,
  "chunks": [
    {
      "chunk_id": "sample_chunk_0001",
      "chunk_index": 0,
      "chunk_text": "Adaptive Multimodal Corrective RAG (AMCRAG) Abstract: Large Language Models frequently suffer from hallucinations when reasoning over complex documents. In this paper, we propose AMCRAG, combining dense semantic search, sparse lexical retrieval, and ColPali visual embeddings with a corrective verification loop. Section 2: Document Ingestion Pipeline Person 1 is responsible for Document Processing and Knowledge Base Preparation. The module extracts page-wise text using PyMuPDF, prepares page",
      "source_file": "sample.pdf",
      "start_page": 1,
      "end_page": 2,
      "page_numbers": [1, 2],
      "source_citation": "sample.pdf, Pages 1-2",
      "section_heading": "Adaptive Multimodal Corrective RAG (AMCRAG)",
      "char_count": 495,
      "word_count": 65
    }
  ]
}
```

### C. Visual Manifest Schema (`data/page_images/sample/sample_manifest.json`)
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
    }
  ]
}
```

---

## 5. Known Limitations & OCR Requirements

1. **Scanned / Image-Only PDFs:**
   - When a research paper contains scanned raster images without a digital text stream, PyMuPDF extracts 0 characters.
   - **Behavior:** The module flags `is_empty: true` and includes the page in `empty_pages`.
   - **Important boundary:** The module **does not run OCR**. Page rendering will still produce high-DPI images for Person 3's ColPali module, but full-text dense/sparse indexing on scanned PDFs requires an external OCR engine (such as Tesseract or Docling OCR).
2. **Encrypted / Password-Protected PDFs:**
   - Raises a descriptive `ValueError` prompting the user to decrypt the file.
3. **Complex Formulas & Vector Graphics:**
   - Extracted text serializes equations as plain Unicode/ASCII symbols.
   - For mathematical formula reasoning, downstream retrieval should rely on **Person 3's ColPali visual embeddings** of the rendered page images rather than raw text chunks.

---

## 6. Execution Commands

### Installation
```bash
pip install -r requirements.txt
```

### Automated Tests (All 42 Tests)
```bash
pytest -v
```

### Process Any Document (Complete Ingestion Flow)
```bash
# 1. Extract text (PyMuPDF)
python extract_pdf.py data/sample.pdf --overwrite

# 2. Extract structured elements with Docling (optional)
python extract_pdf.py data/sample.pdf --backend auto --overwrite

# 3. Generate chunks with citation metadata
python chunk_text.py data/processed/sample_extracted.json --chunk-size 500 --chunk-overlap 100 --overwrite

# 4. Render high-DPI page images for ColPali
python render_pdf_pages.py data/sample.pdf --dpi 150 --overwrite
```
