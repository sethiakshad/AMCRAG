"""Evidence decision policy engine for AMCRAG.

Follows Sections 4.7, 4.8, 6.1, and 10.4 of AMCRAG Central Project Documentation.
"""

import os
from typing import Sequence
from pydantic import BaseModel, Field

from app.schemas.crag import (
    AmbiguousPolicy,
    CandidateEvaluation,
    EvidenceDecision,
    EvidenceLabel,
)
from app.schemas.retrieval import RetrievalCandidate


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is not None:
        try:
            return float(val)
        except ValueError:
            pass
    return default


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return default


class DecisionConfig(BaseModel):
    """Configuration parameters for evidence thresholding and ambiguous policy."""

    upper_threshold: float = Field(
        default_factory=lambda: _env_float("CRAG_UPPER_THRESHOLD", 0.65),
        description="Confidence threshold above which evidence is judged CORRECT (δ_upper)",
    )
    lower_threshold: float = Field(
        default_factory=lambda: _env_float("CRAG_LOWER_THRESHOLD", 0.30),
        description="Confidence threshold below which evidence is judged INCORRECT (δ_lower)",
    )
    ambiguous_policy: AmbiguousPolicy = Field(
        default_factory=lambda: AmbiguousPolicy(
            os.getenv("CRAG_AMBIGUOUS_POLICY", AmbiguousPolicy.RETRY_ONCE.value)
        ),
        description="Policy to execute when evidence score falls in [δ_lower, δ_upper]",
    )
    min_relevant_candidates: int = Field(
        default_factory=lambda: _env_int("CRAG_MIN_RELEVANT_CANDIDATES", 1),
        description="Minimum number of candidates exceeding upper_threshold for a decisive CORRECT",
    )
    peak_score_weight: float = Field(
        default_factory=lambda: _env_float("CRAG_PEAK_SCORE_WEIGHT", 0.7),
        description="Weight given to the top scoring candidate in aggregate score calculation",
    )


