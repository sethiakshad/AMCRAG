"""Utility script to generate a sample demonstration PDF in data/uploads/."""

from pathlib import Path
import fitz

uploads_dir = Path("data/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
pdf_path = uploads_dir / "sample_amcrag_overview.pdf"

doc = fitz.open()

# Page 1
p1 = doc.new_page()
p1.insert_text(fitz.Point(50, 60), "AMCRAG: Adaptive Multimodal Corrective RAG", fontsize=16)
p1.insert_text(fitz.Point(50, 90), "Section 1: Project Overview", fontsize=13)
body_p1 = (
    "Retrieval-Augmented Generation (RAG) systems often fail when processing multi-page documents containing "
    "both dense textual descriptions and complex visual layouts such as charts, tables, and diagrams. "
    "The AMCRAG framework introduces an adaptive corrective loop combined with multimodal visual embeddings "
    "to verify factual accuracy before final response generation. "
    "The initial phase of AMCRAG is Document Processing and Knowledge Base Preparation, spearheaded by Person 1."
)
p1.insert_textbox(fitz.Rect(50, 110, 540, 400), body_p1, fontsize=10)

# Page 2
p2 = doc.new_page()
p2.insert_text(fitz.Point(50, 60), "Section 2: Pipeline Responsibilities", fontsize=13)
body_p2 = (
    "Person 1's module handles PDF file ingestion, dual extraction using PyMuPDF and Docling with automated "
    "fallback mechanics, text chunking with full citation metadata preservation, and high-DPI page rendering "
    "specifically designed for ColPali visual indexing. "
    "Downstream modules consume standard JSON contracts to perform dense vector indexing in Qdrant, BM25 sparse "
    "indexing, ColPali late interaction retrieval, and CRAG correctness evaluation."
)
p2.insert_textbox(fitz.Rect(50, 80, 540, 350), body_p2, fontsize=10)

doc.save(str(pdf_path))
doc.close()
print(f"Sample demonstration PDF successfully created at: {pdf_path.resolve()}")
