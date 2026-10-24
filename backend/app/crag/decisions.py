"""Backward-compatibility shim for backend.app.crag.decisions. Canonical: app.crag.decisions."""
from app.crag.decisions import CRAGDecisionEngine, DecisionConfig

__all__ = ["CRAGDecisionEngine", "DecisionConfig"]
