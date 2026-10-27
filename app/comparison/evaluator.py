"""evaluator.py — Deterministic, transparent evaluation engine for RAG comparative benchmarking.

Computes standard RAG metrics:
- Answer Correctness (Token F1 vs Ground Truth Reference)
- Faithfulness (Context Entailment / Grounding)
- Answer Relevancy (Question-Answer Alignment)
- Context Precision (Rank-weighted Signal-to-Noise Ratio)
- Context Recall (Coverage of Reference in Retrieved Context)
- Retrieval Quality (Recall@1, Recall@3, Recall@5, MRR, nDCG@5)
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.comparison.schemas import EvaluationQuestion, MetricScores, PipelineOutput

STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by", "of",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "it", "its", "that", "this", "these", "those", "which", "what", "who", "whom",
    "from", "as", "into", "about", "such", "than", "too", "very", "can", "could", "will",
    "would", "shall", "should", "not", "no", "yes", "so", "up", "out", "if", "then",
}

INSUFFICIENT_PATTERNS = [
    "insufficient evidence",
    "not contain enough information",
    "cannot be found",
    "does not mention",
    "no information",
    "not provided",
]


def _tokenize(text: str, remove_stopwords: bool = False) -> List[str]:
    """Tokenize and normalize text into lowercase alphanumeric words."""
    if not text:
        return []
    words = re.findall(r"\w+", text.lower())
    if remove_stopwords:
        words = [w for w in words if w not in STOPWORDS and len(w) > 1]
    return words


def _is_refusal_answer(answer: str) -> bool:
    """Check if the answer indicates inability to answer due to missing evidence."""
    ans_lower = answer.lower()
    return any(p in ans_lower for p in INSUFFICIENT_PATTERNS)


class RAGEvaluator:
    """Evaluates individual outputs and computes aggregate comparative metrics."""

    @staticmethod
    def evaluate_answer_correctness(
        candidate_answer: str,
        reference_answer: Optional[str],
    ) -> Optional[float]:
        """Compute Token F1 overlap between candidate answer and ground-truth reference.

        Returns None (N/A) if no reference answer was provided.
        """
        if reference_answer is None or not reference_answer.strip():
            return None

        # Check unanswerable / refusal parity
        ref_is_refusal = _is_refusal_answer(reference_answer)
        cand_is_refusal = _is_refusal_answer(candidate_answer)

        if ref_is_refusal:
            # If the question was genuinely unanswerable and the model refused, score 1.0 (correct)
            # If the model hallucinated an answer, score 0.0
            return 1.0 if cand_is_refusal else 0.0

        if cand_is_refusal and not ref_is_refusal:
            # Model refused when answer was present
            return 0.0

        cand_tokens = _tokenize(candidate_answer, remove_stopwords=True) or _tokenize(candidate_answer)
        ref_tokens = _tokenize(reference_answer, remove_stopwords=True) or _tokenize(reference_answer)

        if not cand_tokens or not ref_tokens:
            return 0.0

        cand_set = set(cand_tokens)
        ref_set = set(ref_tokens)

        shared = cand_set.intersection(ref_set)
        if not shared:
            return 0.0

        precision = len(shared) / len(cand_set)
        recall = len(shared) / len(ref_set)

        if precision + recall == 0:
            return 0.0

        f1 = 2 * (precision * recall) / (precision + recall)
        return round(min(1.0, f1), 4)

    @staticmethod
    def evaluate_faithfulness(
        candidate_answer: str,
        retrieved_evidence: List[Dict[str, Any]],
    ) -> float:
        """Measure what fraction of content tokens in the answer are grounded in evidence.

        A score of 1.0 means no ungrounded claims/entities are introduced.
        """
        if not candidate_answer or not candidate_answer.strip():
            return 0.0

        if _is_refusal_answer(candidate_answer):
            return 1.0

        # Build combined context tokens from all evidence
        context_corpus = " ".join(
            str(c.get("text", "")) for c in retrieved_evidence
        )
        context_tokens = set(_tokenize(context_corpus))

        ans_content_tokens = _tokenize(candidate_answer, remove_stopwords=True)
        if not ans_content_tokens:
            return 1.0

        grounded_count = sum(1 for t in ans_content_tokens if t in context_tokens)
        ratio = grounded_count / len(ans_content_tokens)
        return round(min(1.0, ratio), 4)

    @staticmethod
    def evaluate_answer_relevancy(
        question: str,
        candidate_answer: str,
    ) -> float:
        """Measure semantic and lexical alignment between question and generated answer."""
        if not candidate_answer or not candidate_answer.strip():
            return 0.0

        q_tokens = set(_tokenize(question, remove_stopwords=True))
        if not q_tokens:
            return 1.0

        ans_tokens = set(_tokenize(candidate_answer))

        # Check query term presence in answer
        overlap = q_tokens.intersection(ans_tokens)
        ratio = len(overlap) / len(q_tokens)

        # Scale reasonably between direct answers and refusals
        if _is_refusal_answer(candidate_answer):
            return 0.5  # Refusal addresses the question topic, but doesn't provide new details

        # Baseline bonus for non-empty direct answer
        score = 0.3 + 0.7 * ratio
        return round(min(1.0, score), 4)

    @staticmethod
    def evaluate_context_precision(
        question: str,
        reference_answer: Optional[str],
        retrieved_evidence: List[Dict[str, Any]],
    ) -> float:
        """Compute Mean Average Precision (MAP) of retrieved chunks.

        Evaluates if relevant chunks appear early in the retrieved ranking.
        """
        if not retrieved_evidence:
            return 0.0

        # Target terms from question and reference answer (if available)
        target_tokens = set(_tokenize(question, remove_stopwords=True))
        if reference_answer:
            target_tokens.update(_tokenize(reference_answer, remove_stopwords=True))

        if not target_tokens:
            return 1.0

        relevant_ranks: List[int] = []
        for i, chunk in enumerate(retrieved_evidence, start=1):
            chunk_tokens = set(_tokenize(str(chunk.get("text", ""))))
            overlap = target_tokens.intersection(chunk_tokens)
            # A chunk is considered relevant if it contains at least 2 key terms or 20% of target terms
            if len(overlap) >= min(2, len(target_tokens)):
                relevant_ranks.append(i)

        if not relevant_ranks:
            return 0.0

        # Calculate Mean Average Precision
        running_precisions = []
        for idx, rank in enumerate(relevant_ranks, start=1):
            precision_at_k = idx / rank
            running_precisions.append(precision_at_k)

        map_score = sum(running_precisions) / len(relevant_ranks)
        return round(min(1.0, map_score), 4)

    @staticmethod
    def evaluate_context_recall(
        reference_answer: Optional[str],
        retrieved_evidence: List[Dict[str, Any]],
    ) -> Optional[float]:
        """Compute proportion of reference answer entities found across all retrieved chunks."""
        if reference_answer is None or not reference_answer.strip():
            return None

        if _is_refusal_answer(reference_answer):
            return 1.0

        ref_tokens = set(_tokenize(reference_answer, remove_stopwords=True))
        if not ref_tokens:
            return 1.0

        all_context = " ".join(str(c.get("text", "")) for c in retrieved_evidence)
        context_tokens = set(_tokenize(all_context))

        recalled = ref_tokens.intersection(context_tokens)
        recall = len(recalled) / len(ref_tokens)
        return round(min(1.0, recall), 4)

    @staticmethod
    def evaluate_retrieval_metrics(
        expected_pages: Optional[List[int]],
        expected_keywords: Optional[List[str]],
        retrieved_evidence: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Compute Recall@1, Recall@3, Recall@5, MRR, and nDCG@5.

        Requires ground truth relevance labels (expected_pages or expected_keywords).
        If neither is provided, returns (None, None, None, None, None) representing N/A.
        """
        has_labels = bool(expected_pages) or bool(expected_keywords)
        if not has_labels:
            return None, None, None, None, None

        if not retrieved_evidence:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        expected_pages_set = set(expected_pages or [])
        expected_keywords_clean = [k.lower() for k in (expected_keywords or [])]

        relevance_flags: List[bool] = []
        for chunk in retrieved_evidence:
            is_rel = False
            # Page match check
            chunk_page = chunk.get("page") or chunk.get("page_start") or chunk.get("page_number")
            if chunk_page is not None and chunk_page in expected_pages_set:
                is_rel = True

            # Keyword match check
            chunk_text = str(chunk.get("text", "")).lower()
            if expected_keywords_clean and any(kw in chunk_text for kw in expected_keywords_clean):
                is_rel = True

            relevance_flags.append(is_rel)

        # Recall@k (is there any relevant item in top-k)
        rec_1 = 1.0 if (len(relevance_flags) >= 1 and any(relevance_flags[:1])) else 0.0
        rec_3 = 1.0 if (len(relevance_flags) >= 1 and any(relevance_flags[:3])) else 0.0
        rec_5 = 1.0 if (len(relevance_flags) >= 1 and any(relevance_flags[:5])) else 0.0

        # Mean Reciprocal Rank (MRR)
        mrr = 0.0
        for rank, is_rel in enumerate(relevance_flags, start=1):
            if is_rel:
                mrr = 1.0 / rank
                break

        # nDCG@5
        dcg = 0.0
        for rank, is_rel in enumerate(relevance_flags[:5], start=1):
            rel_score = 1.0 if is_rel else 0.0
            dcg += rel_score / math.log2(rank + 1)

        # Ideal DCG for 1 relevant item is 1 / log2(2) = 1.0
        idcg = 1.0
        ndcg_5 = round(min(1.0, dcg / idcg), 4)

        return rec_1, rec_3, rec_5, round(mrr, 4), ndcg_5

    @classmethod
    def evaluate_output(
        cls,
        question: EvaluationQuestion,
        output: PipelineOutput,
    ) -> MetricScores:
        """Calculate complete metric scores for a single system's pipeline output."""
        correctness = cls.evaluate_answer_correctness(
            candidate_answer=output.answer,
            reference_answer=question.reference_answer,
        )
        faithfulness = cls.evaluate_faithfulness(
            candidate_answer=output.answer,
            retrieved_evidence=output.retrieved_evidence,
        )
        relevancy = cls.evaluate_answer_relevancy(
            question=question.question,
            candidate_answer=output.answer,
        )
        ctx_precision = cls.evaluate_context_precision(
            question=question.question,
            reference_answer=question.reference_answer,
            retrieved_evidence=output.retrieved_evidence,
        )
        ctx_recall = cls.evaluate_context_recall(
            reference_answer=question.reference_answer,
            retrieved_evidence=output.retrieved_evidence,
        )
        rec_1, rec_3, rec_5, mrr, ndcg_5 = cls.evaluate_retrieval_metrics(
            expected_pages=question.expected_pages,
            expected_keywords=question.expected_keywords,
            retrieved_evidence=output.retrieved_evidence,
        )

        return MetricScores(
            answer_correctness=correctness,
            faithfulness=faithfulness,
            answer_relevancy=relevancy,
            context_precision=ctx_precision,
            context_recall=ctx_recall,
            recall_at_1=rec_1,
            recall_at_3=rec_3,
            recall_at_5=rec_5,
            mrr=mrr,
            ndcg_at_5=ndcg_5,
        )
