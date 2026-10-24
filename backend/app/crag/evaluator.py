"""Backward-compatibility shim for backend.app.crag.evaluator. Canonical: app.crag.evaluator."""
from app.crag.evaluator import (
    BaseCRAGEvaluator,
    HeuristicCRAGEvaluator,
    T5CRAGEvaluator,
)

__all__ = [
    "BaseCRAGEvaluator",
    "HeuristicCRAGEvaluator",
    "T5CRAGEvaluator",
]
