"""Unit and integration tests for Person 4 CRAG module."""

import pytest

from app.crag.controller import CRAGController
from app.crag.correction import CorrectionConfig, QueryReformulator
from app.crag.decisions import CRAGDecisionEngine, DecisionConfig
from app.crag.evaluator import HeuristicCRAGEvaluator
from app.schemas.crag import (
    AmbiguousPolicy,
    CandidateEvaluation,
    EvidenceDecision,
)
from app.schemas.retrieval import RetrievalCandidate


@pytest.fixture
def sample_text_candidate() -> RetrievalCandidate:
    return RetrievalCandidate(
        candidate_id="cand_chunk_001",
        document_id="doc_report_2025",
        source_filename="annual_report_2025.pdf",
        page_start=12,
        page_end=12,
        candidate_type="text_chunk",
        text="The company revenue increased by 25% year-over-year reaching 1.2 billion USD.",
        page_reference=None,
        retrieval_method="dense",
        retrieval_rank=1,
        retrieval_score=0.88,
        metadata={"section": "Financial Highlights"},
    )


@pytest.fixture
def sample_visual_candidate() -> RetrievalCandidate:
    return RetrievalCandidate(
        candidate_id="cand_page_008",
        document_id="doc_report_2025",
        source_filename="annual_report_2025.pdf",
        page_start=8,
        page_end=8,
        candidate_type="visual_page",
        text=None,
        page_reference="artifacts/pages/doc_report_2025_p8.png",
        retrieval_method="colpali",
        retrieval_rank=2,
        retrieval_score=0.74,
        metadata={"caption": "Figure 3: Revenue breakdown chart by operating segment"},
    )


class TestCandidateSchema:
    def test_text_candidate_evaluable_content(self, sample_text_candidate):
        assert "revenue increased by 25%" in sample_text_candidate.get_evaluable_content()

    def test_visual_candidate_evaluable_content(self, sample_visual_candidate):
        content = sample_visual_candidate.get_evaluable_content()
        assert "Figure 3: Revenue breakdown" in content
        assert "page 8" in content


class TestCRAGDecisionEngine:
    def test_decide_correct_evidence(self):
        engine = CRAGDecisionEngine(DecisionConfig(upper_threshold=0.65, lower_threshold=0.30))
        evals = [
            CandidateEvaluation(candidate_id="c1", relevance_score=0.85, is_relevant=True),
            CandidateEvaluation(candidate_id="c2", relevance_score=0.40, is_relevant=False),
        ]
        decision = engine.decide(evals, attempt_number=0)
        assert decision.label == "CORRECT"
        assert decision.needs_correction is False
        assert decision.score >= 0.65

    def test_decide_incorrect_evidence_triggers_correction(self):
        engine = CRAGDecisionEngine(DecisionConfig(upper_threshold=0.65, lower_threshold=0.30))
        evals = [
            CandidateEvaluation(candidate_id="c1", relevance_score=0.20, is_relevant=False),
            CandidateEvaluation(candidate_id="c2", relevance_score=0.15, is_relevant=False),
        ]
        decision = engine.decide(evals, attempt_number=0, max_attempts=2)
        assert decision.label == "INCORRECT"
        assert decision.needs_correction is True

    def test_decide_incorrect_at_max_attempts_stops(self):
        engine = CRAGDecisionEngine(DecisionConfig(upper_threshold=0.65, lower_threshold=0.30))
        evals = [
            CandidateEvaluation(candidate_id="c1", relevance_score=0.20, is_relevant=False),
        ]
        # At attempt 2 (max_attempts = 2), retry must NOT be triggered
        decision = engine.decide(evals, attempt_number=2, max_attempts=2)
        assert decision.label == "INCORRECT"
        assert decision.needs_correction is False
        assert "Retry limit reached" in decision.explanation

    def test_ambiguous_policy_retry_once(self):
        engine = CRAGDecisionEngine(
            DecisionConfig(
                upper_threshold=0.70,
                lower_threshold=0.30,
                ambiguous_policy=AmbiguousPolicy.RETRY_ONCE,
            )
        )
        evals = [CandidateEvaluation(candidate_id="c1", relevance_score=0.50, is_relevant=True)]

        # Attempt 0: Should retry once
        decision_0 = engine.decide(evals, attempt_number=0, max_attempts=2)
        assert decision_0.label == "AMBIGUOUS"
        assert decision_0.needs_correction is True

        # Attempt 1: Should now proceed with qualification
        decision_1 = engine.decide(evals, attempt_number=1, max_attempts=2)
        assert decision_1.label == "AMBIGUOUS"
        assert decision_1.needs_correction is False

    def test_ambiguous_policy_accept_immediately(self):
        engine = CRAGDecisionEngine(
            DecisionConfig(
                upper_threshold=0.70,
                lower_threshold=0.30,
                ambiguous_policy=AmbiguousPolicy.ACCEPT_WITH_QUALIFICATION,
            )
        )
        evals = [CandidateEvaluation(candidate_id="c1", relevance_score=0.50, is_relevant=True)]
        decision = engine.decide(evals, attempt_number=0, max_attempts=2)
        assert decision.label == "AMBIGUOUS"
        assert decision.needs_correction is False


