"""CRAG Evidence Evaluator base classes and scoring engines.

Follows Sections 4.7, 6.1, 8.3, and 10.4 of AMCRAG Central Project Documentation.
"""

from abc import ABC, abstractmethod
import re
from typing import Sequence

from app.schemas.crag import CandidateEvaluation
from app.schemas.retrieval import RetrievalCandidate


class BaseCRAGEvaluator(ABC):
    """Abstract interface for evaluating candidate relevance against a query."""

    @abstractmethod
    def evaluate_candidate(
        self, query: str, candidate: RetrievalCandidate
    ) -> CandidateEvaluation:
        """Evaluates an individual candidate against the query and returns a score in [0.0, 1.0]."""
        pass

    def evaluate_batch(
        self, query: str, candidates: Sequence[RetrievalCandidate]
    ) -> list[CandidateEvaluation]:
        """Evaluates a batch of candidates. Can be overridden for vectorized GPU inference."""
        return [self.evaluate_candidate(query, cand) for cand in candidates]


class HeuristicCRAGEvaluator(BaseCRAGEvaluator):
    """Lightweight reference evaluator based on candidate relevance scores and lexical overlap.

    Used for unit testing, offline development, and baseline benchmarking without requiring
    heavy PyTorch model downloads.
    """

    def evaluate_candidate(
        self, query: str, candidate: RetrievalCandidate
    ) -> CandidateEvaluation:
        content = candidate.get_evaluable_content().lower()
        query_terms = set(re.findall(r"\w+", query.lower()))

        if not query_terms:
            overlap_ratio = 0.0
        else:
            matches = sum(1 for term in query_terms if term in content)
            overlap_ratio = matches / len(query_terms)

        # Combine candidate retrieval/reranker score with lexical overlap
        base_score = candidate.retrieval_score if candidate.retrieval_score is not None else 0.5
        # Normalize base_score if it came from a reranker (e.g. sigmoid or bounded)
        if base_score > 1.0:
            base_score = min(base_score / 10.0, 1.0)
        elif base_score < 0.0:
            base_score = max(0.0, (base_score + 10.0) / 20.0)

        # Composite score
        relevance_score = round(0.5 * base_score + 0.5 * overlap_ratio, 4)
        is_relevant = relevance_score >= 0.5

        # Split content into sentences/strips for CRAG knowledge refinement
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", content) if len(s.strip()) > 15]
        relevant_strips = [s for s in sentences if any(term in s for term in query_terms)][:3]

        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            relevance_score=relevance_score,
            is_relevant=is_relevant,
            extracted_strips=relevant_strips,
            notes=f"Lexical overlap: {overlap_ratio:.2f}, retriever score: {base_score:.2f}",
        )


class T5CRAGEvaluator(BaseCRAGEvaluator):
    """Fine-tuned T5-Large CRAG Evaluator.

    Checkpoint selection (HuggingFace vs Husky official GitHub repo) will be configured
    upon confirmation with the user.
    """

    def __init__(self, model_path_or_id: str | None = None, device: str = "cpu"):
        self.model_path_or_id = model_path_or_id
        self.device = device
        self._is_loaded = False

    def load_model(self) -> None:
        """Loads model weights and tokenizer once checkpoint source is chosen."""
        raise NotImplementedError(
            "T5 checkpoint configuration pending user decision between "
            "Hugging Face (Mindie/CRAG-Evaluator) or Husky official repo weights."
        )

    def evaluate_candidate(
        self, query: str, candidate: RetrievalCandidate
    ) -> CandidateEvaluation:
        if not self._is_loaded:
            self.load_model()
        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            relevance_score=0.0,
            is_relevant=False,
            notes="T5 evaluation placeholder",
        )
