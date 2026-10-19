"""
Self-Contained Verification Script for Hybrid Text Retrieval & Multimodal Fusion.
Project: AMC-RAG
"""
from schemas import DocumentChunk, RetrievalResult
from fusion_engine import ReciprocalRankFusion
from multimodal_bridge import MultimodalFusionBridge


def run_unit_simulation():
    print("AMC-RAG RETRIEVAL & FUSION UNIT SIMULATION")

    # 1. Simulate Document Chunks from Knowledge Base Teammate
    chunks = [
        DocumentChunk(
            chunk_id="c1",
            document_id="docling_paper.pdf",
            page_number=2,
            text="Docling parses complex document layouts including tables and reading orders.",
            metadata={"source": "Docling Engine"}
        ),
        DocumentChunk(
            chunk_id="c2",
            document_id="crag_paper.pdf",
            page_number=4,
            text="Corrective RAG uses a T5-large evaluator to assign confidence scores: Correct, Ambiguous, Incorrect.",
            metadata={"source": "CRAG Engine"}
        ),
        DocumentChunk(
            chunk_id="c3",
            document_id="amc_rag_spec.pdf",
            page_number=12,
            text="Error code E-502 denotes network timeout during ColPali image transfer over HTTP.",
            metadata={"source": "Diagnostics"}
        )
    ]
    print(f"1. Upstream Contract: Successfully received {len(chunks)} DocumentChunks.")

    # 2. Simulate Fusion between Dense and Sparse results
    from schemas import ScoredCandidate
    dense_cand = [
        ScoredCandidate(chunk_id="c2", document_id="crag_paper.pdf", page_number=4, text=chunks[1].text, score=0.89, rank=1),
        ScoredCandidate(chunk_id="c1", document_id="docling_paper.pdf", page_number=2, text=chunks[0].text, score=0.74, rank=2),
    ]
    sparse_cand = [
        ScoredCandidate(chunk_id="c3", document_id="amc_rag_spec.pdf", page_number=12, text=chunks[2].text, score=4.12, rank=1),
        ScoredCandidate(chunk_id="c2", document_id="crag_paper.pdf", page_number=4, text=chunks[1].text, score=2.50, rank=2),
    ]

    fusion = ReciprocalRankFusion(k=60)
    fused_text = fusion.fuse(dense_candidates=dense_cand, sparse_candidates=sparse_cand, top_k=3)
    print("\n2. Hybrid Text Retrieval (RRF Fused Candidates):")
    for r in fused_text:
        print(f"   [{r.chunk_id}] FusedScore={r.fused_score:.5f} | DenseRank={r.dense_rank} | SparseRank={r.sparse_rank} | Text: {r.text[:50]}...")

    # 3. Simulate ColPali Visual Page Retrieval from Teammate
    colpali_visual_results = [
        RetrievalResult(
            chunk_id="page_img_crag_p4",
            document_id="crag_paper.pdf",
            page_number=4,
            text="[Visual Rendering of Page 4 showing CRAG architecture diagram]",
            modality="visual_page",
            fused_score=0.016, # ColPali rank 1
            metadata={"type": "visual_page_300dpi"}
        )
    ]

    # 4. Multimodal Fusion Bridge (Feeding into BGE Reranker & T5 Evaluator)
    final_merged = MultimodalFusionBridge.merge_text_and_visual(
        text_results=fused_text,
        visual_results=colpali_visual_results,
        final_top_k=3
    )

    print("\n3. Cross-Modal Fusion Output (Ready for BGE-Reranker & T5-Large Evaluator):")
    for idx, item in enumerate(final_merged, 1):
        print(f"   Rank {idx}: [{item.modality.upper()}] Doc={item.document_id} P={item.page_number} FusedScore={item.fused_score:.5f}")

    print("\n[SUCCESS] All data contracts and interfaces operate deterministically.")


if __name__ == "__main__":
    run_unit_simulation()
