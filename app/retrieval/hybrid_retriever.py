"""
Unified Pluggable Hybrid Text Retriever Subsystem.
Single interface connecting Upstream Chunking to Downstream Multimodal/Reranker pipelines.
Owner: Om Khapekar (Person 2 - Dense/Sparse Text Retrieval & Fusion)
"""
from typing import List, Optional, Any
from schemas import DocumentChunk, RetrievalResult, RetrievalCandidate
try:
    from app.retrieval.dense_engine import BGEDenseEngine
    from app.retrieval.sparse_engine import BM25SparseEngine
    from app.retrieval.fusion_engine import ReciprocalRankFusion
except ImportError:
    from dense_engine import BGEDenseEngine
    from sparse_engine import BM25SparseEngine
    from fusion_engine import ReciprocalRankFusion


class HybridTextRetriever:
    """
    Main entry point for Person 2's deliverable in AMC-RAG.
    Connects Upstream Ingestion to Downstream Hybrid & Multimodal Retrieval.
    """
    def __init__(
        self,
        dense_model_name: str = "BAAI/bge-base-en-v1.5",
        qdrant_path: Optional[str] = "./qdrant_storage",
        bm25_index_path: Optional[str] = "./bm25_index.pkl",
        rrf_k: int = 60,
        weight_dense: float = 1.0,
        weight_sparse: float = 1.0,
        weight_visual: float = 1.0,
        device: Optional[str] = None
    ):
        self.dense_engine = BGEDenseEngine(
            model_name=dense_model_name,
            qdrant_path=qdrant_path,
            device=device
        )
        self.sparse_engine = BM25SparseEngine(
            index_file_path=bm25_index_path
        )
        self.fusion_engine = ReciprocalRankFusion(
            k=rrf_k,
            weight_dense=weight_dense,
            weight_sparse=weight_sparse,
            weight_visual=weight_visual
        )

    # -------------------------------------------------------------
    # PLUG 1: Upstream Ingestion Hook (Used by Knowledge Base teammate)
    # -------------------------------------------------------------
    def index_knowledge_base(self, chunks: List[DocumentChunk]):
        """
        Called when upstream teammate completes PDF document parsing and chunking.
        Indexes chunks into both Qdrant (dense) and BM25 (sparse).
        """
        print(f"[HybridRetriever] Ingesting {len(chunks)} chunks into Knowledge Stores...")
        # 1. Index in Qdrant Vector Store
        self.dense_engine.index_chunks(chunks)
        # 2. Index in BM25 Inverted Index
        self.sparse_engine.index_chunks(chunks)
        print("[HybridRetriever] Knowledge Base indexing completed successfully.")
        return len(chunks)

    # -------------------------------------------------------------
    # PLUG 2: Downstream Query Hook (Used by AMC-RAG Routing & Reranker)
    # -------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        top_k: int = 15,
        filters: Optional[dict] = None,
        dense_top_k: int = 25,
        sparse_top_k: int = 25,
        final_top_k: Optional[int] = None,
        visual_candidates: Optional[List[Any]] = None
    ) -> List[RetrievalResult]:
        """
        Executes parallel dense and keyword searches, then applies RRF.
        Conforms strictly to Section 10.2 Retrieval Interface:
        `def retrieve(query: str, top_k: int, filters: dict | None = None) -> list[RetrievalCandidate]`

        Args:
            query: User search query
            top_k: Final number of fused candidates to return
            filters: Optional metadata filters (e.g. {"document_id": "doc1.pdf"})
            dense_top_k: Number of raw dense candidates to fetch
            sparse_top_k: Number of raw BM25 candidates to fetch
            final_top_k: Deprecated alias for top_k (for backward compatibility)
            visual_candidates: Optional ColPali visual candidates from Person 3
        """
        effective_top_k = final_top_k if final_top_k is not None else top_k

        # Execute retrievals
        dense_candidates = self.dense_engine.search(
            query=query,
            top_k=dense_top_k,
            filters=filters
        )
        sparse_candidates = self.sparse_engine.search(
            query=query,
            top_k=sparse_top_k,
            filters=filters
        )

        # Fuse results with RRF (including optional visual candidates from Person 3)
        fused_candidates = self.fusion_engine.fuse(
            dense_candidates=dense_candidates,
            sparse_candidates=sparse_candidates,
            visual_candidates=visual_candidates,
            top_k=effective_top_k
        )
        return fused_candidates

    def delete_document(self, document_id: str) -> None:
        """Purges document chunks from dense Qdrant collection and sparse BM25 index."""
        if hasattr(self.dense_engine, "delete_document"):
            self.dense_engine.delete_document(document_id)
        if hasattr(self.sparse_engine, "delete_document"):
            self.sparse_engine.delete_document(document_id)
