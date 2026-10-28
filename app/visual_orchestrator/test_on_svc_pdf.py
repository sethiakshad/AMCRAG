"""Targeted End-to-End Test for Visual Orchestrator on '6-Support+Vector+Classifier.pdf'.

Executes:
1. Rendering of '6-Support+Vector+Classifier.pdf' pages into 150 DPI PNG images
2. Visual indexing using Ollama Cloud Gemma 4 Vision into Qdrant ('gemma_visual_pages')
3. Multimodal visual search across multiple test queries
4. Candidate ranking, scoring, and visual reranking
5. Schema compliance verification against ScoredCandidate and RetrievalCandidate
"""

import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pymupdf

from app.schemas.document import PageRenderInfo
from app.schemas.retrieval import RetrievalCandidate
from app.visual_orchestrator.bridge import GemmaVisualBridge
from schemas import RetrievalResult, ScoredCandidate


def render_pdf(pdf_path: Path, output_dir: Path) -> list[PageRenderInfo]:
    """Renders PDF pages to 150 DPI PNGs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf_path))
    zoom = 150 / 72.0
    mat = pymupdf.Matrix(zoom, zoom)

    rendered: list[PageRenderInfo] = []
    print(f"\n[1/4] Rendering '{pdf_path.name}' ({len(doc)} pages) to PNG images...")
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat)
        img_path = output_dir / f"page_{i:03d}.png"
        pix.save(str(img_path))
        raw_text = page.get_text().strip()

        file_size_kb = img_path.stat().st_size / 1024
        info = PageRenderInfo(
            page_number=i,
            image_path=str(img_path.resolve()),
            width=pix.width,
            height=pix.height,
            dpi=150,
            title=f"Page {i}",
            caption=f"Visual page {i} from {pdf_path.name}",
        )
        rendered.append(info)
        print(f"  • Page {i}: {img_path.name} ({pix.width}x{pix.height}, {file_size_kb:.1f} KB)")
    return rendered


def main():
    print("=" * 70)
    print("AMCRAG VISUAL ORCHESTRATOR — TARGET TEST ON 6-Support+Vector+Classifier.pdf")
    print("=" * 70)

    pdf_file = PROJECT_ROOT / "6-Support+Vector+Classifier.pdf"
    if not pdf_file.exists():
        print(f"ERROR: Target PDF not found at {pdf_file}")
        sys.exit(1)

    images_dir = PROJECT_ROOT / "data" / "page_images" / "svc_classifier_test"
    rendered_pages = render_pdf(pdf_file, images_dir)

    # 2. Initialize GemmaVisualBridge
    print("\n[2/4] Initializing GemmaVisualBridge with Ollama Cloud Gemma 4 Vision...")
    storage_path = str(PROJECT_ROOT / "data" / "gemma_qdrant_storage")
    bridge = GemmaVisualBridge(
        storage_path=storage_path,
        collection="gemma_visual_pages",
        top_k=3,
        enabled=True,
    )
    print(f"  • Bridge initialized: is_ready={bridge.is_ready}")
    print(f"  • Qdrant collection: '{bridge.collection}'")
    print(f"  • Model: '{bridge.model.model_name}' (Ollama Cloud)")

    # 3. Index the pages
    print("\n[3/4] Indexing rendered pages of 6-Support+Vector+Classifier.pdf...")
    doc_id = "doc_svc_classifier"
    start_t = time.time()
    indexed_count = bridge.index_pages(
        rendered_pages=rendered_pages,
        document_id=doc_id,
        source_filename=pdf_file.name,
    )
    elapsed = time.time() - start_t
    verified_count = bridge.count_document_pages(doc_id)
    print(f"  • Successfully indexed: {indexed_count} pages in {elapsed:.2f}s")
    print(f"  • Verified in Qdrant: {verified_count} page points")

    # 4. Search and Rerank Queries
    print("\n[4/4] Executing Visual Search & Reranking Queries on target PDF...")
    test_queries = [
        "Support vector classifier optimal hyperplane and margin",
        "Linear boundary between positive and negative data points",
        "Soft margin tolerance and support vectors classification",
    ]

    for q_idx, query in enumerate(test_queries, start=1):
        print(f"\n--- Query {q_idx}: \"{query}\" ---")

        # A. Visual Retrieval
        scored_candidates = bridge.retrieve(query=query, top_k=3)
        print(f"Retrieved {len(scored_candidates)} ScoredCandidate(s):")
        for sc in scored_candidates:
            page_num = sc.metadata.get("page_number", sc.page_number)
            print(f"  [Rank {sc.rank}] Page {page_num}: Score={sc.score:.4f} | Modality={sc.modality} | ID={sc.chunk_id}")

        # B. Retrieve CRAG candidates schema
        crag_candidates = bridge.retrieve_candidates(query=query, top_k=2)
        print(f"\nCRAG Candidate Schema Check (for Person 4):")
        for cc in crag_candidates:
            assert isinstance(cc, RetrievalCandidate), "Must conform to RetrievalCandidate!"
            print(f"  • candidate_id={cc.candidate_id}, type={cc.candidate_type}, score={cc.retrieval_score:.4f}, method={cc.retrieval_method}")

        # C. Visual Reranker
        retrieval_results = bridge.retriever.retrieve_results(query=query, top_k=3)
        reranked = bridge.rerank(query=query, candidates=retrieval_results, strategy="visual_only")
        print(f"\nReranked Results (visual_only):")
        for r_idx, r in enumerate(reranked, start=1):
            assert isinstance(r, RetrievalResult), "Must conform to RetrievalResult!"
            print(f"  [Pos {r_idx}] Page {r.page_number}: Final Score={r.fused_score:.4f} (Raw={r.score:.4f})")

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED SUCCESSFULLY ON 6-Support+Vector+Classifier.pdf!")
    print("=" * 70)


if __name__ == "__main__":
    main()
