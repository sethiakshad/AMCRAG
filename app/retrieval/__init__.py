"""Retrieval subpackage for AMCRAG (Person 2 deliverables).

Provides:
- BGEDenseEngine: Dense embedding and Qdrant vector retrieval (BAAI/bge-base-en-v1.5)
- BM25SparseEngine: Sparse lexical inverted-index search (rank-bm25 Okapi)
- ReciprocalRankFusion: Multi-channel rank fusion algorithm (RRF)
- HybridTextRetriever: Combined dense + sparse text retrieval pipeline
- MultimodalFusionBridge: Integration bridge connecting text retrieval with ColPali visual candidates
"""

from app.retrieval.fusion_engine import ReciprocalRankFusion
from app.retrieval.multimodal_bridge import MultimodalFusionBridge

# Optional heavy dependencies (graceful failure when sentence-transformers or rank-bm25 not installed)
try:
    from app.retrieval.dense_engine import BGEDenseEngine
except ImportError:
    BGEDenseEngine = None  # type: ignore

try:
    from app.retrieval.sparse_engine import BM25SparseEngine
except ImportError:
    BM25SparseEngine = None  # type: ignore

try:
    from app.retrieval.hybrid_retriever import HybridTextRetriever
except ImportError:
    HybridTextRetriever = None  # type: ignore

__all__ = [
    "BGEDenseEngine",
    "BM25SparseEngine",
    "ReciprocalRankFusion",
    "HybridTextRetriever",
    "MultimodalFusionBridge",
]
