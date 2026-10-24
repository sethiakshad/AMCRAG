"""Unified CRAG Controller for AMCRAG.

Serves as the Person 4 orchestrator interface:
Reranked Evidence -> Evaluator -> Decision -> Accepted Evidence / Reformulate Query.
"""

from typing import Sequence

from app.crag.correction import CorrectionConfig, QueryReformulator
from app.crag.decisions import CRAGDecisionEngine, DecisionConfig
from app.crag.evaluator import BaseCRAGEvaluator, HeuristicCRAGEvaluator
from app.schemas.crag import CRAGResult, EvidenceDecision
from app.schemas.retrieval import RetrievalCandidate


class CRAGController:
    """Coordinates evidence evaluation, decision policies, and query reformulation."""

    def __init__(
        self,
        evaluator: BaseCRAGEvaluator | None = None,
        decision_engine: CRAGDecisionEngine | None = None,
        reformulator: QueryReformulator | None = None,
        decision_config: DecisionConfig | None = None,
        correction_config: CorrectionConfig | None = None,
    ):
        self.evaluator = evaluator or HeuristicCRAGEvaluator()
        self.decision_engine = decision_engine or CRAGDecisionEngine(decision_config)
        self.reformulator = reformulator or QueryReformulator(correction_config)
        self.max_attempts = (
            correction_config.max_attempts if correction_config else 2
        )

    def process_candidates(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        attempt_number: int = 0,
    ) -> CRAGResult:
        """Main entry point for evaluating reranked candidates and deciding next action.

        Args:
            query: The user query (or active reformulated query).
            candidates: Ranked list of retrieval candidates from Person 3's reranker.
            attempt_number: Current retry index (0 = initial retrieval).

        Returns:
            CRAGResult package containing the decision, next query (if corrective),
            and filtered accepted candidates for context building.
        """
        # Step 1: Evaluate candidates
        evaluations = self.evaluator.evaluate_batch(query=query, candidates=candidates)

        # Step 2: Make system decision based on policy and thresholds
        decision: EvidenceDecision = self.decision_engine.decide(
            candidate_evaluations=evaluations,
            attempt_number=attempt_number,
            max_attempts=self.max_attempts,
        )

        # Step 3: Handle outcome
        if decision.needs_correction:
            # Trigger query reformulation
            next_query = self.reformulator.reformulate_query(
                original_query=query,
                candidates=candidates,
                decision=decision,
                attempt_number=attempt_number,
            )
            return CRAGResult(
                decision=decision,
                reformulated_query=next_query,
                accepted_candidates=[],
                can_proceed_to_generation=False,
                insufficient_evidence=False,
            )

        # Check if attempts are exhausted and evidence remains inadequate
        is_exhausted = attempt_number >= self.max_attempts and decision.label == "INCORRECT"

        # Step 4: Filter accepted evidence (Knowledge refinement)
        accepted = self.decision_engine.filter_accepted_candidates(
            candidates=candidates, decision=decision
        )

        return CRAGResult(
            decision=decision,
            reformulated_query=None,
            accepted_candidates=accepted,
            can_proceed_to_generation=not is_exhausted,
            insufficient_evidence=is_exhausted,
        )
