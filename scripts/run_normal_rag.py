"""run_normal_rag.py — Standalone CLI runner to test Normal RAG baseline on a PDF or query.

Usage:
    # 1. Query an already processed document or sample chunks:
    python scripts/run_normal_rag.py --query "What is the primary contribution of the paper?"

    # 2. Ingest and query a PDF document:
    python scripts/run_normal_rag.py --pdf data/sample.pdf --query "What is AMCRAG?" --top-k 3
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.normal_rag.config import NormalRAGConfig
from app.normal_rag.pipeline import NormalRAGPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("NormalRAG.CLI")


def main():
    parser = argparse.ArgumentParser(description="Execute Normal RAG baseline on documents or questions.")
    parser.add_argument("--query", "-q", type=str, default="What are the key components of the system?", help="Question to query")
    parser.add_argument("--pdf", type=str, default=None, help="Path to PDF file to ingest and index")
    parser.add_argument("--doc-id", type=str, default=None, help="Document ID from data/processed/{doc_id}.json to index")
    parser.add_argument("--top-k", "-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
    args = parser.parse_args()

    pipeline = NormalRAGPipeline(config=NormalRAGConfig(top_k=args.top_k))

    # Ingest PDF if provided
    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            logger.error("Specified PDF does not exist: %s", pdf_path)
            sys.exit(1)
        logger.info("Ingesting and indexing PDF: %s", pdf_path)
        pipeline.ingest_pdf(pdf_path)

    # Index doc-id if provided
    elif args.doc_id:
        processed_file = PROJECT_ROOT / "data" / "processed" / f"{args.doc_id}.json"
        if not processed_file.exists():
            logger.error("Processed document JSON not found: %s", processed_file)
            sys.exit(1)
        from app.schemas.chunk import ProcessedDocumentOutput

        data = json.loads(processed_file.read_text(encoding="utf-8"))
        doc_output = ProcessedDocumentOutput.model_validate(data)
        pipeline.index_document_output(doc_output)

    # Fallback to sample chunks if nothing indexed and sample_chunks.json exists
    else:
        sample_chunks_path = PROJECT_ROOT / "data" / "processed" / "sample_chunks.json"
        if sample_chunks_path.exists():
            try:
                data = json.loads(sample_chunks_path.read_text(encoding="utf-8"))
                chunks = data.get("chunks", [])
                if chunks:
                    logger.info("Pre-loading %d sample chunks from %s", len(chunks), sample_chunks_path.name)
                    pipeline.index_chunks(chunks)
            except Exception as e:
                logger.warning("Could not pre-load sample chunks: %s", e)

    # Execute query
    logger.info("Executing Normal RAG for query: '%s' (top_k=%d)...", args.query, args.top_k)
    result = pipeline.query(query_text=args.query, top_k=args.top_k)

    print("\n" + "=" * 70)
    print("NORMAL RAG BASELINE RESULT")
    print("=" * 70)
    print(f"System:                {result.system}")
    print(f"Question:              {result.question}")
    print(f"Retrieval Latency:     {result.retrieval_latency_ms:.2f} ms")
    print(f"Generation Latency:    {result.generation_latency_ms:.2f} ms")
    print(f"Total Latency:         {result.total_latency_ms:.2f} ms")
    print(f"Source Pages:          {result.source_pages}")
    print(f"Retrieved Chunks:      {len(result.retrieved_chunks)}")
    print("-" * 70)
    print("Generated Answer:")
    print(result.answer)
    print("-" * 70)
    if result.retrieved_chunks:
        print("Retrieved Chunks Detail:")
        for chunk in result.retrieved_chunks:
            print(f"  - [{chunk.chunk_id}] (Score: {chunk.score:.4f}, Page: {chunk.page_number}): {chunk.text[:120]}...")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
