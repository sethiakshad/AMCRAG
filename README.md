# AMCRAG - Milestone 1: Page-wise PDF Text Extraction

> **Module:** Person 1 — Document Processing and Knowledge Base Preparation  
> **Project:** AMCRAG (Adaptive Multimodal Corrective RAG)

---

## 1. Overview

This is the initial, foundational step of Person 1's module. It extracts text separately from every page of a PDF document using **PyMuPDF (`fitz`)**, preserves original page order, uses 1-based page numbering, and exports the clean text into a structured, UTF-8 encoded JSON format for downstream processing.

### Key Capabilities
- **Page-by-page extraction:** Text from each page is stored individually.
- **1-based page numbering:** Page 1 corresponds to PDF page 1.
- **Empty page detection:** Transparently flags pages with no extracted text or only whitespace (e.g., scanned images or blank pages) without inventing text or claiming OCR was performed.
- **Resilient error handling:** Handles missing files, invalid formats, empty files, and password-protected PDFs with user-friendly messages.
- **Structured UTF-8 JSON output:** Creates output directories on the fly and saves clean JSON files.

---

## 2. Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.13)

### Installation
Install the minimal dependencies for this milestone:

```bash
pip install -r requirements.txt
```

*(Only `pymupdf>=1.24.0` is required for this milestone).*

---

## 3. How to Run

### Example 1: Run on the included sample PDF
A sample 3-page PDF is provided in `data/sample.pdf` (containing text on pages 1 and 2, and an intentionally blank page 3 to test empty page detection):

```bash
python extract_pdf.py data/sample.pdf
```

### Example 2: Run on your own PDF
```bash
python extract_pdf.py path/to/your_paper.pdf
```

### Example 3: Specify a custom output directory
```bash
python extract_pdf.py data/sample.pdf --output-dir my_output_folder
```

---

## 4. Output JSON Format

Output files are saved to `data/processed/<filename>_extracted.json`:

```json
{
  "source_file": "sample.pdf",
  "total_pages": 3,
  "empty_pages": [3],
  "has_empty_pages": true,
  "pages": [
    {
      "page_number": 1,
      "text": "Adaptive Multimodal Corrective RAG (AMCRAG)\nAbstract: ...",
      "char_count": 272,
      "is_empty": false
    },
    {
      "page_number": 2,
      "text": "Section 2: Document Ingestion Pipeline\nPerson 1 is responsible...",
      "char_count": 258,
      "is_empty": false
    },
    {
      "page_number": 3,
      "text": "",
      "char_count": 0,
      "is_empty": true
    }
  ]
}
```

---

## 5. What's Next (Upcoming Milestones)
- **Milestone 2:** Page image rendering at configurable DPI for teammate's ColPali visual retrieval module.
- **Milestone 3:** Sentence-aware text chunking with chunk overlap and page-level citation metadata.
- **Milestone 4:** Structured table & layout parsing with Docling.
