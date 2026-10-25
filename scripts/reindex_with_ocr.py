"""reindex_with_ocr.py — OCR scanned document and reindex with Person 2 HybridTextRetriever."""

import json
import logging
import subprocess
import sys
from pathlib import Path

from app.config import default_settings
from app.retrieval.hybrid_retriever import HybridTextRetriever
from schemas import DocumentChunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OCRReindexer")

def main():
    doc_id = "doc_79fc1b9312059890"
    pdf_filename = "doc_79fc1b9312059890_E Balagurusamy - Programming with Java a Primer-McGraw-Hill (2008).pdf"
    
    images_dir = Path("data/page_images") / doc_id
    if not images_dir.exists():
        logger.error("Images directory %s not found!", images_dir)
        sys.exit(1)
        
    start_page = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end_page = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    logger.info("Running Apple Vision OCR on %s (pages %d to %d)...", doc_id, start_page, end_page)
    cmd = ["./scripts/fast_ocr_bin", str(images_dir), str(start_page), str(end_page)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("OCR execution failed: %s", proc.stderr)
        sys.exit(1)

    try:
        pages_data = json.loads(proc.stdout)
    except Exception as e:
        logger.error("Failed to parse OCR output: %s", e)
        sys.exit(1)

    logger.info("Successfully OCRed %d pages. Preparing text chunks...", len(pages_data))
    
    # Filter watermarks & split into substantive chunks
    watermark_terms = ["books4career.blogspot.com", "copyrighted material"]
    chunks: list[DocumentChunk] = []
    
    for item in pages_data:
        p_num = item["page"]
        raw_text = item["text"]
        
        # Clean watermark lines
        clean_lines = []
        for line in raw_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if any(term in line_str.lower() for term in watermark_terms):
                continue
            clean_lines.append(line_str)
            
        page_clean_text = "\n".join(clean_lines).strip()
        if len(page_clean_text) < 30:
            continue
            
        # Create chunk (if page text is large, split into ~800 char blocks)
        chunk_size = 800
        overlap = 150
        text_len = len(page_clean_text)
        
        start_idx = 0
        c_sub = 0
        while start_idx < text_len:
            end_idx = min(start_idx + chunk_size, text_len)
            chunk_content = page_clean_text[start_idx:end_idx].strip()
            if chunk_content:
                cid = f"{doc_id}_p{p_num:03d}_c{c_sub:02d}"
                chunk = DocumentChunk(
                    chunk_id=cid,
                    document_id=doc_id,
                    source_filename=pdf_filename,
                    page_number=p_num,
                    page_start=p_num,
                    page_end=p_num,
                    text=chunk_content,
                    candidate_type="text_chunk",
                    chunk_index=len(chunks),
                    section_heading=f"Page {p_num}",
                    char_count=len(chunk_content),
                    word_count=len(chunk_content.split()),
                )
                chunks.append(chunk)
                c_sub += 1
            if end_idx >= text_len:
                break
            start_idx += (chunk_size - overlap)

    logger.info("Generated %d rich text chunks from OCR text. Indexing into Knowledge Base...", len(chunks))
    
    retriever = HybridTextRetriever(
        dense_model_name="BAAI/bge-base-en-v1.5",
        qdrant_path=str(default_settings.base_dir / "qdrant_storage"),
        bm25_index_path=str(default_settings.base_dir / "bm25_index.pkl"),
    )
    indexed = retriever.index_knowledge_base(chunks=chunks)
    logger.info("Successfully indexed %s chunks into Qdrant & BM25!", indexed)
    
    # Update processed json
    processed_json = Path("data/processed") / f"{doc_id}.json"
    if processed_json.exists():
        with open(processed_json, "r") as f:
            d = json.load(f)
        d["chunks"] = [c.model_dump() for c in chunks]
        d["total_chunks"] = len(chunks)
        d["is_scanned"] = True
        d["ocr_needed"] = False
        d["status"] = "indexed_with_ocr"
        d["warnings"] = [f"OCRed {len(pages_data)} pages using Apple Vision Engine."]
        with open(processed_json, "w") as f:
            json.dump(d, f, indent=2)
        logger.info("Updated %s with new chunk data.", processed_json)

if __name__ == "__main__":
    main()