class TestQueryReformulator:
    def test_clean_conversational_prefixes(self):
        reformulator = QueryReformulator()
        cleaned = reformulator._clean_query("Can you please tell me what is the company revenue?")
        assert cleaned == "the company revenue"

    def test_detect_visual_intent(self):
        reformulator = QueryReformulator()
        assert reformulator._detect_visual_intent("Which figure compares model latency?") is True
        assert reformulator._detect_visual_intent("Show table 4 details") is True
        assert reformulator._detect_visual_intent("Explain the attention mechanism") is False

    def test_cycle_avoidance(self, sample_text_candidate):
        reformulator = QueryReformulator()
        query = "What is the revenue growth?"
        decision = EvidenceDecision(label="INCORRECT", score=0.1, needs_correction=True)

        ref_1 = reformulator.reformulate_query(query, [sample_text_candidate], decision, 0)
        ref_2 = reformulator.reformulate_query(query, [sample_text_candidate], decision, 1)

        # Ensure subsequent reformulations never yield the exact same query
        assert ref_1 != query
        assert ref_2 != ref_1
        assert ref_2 != query


class TestCRAGControllerIntegration:
    def test_initial_poor_retrieval_triggers_reformulation(self):
        controller = CRAGController()
        query = "Can you tell me what is the net income in 2025?"
        poor_candidate = RetrievalCandidate(
            candidate_id="c_unrelated",
            document_id="doc_1",
            source_filename="doc.pdf",
            candidate_type="text_chunk",
            text="The acknowledgements section thanks all university faculty members.",
            retrieval_method="bm25",
            retrieval_score=0.10,
        )

        result = controller.process_candidates(query, [poor_candidate], attempt_number=0)

        assert result.can_proceed_to_generation is False
        assert result.decision.label == "INCORRECT"
        assert result.decision.needs_correction is True
        assert result.reformulated_query is not None
        assert "net income" in result.reformulated_query

    def test_successful_retrieval_proceeds(self, sample_text_candidate):
        controller = CRAGController()
        query = "What was the revenue increase and USD total?"

        result = controller.process_candidates(query, [sample_text_candidate], attempt_number=1)

        assert result.can_proceed_to_generation is True
        assert result.decision.label == "CORRECT"
        assert result.decision.needs_correction is False
        assert result.reformulated_query is None
        assert len(result.accepted_candidates) == 1
        assert result.accepted_candidates[0].candidate_id == "cand_chunk_001"

    def test_exhausted_retries_flags_insufficient_evidence(self):
        controller = CRAGController(decision_config=DecisionConfig(lower_threshold=0.30))
        poor_candidate = RetrievalCandidate(
            candidate_id="c_unrelated",
            document_id="doc_1",
            source_filename="doc.pdf",
            candidate_type="text_chunk",
            text="Unrelated text passage about completely different topic.",
            retrieval_method="dense",
            retrieval_score=0.05,
        )

        # Attempt 2 is max_attempts
        result = controller.process_candidates("Query", [poor_candidate], attempt_number=2)

        assert result.can_proceed_to_generation is False
        assert result.insufficient_evidence is True
        assert result.decision.needs_correction is False
