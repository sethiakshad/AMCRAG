"""CRAG evaluation and decision contracts for AMCRAG.

Follows Sections 4.7, 4.8, 10.4, and 10.5 of AMCRAG Central Project Documentation.
"""

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalCandidate

EvidenceLabel = Literal["CORRECT", "AMBIGUOUS", "INCORRECT"]


class AmbiguousPolicy(str, Enum):
    """Configurable policy for handling AMBIGUOUS evidence decisions."""

    RETRY_ONCE = "retry_once"
    ACCEPT_WITH_QUALIFICATION = "accept_with_qualification"
    STRICT_CORRECTION = "strict_correction"


class CandidateEvaluation(BaseModel):
    """Evaluation result for an individual retrieved candidate."""

    candidate_id: str
    relevance_score: float = Field(
        ..., description="Relevance score (normalized or confidence metric)"
    )
    is_relevant: bool = Field(
        ..., description="Whether this individual candidate is considered relevant"
    )
    extracted_strips: list[str] = Field(
        default_factory=list,
        description="Key knowledge strips decomposed from the candidate passage (CRAG refinement)",
    )
    notes: str | None = Field(default=None, description="Diagnostic notes or confidence explanation")


class EvidenceDecision(BaseModel):
    """Aggregate decision on the retrieved candidate set for a query."""

    label: EvidenceLabel = Field(
        ..., description="Aggregate decision: CORRECT, AMBIGUOUS, or INCORRECT"
    )
    score: float | None = Field(
        default=None, description="Aggregate confidence score across evidence candidates"
    )
    explanation: str | None = Field(
        default=None, description="Detailed explanation of the decision rationale"
    )
    needs_correction: bool = Field(
        ..., description="Whether the orchestrator must perform a corrective retrieval loop"
    )
    candidate_evaluations: list[CandidateEvaluation] = Field(
        default_factory=list, description="Per-candidate evaluation breakdown"
    )
    attempt_number: int = Field(
        default=0, description="Current retrieval attempt number (0 = initial, 1 = first retry, etc.)"
    )


class CRAGResult(BaseModel):
    """Final output package from the Person 4 CRAG controller for the orchestrator."""

    decision: EvidenceDecision
    reformulated_query: str | None = Field(
        default=None, description="New retrieval query if correction is triggered"
    )
    accepted_candidates: list[RetrievalCandidate] = Field(
        default_factory=list,
        description="Filtered/refined candidates passed forward to Context Builder",
    )
    can_proceed_to_generation: bool = Field(
        ..., description="True if evidence is ready for answer generation"
    )
    insufficient_evidence: bool = Field(
        default=False,
        description="True if retries are exhausted and evidence remains inadequate",
    )
