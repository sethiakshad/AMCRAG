"""Backward-compatibility shim for backend.app.crag package.

Canonical module location: app.crag
"""

from app.crag import (
    BaseCRAGEvaluator,
    CRAGController,
    CRAGDecisionEngine,
    CorrectionConfig,
    DecisionConfig,
    HeuristicCRAGEvaluator,
    QueryReformulator,
    T5CRAGEvaluator,
)

__all__ = [
    "BaseCRAGEvaluator",
    "HeuristicCRAGEvaluator",
    "T5CRAGEvaluator",
    "CRAGDecisionEngine",
    "DecisionConfig",
    "QueryReformulator",
    "CorrectionConfig",
    "CRAGController",
]
