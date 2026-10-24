"""Backward-compatibility shim for backend.app.schemas.crag. Canonical: app.schemas.crag."""
from app.schemas.crag import (
    AmbiguousPolicy,
    CandidateEvaluation,
    CRAGResult,
    EvidenceDecision,
    EvidenceLabel,
)

__all__ = [
    "AmbiguousPolicy",
    "CandidateEvaluation",
    "CRAGResult",
    "EvidenceDecision",
    "EvidenceLabel",
]
