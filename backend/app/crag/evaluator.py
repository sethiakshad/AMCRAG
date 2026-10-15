"""CRAG Evidence Evaluator base classes and scoring engines.

Follows Sections 4.7, 6.1, 8.3, and 10.4 of AMCRAG Central Project Documentation.
"""

from abc import ABC, abstractmethod
import logging
import os
import re
from typing import Sequence

from app.schemas.crag import CandidateEvaluation
from app.schemas.retrieval import RetrievalCandidate

logger = logging.getLogger(__name__)

# Prevent Intel OpenMP initialization conflict on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


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
            notes=f"Heuristic scoring: lexical overlap {overlap_ratio:.2f}, retriever score {base_score:.2f}",
        )


class T5CRAGEvaluator(BaseCRAGEvaluator):
    """Fine-tuned T5-Large CRAG Evaluator.

    Integrates Hugging Face 'Mindie/CRAG-Evaluator' with support for local weights
    (e.g. from the official HuskyInSalt/CRAG repository) and automatic hardware device selection.
    """

    DEFAULT_MODEL_ID = "Mindie/CRAG-Evaluator"

    def __init__(
        self,
        model_path_or_id: str | None = None,
        device: str | None = None,
        max_length: int = 512,
        fallback_on_error: bool = True,
    ):
        self.model_path_or_id = model_path_or_id or os.getenv(
            "CRAG_EVALUATOR_PATH", self.DEFAULT_MODEL_ID
        )
        self.max_length = max_length
        self.fallback_on_error = fallback_on_error
        self._fallback_evaluator = HeuristicCRAGEvaluator()

        self._device = device
        self.tokenizer = None
        self.model = None
        self._is_loaded = False
        self._is_seq2seq = False

    @property
    def device(self) -> str:
        if self._device:
            return self._device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def load_model(self) -> None:
        """Loads model weights and tokenizer from Hugging Face or local path."""
        if self._is_loaded:
            return

        try:
            import torch
            from transformers import (
                AutoModelForSeq2SeqLM,
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            logger.info("Loading CRAG Evaluator model from '%s' on device '%s'...", self.model_path_or_id, self.device)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path_or_id)

            try:
                # First try SequenceClassification (typical for scoring heads)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    self.model_path_or_id
                )
                self._is_seq2seq = False
            except Exception:
                # Fallback to Seq2SeqLM (standard T5 conditional generation)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_path_or_id
                )
                self._is_seq2seq = True

            self.model.to(self.device)
            self.model.eval()
            self._is_loaded = True
            logger.info("CRAG Evaluator loaded successfully.")

        except Exception as e:
            logger.error("Failed to load T5 CRAG model '%s': %s", self.model_path_or_id, e)
            if self.fallback_on_error:
                logger.warning("Defaulting to HeuristicCRAGEvaluator fallback.")
                self._is_loaded = False
            else:
                raise

    def evaluate_candidate(
        self, query: str, candidate: RetrievalCandidate
    ) -> CandidateEvaluation:
        results = self.evaluate_batch(query=query, candidates=[candidate])
        return results[0]

    def evaluate_batch(
        self, query: str, candidates: Sequence[RetrievalCandidate]
    ) -> list[CandidateEvaluation]:
        """Performs batch evaluation using the fine-tuned T5 evaluator."""
        if not candidates:
            return []

        if not self._is_loaded:
            try:
                self.load_model()
            except Exception:
                pass

        # If model failed to load and fallback is enabled, use heuristic
        if not self._is_loaded:
            return self._fallback_evaluator.evaluate_batch(query, candidates)

        try:
            import torch

            input_texts = [
                f"query: {query} document: {cand.get_evaluable_content()}"
                for cand in candidates
            ]

            inputs = self.tokenizer(
                input_texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                if hasattr(outputs, "logits"):
                    logits = outputs.logits
                    if logits.dim() == 2:
                        # Softmax over 2 classes (irrelevant / relevant)
                        if logits.shape[1] >= 2:
                            probs = torch.softmax(logits, dim=-1)[:, 1]
                        else:
                            probs = torch.sigmoid(logits.squeeze(-1))
                    elif logits.dim() == 3:
                        # Seq2Seq first token logits
                        first_token_logits = logits[:, 0, :]
                        probs = torch.softmax(first_token_logits, dim=-1).max(dim=-1).values
                    else:
                        probs = torch.ones(len(candidates)) * 0.5
                    scores = probs.cpu().tolist()
                else:
                    scores = [0.5] * len(candidates)

            evaluations: list[CandidateEvaluation] = []
            for cand, score in zip(candidates, scores):
                norm_score = max(0.0, min(1.0, float(score)))
                content = cand.get_evaluable_content()
                sentences = [s.strip() for s in re.split(r"[.!?\n]+", content) if len(s.strip()) > 15]
                query_terms = set(re.findall(r"\w+", query.lower()))
                strips = [s for s in sentences if any(t in s.lower() for t in query_terms)][:3]

                evaluations.append(
                    CandidateEvaluation(
                        candidate_id=cand.candidate_id,
                        relevance_score=round(norm_score, 4),
                        is_relevant=norm_score >= 0.5,
                        extracted_strips=strips,
                        notes=f"T5 CRAG model confidence: {norm_score:.4f}",
                    )
                )
            return evaluations

        except Exception as e:
            logger.error("Inference error with T5 CRAG evaluator: %s", e)
            if self.fallback_on_error:
                return self._fallback_evaluator.evaluate_batch(query, candidates)
            raise
