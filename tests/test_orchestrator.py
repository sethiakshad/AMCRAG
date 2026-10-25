"""test_orchestrator.py — Unit & Integration Tests for Milestone 3 (RAGOrchestrator).

Verifies:
  - Intent classification (text vs visual)
  - End-to-end query execution with CRAG evaluation
  - Query reformulation and bounded retry loops (cycle detection)
  - Safe-halt on insufficient evidence
  - Streaming token emissions
  - Subsystem fault tolerance when retriever raises exceptions
"""

import pytest

from app.context_builder.schemas import ModelModality
from app.schemas.api import QueryRequest, QueryResponse
from app.schemas.crag import CandidateEvaluation, CRAGResult, EvidenceDecision
from app.schemas.retrieval import RetrievalCandidate
from app.services.generator import INSUFFICIENT_EVIDENCE_ANSWER
from app.services.orchestrator import OrchestratorConfig, RAGOrchestrator


class MockRetriever:
    """Mock retriever that simulates dynamic candidate responses for testing."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_count = 0
        self.last_query = None

    def retrieve(self, query: str, top_k: int = 5, **kwargs):
        self.call_count += 1
        self.last_query = query
        if query in self.responses:
            return self.responses[query]
        # Default mock candidate
        return [
            RetrievalCandidate(
                candidate_id=f"c_{self.call_count}",
                document_id="doc1",
                source_filename="doc1.pdf",
                page_start=1,
                page_end=1,
                candidate_type="text_chunk",
                text=f"Default relevant content for query: {query}",
                retrieval_method="hybrid",
                retrieval_rank=1,
                retrieval_score=0.92,
            )
        ]


class MockCRAGController:
    """Mock CRAG controller for fine-grained testing of decision outcomes."""

    def __init__(self, sequence=None):
        self.sequence = sequence or []
        self.call_count = 0

    def process_candidates(self, query: str, candidates, attempt_number: int = 0):
        if self.call_count < len(self.sequence):
            res = self.sequence[self.call_count]
            self.call_count += 1
            return res
        # Default: accept all candidates
        decision = EvidenceDecision(
            label="CORRECT",
            score=0.90,
            needs_correction=False,
            candidate_evaluations=[
                CandidateEvaluation(
                    candidate_id=c.candidate_id,
                    relevance_score=0.95,
                    is_relevant=True,
                )
                for c in candidates
            ],
        )
        return CRAGResult(
            decision=decision,
            reformulated_query=None,
            accepted_candidates=list(candidates),
            can_proceed_to_generation=True,
            insufficient_evidence=False,
        )


# =============================================================================
# TESTS
# =============================================================================

class TestRAGOrchestrator:
    """Test suite for Milestone 3 RAGOrchestrator."""

    def test_intent_classification(self):
        orchestrator = RAGOrchestrator()

        # Visual keywords
        assert orchestrator.analyze_query_intent("Show me the revenue growth chart.") == ModelModality.VISION
        assert orchestrator.analyze_query_intent("What is shown in the figure on page 5?") == ModelModality.VISION
        assert orchestrator.analyze_query_intent("Summarize the balance sheet table.") == ModelModality.VISION

        # Factual textual queries
        assert orchestrator.analyze_query_intent("What is the definition of equity?") == ModelModality.TEXT
        assert orchestrator.analyze_query_intent("Who is the fund manager?") == ModelModality.TEXT

    @pytest.mark.anyio
    async def test_end_to_end_query_fast_path_correct(self):
        mock_retriever = MockRetriever()
        orchestrator = RAGOrchestrator(retriever=mock_retriever)

        req = QueryRequest(query="What is the lock-in period for ELSS?", top_k=3)
        response = await orchestrator.query(req)

        assert isinstance(response, QueryResponse)
        assert response.query == "What is the lock-in period for ELSS?"
        assert response.retrieval_attempts == 1
        assert response.crag_decision == "CORRECT"
        assert len(response.sources) > 0
        assert response.sources[0].evidence_id == "E1"
        assert "[E1]" in response.answer
        assert response.latency.total_ms > 0
        assert response.latency.retrieval_ms > 0

    @pytest.mark.anyio
    async def test_crag_reformulation_and_retry_loop(self):
        # Scenario: attempt 0 returns INCORRECT -> reformulates -> attempt 1 returns CORRECT
        attempt_0_result = CRAGResult(
            decision=EvidenceDecision(
                label="INCORRECT",
                score=0.20,
                needs_correction=True,
            ),
            reformulated_query="ELSS tax benefit section 80C",
            accepted_candidates=[],
            can_proceed_to_generation=False,
            insufficient_evidence=False,
        )
        attempt_1_result = CRAGResult(
            decision=EvidenceDecision(
                label="CORRECT",
                score=0.88,
                needs_correction=False,
            ),
            reformulated_query=None,
            accepted_candidates=[
                RetrievalCandidate(
                    candidate_id="c_reform",
                    document_id="doc1",
                    source_filename="doc1.pdf",
                    page_start=2,
                    page_end=2,
                    candidate_type="text_chunk",
                    text="ELSS provides tax deduction under 80C with 3-year lock-in.",
                    retrieval_method="hybrid",
                    retrieval_rank=1,
                    retrieval_score=0.91,
                )
            ],
            can_proceed_to_generation=True,
            insufficient_evidence=False,
        )

        mock_crag = MockCRAGController(sequence=[attempt_0_result, attempt_1_result])
        mock_retriever = MockRetriever()
        orchestrator = RAGOrchestrator(
            retriever=mock_retriever,
            crag_controller=mock_crag,
        )

        req = QueryRequest(query="ELSS?")
        response = await orchestrator.query(req)

        assert response.retrieval_attempts == 2
        assert mock_retriever.call_count == 2
        assert mock_retriever.last_query == "ELSS tax benefit section 80C"
        assert response.crag_decision == "CORRECT"
        assert len(response.sources) == 1
        assert "[E1]" in response.answer

    @pytest.mark.anyio
    async def test_cycle_detection_stops_loop(self):
        # Scenario: Reformulator proposes query identical to initial query
        cycle_result = CRAGResult(
            decision=EvidenceDecision(
                label="INCORRECT",
                score=0.10,
                needs_correction=True,
            ),
            reformulated_query="What is ELSS?",  # Identical to original query
            accepted_candidates=[],
            can_proceed_to_generation=False,
            insufficient_evidence=False,
        )
        mock_crag = MockCRAGController(sequence=[cycle_result])
        orchestrator = RAGOrchestrator(
            retriever=MockRetriever(),
            crag_controller=mock_crag,
        )

        req = QueryRequest(query="What is ELSS?")
        response = await orchestrator.query(req)

        # Loop must terminate immediately without repeating identical query
        assert response.insufficient_evidence is True
        assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER
        assert response.retrieval_attempts == 1

    @pytest.mark.anyio
    async def test_insufficient_evidence_halts_generation(self):
        # Scenario: Retries exhausted and evidence remains incorrect
        exhausted_result = CRAGResult(
            decision=EvidenceDecision(
                label="INCORRECT",
                score=0.05,
                needs_correction=False,
            ),
            reformulated_query=None,
            accepted_candidates=[],
            can_proceed_to_generation=False,
            insufficient_evidence=True,
        )
        mock_crag = MockCRAGController(sequence=[exhausted_result])
        orchestrator = RAGOrchestrator(
            retriever=MockRetriever(),
            crag_controller=mock_crag,
        )

        req = QueryRequest(query="Unanswerable physics question")
        response = await orchestrator.query(req)

        assert response.insufficient_evidence is True
        assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER
        assert response.sources == []

    @pytest.mark.anyio
    async def test_streaming_query(self):
        mock_retriever = MockRetriever()
        orchestrator = RAGOrchestrator(retriever=mock_retriever)

        req = QueryRequest(query="What is the lock-in period?")
        events = []
        async for event in orchestrator.query_stream(req):
            events.append(event)

        assert any(e["event"] == "metadata" for e in events)
        assert any(e["event"] == "token" for e in events)
        assert events[-1]["event"] == "done"

        tokens = [e["data"] for e in events if e["event"] == "token"]
        full_text = "".join(tokens)
        assert "[E1]" in full_text

    @pytest.mark.anyio
    async def test_subsystem_fault_tolerance_when_retriever_fails(self):
        class FailingRetriever:
            def retrieve(self, *args, **kwargs):
                raise ConnectionError("Qdrant connection refused")

        orchestrator = RAGOrchestrator(retriever=FailingRetriever())
        req = QueryRequest(query="Will this crash the backend?")
        # Must not raise 500 / unhandled exception
        response = await orchestrator.query(req)
        assert isinstance(response, QueryResponse)
        assert response.insufficient_evidence is True
        assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER
