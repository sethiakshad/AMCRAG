"""CRAG (Corrective Retrieval-Augmented Generation) package for AMCRAG.

Implements Person 4 deliverables:
- BaseCRAGEvaluator, HeuristicCRAGEvaluator, T5CRAGEvaluator
- CRAGDecisionEngine, DecisionConfig
- QueryReformulator, CorrectionConfig
- CRAGController
"""

from app.crag.controller import CRAGController
from app.crag.correction import CorrectionConfig, QueryReformulator
from app.crag.decisions import CRAGDecisionEngine, DecisionConfig
from app.crag.evaluator import (
    BaseCRAGEvaluator,
    HeuristicCRAGEvaluator,
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