class CRAGDecisionEngine:
    """Evaluates candidate relevance scores to produce a system-level EvidenceDecision."""

    def __init__(self, config: DecisionConfig | None = None):
        self.config = config or DecisionConfig()

    def decide(
        self,
        candidate_evaluations: Sequence[CandidateEvaluation],
        attempt_number: int = 0,
        max_attempts: int = 2,
    ) -> EvidenceDecision:
        """Determines the EvidenceDecision based on candidate scores and configured policy.

        Args:
            candidate_evaluations: List of per-candidate evaluation objects.
            attempt_number: Current retrieval iteration index (0 = initial).
            max_attempts: Maximum correction retry limit.

        Returns:
            EvidenceDecision indicating whether to proceed or trigger corrective retrieval.
        """
        if not candidate_evaluations:
            return EvidenceDecision(
                label="INCORRECT",
                score=0.0,
                explanation="No candidates were retrieved for evaluation.",
                needs_correction=(attempt_number < max_attempts),
                candidate_evaluations=[],
                attempt_number=attempt_number,
            )

        # Aggregate evidence score: weighted combination of peak candidate and top-3 mean
        scores = [c.relevance_score for c in candidate_evaluations]
        max_score = max(scores)
        top_k_scores = sorted(scores, reverse=True)[:3]
        peak_weight = max(0.0, min(1.0, self.config.peak_score_weight))
        mean_weight = 1.0 - peak_weight
        aggregate_score = (max_score * peak_weight) + ((sum(top_k_scores) / len(top_k_scores)) * mean_weight)

        num_above_upper = sum(1 for s in scores if s >= self.config.upper_threshold)

        # 1. CORRECT Branch
        if max_score >= self.config.upper_threshold and num_above_upper >= self.config.min_relevant_candidates:
            label: EvidenceLabel = "CORRECT"
            needs_correction = False
            explanation = (
                f"Retrieved evidence is highly relevant (peak score: {max_score:.2f} >= "
                f"{self.config.upper_threshold}). Ready for context builder."
            )

        # 2. INCORRECT Branch
        elif max_score <= self.config.lower_threshold:
            label = "INCORRECT"
            # If we've reached max_attempts, we cannot retry anymore
            needs_correction = attempt_number < max_attempts
            if needs_correction:
                explanation = (
                    f"Retrieved evidence is inadequate (peak score: {max_score:.2f} <= "
                    f"{self.config.lower_threshold}). Triggering corrective retrieval attempt {attempt_number + 1}."
                )
            else:
                explanation = (
                    f"Retrieved evidence remains inadequate after {attempt_number + 1} attempts. "
                    "Retry limit reached; stopping to prevent hallucination."
                )

        # 3. AMBIGUOUS Branch (Between lower and upper thresholds)
        else:
            label = "AMBIGUOUS"
            needs_correction, explanation = self._handle_ambiguous(
                aggregate_score=aggregate_score,
                attempt_number=attempt_number,
                max_attempts=max_attempts,
            )

        return EvidenceDecision(
            label=label,
            score=round(aggregate_score, 4),
            explanation=explanation,
            needs_correction=needs_correction,
            candidate_evaluations=list(candidate_evaluations),
            attempt_number=attempt_number,
        )

    def _handle_ambiguous(
        self, aggregate_score: float, attempt_number: int, max_attempts: int
    ) -> tuple[bool, str]:
        """Applies configured policy to resolve ambiguous retrieval results."""
        if attempt_number >= max_attempts:
            return (
                False,
                f"Evidence is ambiguous (score: {aggregate_score:.2f}) but retry limit reached. "
                "Proceeding with qualification.",
            )

        policy = self.config.ambiguous_policy

        if policy == AmbiguousPolicy.RETRY_ONCE:
            if attempt_number == 0:
                return (
                    True,
                    f"Evidence is ambiguous (score: {aggregate_score:.2f}). "
                    f"Executing 1 corrective retrieval retry under '{policy.value}' policy.",
                )
            return (
                False,
                f"Evidence remains ambiguous after retry (score: {aggregate_score:.2f}). "
                "Proceeding to generation with qualified context.",
            )

        if policy == AmbiguousPolicy.ACCEPT_WITH_QUALIFICATION:
            return (
                False,
                f"Evidence is ambiguous (score: {aggregate_score:.2f}). "
                f"Proceeding immediately to context builder under '{policy.value}' policy.",
            )

        if policy == AmbiguousPolicy.STRICT_CORRECTION:
            return (
                True,
                f"Evidence is ambiguous (score: {aggregate_score:.2f}). "
                f"Triggering corrective retrieval under '{policy.value}' policy.",
            )

        return (False, f"Unrecognized ambiguous policy '{policy}'. Defaulting to proceed.")

    def filter_accepted_candidates(
        self,
        candidates: Sequence[RetrievalCandidate],
        decision: EvidenceDecision,
    ) -> list[RetrievalCandidate]:
        """Knowledge Refinement: Filters out irrelevant noise candidates based on evaluation.

        If the decision is CORRECT or AMBIGUOUS, returns candidates meeting minimum relevance.
        If INCORRECT and no retries remain, returns empty or best-effort candidates.
        """
        if not candidates:
            return []

        eval_map = {e.candidate_id: e for e in decision.candidate_evaluations}

        accepted: list[RetrievalCandidate] = []
        for cand in candidates:
            evaluation = eval_map.get(cand.candidate_id)
            if evaluation:
                # Discard candidates strictly below the lower threshold (noise filtering)
                if evaluation.relevance_score >= self.config.lower_threshold:
                    accepted.append(cand)
            else:
                accepted.append(cand)

        # Fallback: preserve at least the highest-ranking candidate if non-empty
        if not accepted and candidates and decision.label != "INCORRECT":
            accepted = [candidates[0]]

        return accepted
