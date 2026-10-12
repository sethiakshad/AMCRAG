# AMCRAG - Document Processing & Knowledge Base Preparation

> **Module:** Person 1 — Document Processing and Knowledge Base Preparation  
> **Project:** AMCRAG (Adaptive Multimodal Corrective RAG)

---

## 1. Overview & Architecture

Person 1's module prepares clean, structured knowledge representations from input PDF research papers for downstream AMCRAG teammates:
- **Milestone 1 (`extract_pdf.py`):** Page-wise text extraction using PyMuPDF (`fitz`), preserving 1-based page order, detecting empty/whitespace pages without inventing text.
- **Milestone 2 (`chunk_text.py`):** Configurable sliding-window text chunking with overlap, preserving word boundaries, provenance, stable unique IDs, and start/end page numbers.
- **Milestone 3 (`docling_extractor.py`):** Optional structured document extraction using IBM Docling for headings, paragraphs, and tables, with automatic, transparent fallback to PyMuPDF.

All milestones are decoupled into separate, reusable modules that adhere to a unified JSON contract.

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
*(If Docling is not installed, the pipeline automatically detects this and falls back to PyMuPDF without crashing or failing).*

---

## 3. How to Run

### Extraction (`extract_pdf.py`)

Extract text page-by-page from any PDF file using your chosen backend:

```bash
# 1. Default (Fast PyMuPDF extraction - 100% backward compatible)
python extract_pdf.py data/sample.pdf

# 2. Auto Backend (Tries Docling for structure; falls back to PyMuPDF if uninstalled/fails)
python extract_pdf.py data/sample.pdf --backend auto

# 3. Strict Docling Backend (Requires Docling installed; reports error if uninstalled)
python extract_pdf.py data/sample.pdf --backend docling

# 4. Overwrite existing extracted output
python extract_pdf.py data/sample.pdf --overwrite
```
Outputs: `data/processed/<name>_extracted.json`

---

### Chunking (`chunk_text.py`)

Chunk directly from a raw PDF **or** from an already extracted JSON file:

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

## 4. Output JSON Schemas

### Normalized Extraction Schema (`data/processed/<name>_extracted.json`)

The schema maintains **100% backward compatibility** with Milestone 1 while adding structured metadata:

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
      "text": "Adaptive Multimodal Corrective RAG (AMCRAG)\nAbstract: ...",
      "char_count": 312,
      "is_empty": false,
      "headings": ["Adaptive Multimodal Corrective RAG (AMCRAG)"],
      "paragraphs": ["Abstract: Large Language Models frequently suffer..."],
      "tables": []
    }
  ]
}
```

#### Why this schema design?
- **Existing consumers:** Teammates reading `page["text"]` or `page["page_number"]` experience zero breakage.
- **Structured consumers:** Teammates needing table markdown (`tables[*].markdown`) or section titles (`headings`) can access them directly without regex hacks.
- **Auditability:** `backend_used`, `fallback_occurred`, and `fallback_reason` explicitly document how the file was parsed.

---

### Chunk Output Schema (`data/processed/<name>_chunks.json`)

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
      "chunk_text": "Adaptive Multimodal Corrective RAG (AMCRAG)...",
      "source_file": "sample.pdf",
      "start_page": 1,
      "end_page": 2,
      "page_numbers": [1, 2],
      "char_count": 495,
      "word_count": 65
    }
  ]
}
```

---

## 5. Automated Tests

```bash
# Run the entire test suite (33 tests)
pytest -v

# Run Milestone 1 tests (15 extraction tests)
pytest tests/test_extract_pdf.py -v

# Run Milestone 2 tests (11 chunking tests)
pytest tests/test_chunk_text.py -v

# Run Milestone 3 tests (7 Docling normalization & fallback tests)
pytest tests/test_docling_extractor.py -v
```

---

## 6. What's Next
- **Milestone 4:** High-DPI page rendering to PNG images (`data/page_images/`) for downstream visual retrieval (ColPali).
