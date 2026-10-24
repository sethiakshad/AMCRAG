"""Backward-compatibility shim for sparse_engine.

Canonical module location: app.retrieval.sparse_engine
Owner: Om Khapekar (Person 2 - Sparse BM25 Retrieval)
"""

from app.retrieval.sparse_engine import BM25SparseEngine

__all__ = ["BM25SparseEngine"]
