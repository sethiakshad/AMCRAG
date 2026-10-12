# AMCRAG - Document Processing & Knowledge Base Preparation

> **Module:** Person 1 — Document Processing and Knowledge Base Preparation  
> **Project:** AMCRAG (Adaptive Multimodal Corrective RAG)

---

## 1. Overview & Architecture

Person 1's module prepares clean, structured knowledge representations from input PDF research papers for downstream AMCRAG teammates:
- **Milestone 1 (`extract_pdf.py`):** Page-wise text extraction using PyMuPDF (`fitz`), preserving 1-based page order, transparently detecting empty/whitespace pages without inventing text.
- **Milestone 2 (`chunk_text.py`):** Configurable sliding-window text chunking with overlap, preserving word boundaries, source file provenance, stable unique IDs, and exact start/end page numbers for citation tracking.

Extraction and chunking are cleanly decoupled into separate, reusable modules.

---

## 2. Setup & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.13)

### Installation
```bash
pip install -r requirements.txt
```
*(Requires `pymupdf>=1.24.0` and `pytest>=8.0.0` for automated testing).*

---

## 3. How to Run

### Milestone 1: PDF Text Extraction (`extract_pdf.py`)

Extract text page-by-page from any PDF file:

```bash
# Basic extraction
python extract_pdf.py data/sample.pdf

# Overwrite existing extracted output
python extract_pdf.py data/sample.pdf --overwrite

# Custom output directory
python extract_pdf.py data/sample.pdf --output-dir my_custom_dir
```
Outputs: `data/processed/<name>_extracted.json`

---

### Milestone 2: Text Chunking (`chunk_text.py`)

Chunk directly from a raw PDF **or** from an already extracted JSON file:

```bash
# Chunk directly from PDF with default parameters (chunk_size=500, chunk_overlap=100)
python chunk_text.py data/sample.pdf

# Custom chunk size and overlap
python chunk_text.py data/sample.pdf --chunk-size 300 --chunk-overlap 50

# Chunk an already extracted JSON file
python chunk_text.py data/processed/sample_extracted.json

# Overwrite existing chunk output
python chunk_text.py data/sample.pdf --overwrite
```
Outputs: `data/processed/<name>_chunks.json`

---

## 4. Chunking Logic & Walkthrough

### Word-Stream Page Tagging
1. Every word in the document is mapped to its origin page: `[(word_1, page_1), (word_2, page_1), ..., (word_k, page_2)]`.
2. **Word Boundary Preservation:** Chunks accumulate complete words until reaching `chunk_size` characters, ensuring words are never truncated in half.
3. **Multi-Page Tracking:** If a chunk begins with words from Page 1 and ends with words from Page 2, `start_page` is set to `1`, `end_page` is set to `2`, and `page_numbers` contains `[1, 2]`.
4. **Controlled Overlap:** The next chunk steps backward to include ~`chunk_overlap` characters from the end of the previous chunk, ensuring semantic context is preserved across chunk boundaries while guaranteeing steady forward progress without duplicate chunks.

---

## 5. Output JSON Schemas

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
      "chunk_text": "Adaptive Multimodal Corrective RAG (AMCRAG) Abstract: Large Language Models frequently suffer from hallucinations...",
      "source_file": "sample.pdf",
      "start_page": 1,
      "end_page": 1,
      "page_numbers": [1],
      "char_count": 312,
      "word_count": 42
    },
    {
      "chunk_id": "sample_chunk_0002",
      "chunk_index": 1,
      "chunk_text": "Section 2: Document Ingestion Pipeline Person 1 is responsible for Document Processing...",
      "source_file": "sample.pdf",
      "start_page": 2,
      "end_page": 2,
      "page_numbers": [2],
      "char_count": 297,
      "word_count": 39
    }
  ]
}
```

---

## 6. Running Automated Tests

Run the complete test suite verifying both extraction and chunking:

```bash
# Run all tests
pytest -v

# Run Milestone 1 extraction tests (15 tests)
pytest tests/test_extract_pdf.py -v

# Run Milestone 2 chunking tests (11 tests)
pytest tests/test_chunk_text.py -v
```

---

## 7. Upcoming Milestones
- **Milestone 3:** Page image rendering at configurable DPI for teammate's ColPali visual retrieval module.
- **Milestone 4:** Structured table & layout parsing with Docling.
