"""CRAG Evidence Evaluator base classes and scoring engines.

Follows Sections 4.7, 6.1, 8.3, and 10.4 of AMCRAG Central Project Documentation.
"""

from abc import ABC, abstractmethod
import logging
import math
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

    STOPWORDS = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
        "are", "as", "at", "be", "because", "been", "before", "being", "below", "between",
        "both", "but", "by", "can", "could", "did", "do", "does", "doing", "down", "during",
        "each", "few", "for", "from", "further", "had", "has", "have", "having", "he", "her",
        "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into",
        "is", "it", "its", "itself", "me", "more", "most", "my", "myself", "no", "nor", "not",
        "of", "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out",
        "over", "own", "same", "she", "should", "so", "some", "such", "than", "that", "the",
        "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this",
        "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were",
        "what", "when", "where", "which", "while", "who", "whom", "why", "with", "you", "your",
        "yours", "yourself", "yourselves", "tell", "acc", "according"
    }

    def _evaluate_visual_candidate(
        self, query: str, candidate: RetrievalCandidate
    ) -> CandidateEvaluation:
        """Evaluates visual page candidate using calibrated visual retrieval scores and optional OCR text.

        Distinguishes raw ColPali MaxSim score vs. RRF fused score vs. CRAG confidence.
        Does not penalize pure visual candidates (diagrams, scans) lacking OCR text.
        """
        meta = getattr(candidate, "metadata", {}) or {}

        # 1. Distinguish original visual retrieval score vs fused ranking score
        colpali_score = meta.get("colpali_score")
        if colpali_score is None and getattr(candidate, "retrieval_method", "") == "colpali":
            colpali_score = candidate.retrieval_score

        raw_score = candidate.retrieval_score if candidate.retrieval_score is not None else 0.5
        rank = getattr(candidate, "retrieval_rank", meta.get("colpali_rank", 1))

        # 2. Calibrate visual evidence score to CRAG confidence [0.0, 1.0]
        if colpali_score is not None:
            cs = float(colpali_score)
            if cs > 1.0:
                # Unnormalized multi-vector MaxSim sum (typically 2.0 to 30.0)
                if cs <= 3.5:
                    base_score = max(0.10, 0.10 + (cs / 3.5) * 0.18)  # [0.10, 0.28] -> INCORRECT (< 0.30)
                elif cs < 8.0:
                    base_score = 0.30 + ((cs - 3.5) / 4.5) * 0.34    # [0.30, 0.64] -> AMBIGUOUS
                elif cs <= 22.0:
                    base_score = 0.65 + min(1.0, (cs - 8.0) / 14.0) * 0.23  # [0.65, 0.88] -> CORRECT (>= 0.65)
                else:
                    base_score = min(0.96, 0.88 + ((cs - 22.0) / 18.0) * 0.08)
            else:
                # Normalized Cosine MaxSim average (0.0 to 1.0)
                if cs < 0.25:
                    base_score = max(0.10, 0.10 + (cs / 0.25) * 0.18)  # [0.10, 0.28] -> INCORRECT (< 0.30)
                elif cs < 0.45:
                    base_score = 0.30 + ((cs - 0.25) / 0.20) * 0.34    # [0.30, 0.64] -> AMBIGUOUS
                elif cs <= 0.75:
                    base_score = 0.65 + min(1.0, (cs - 0.45) / 0.30) * 0.23  # [0.65, 0.88] -> CORRECT (>= 0.65)
                else:
                    base_score = min(0.96, 0.88 + ((cs - 0.75) / 0.25) * 0.08)
        elif 0.0 < raw_score <= 0.08:
            # Fused RRF score without explicit colpali_score in metadata
            if raw_score >= 0.030:
                # Multi-retriever agreement (fused text + vision)
                base_score = min(0.90, 0.75 + (raw_score - 0.030) * 5.0)
            elif rank == 1 or raw_score >= 0.0163:
                base_score = 0.68  # Passes CORRECT gate (>= 0.65)
            elif rank == 2 or raw_score >= 0.0160:
                base_score = 0.58  # AMBIGUOUS
            else:
                base_score = max(0.20, 0.48 - (rank - 2) * 0.08)
        else:
            base_score = max(0.0, min(1.0, raw_score))

        # 3. Optional OCR textual evidence blending (do not penalize if OCR is absent)
        ocr_text = meta.get("ocr_text", "")
        content_text = getattr(candidate, "text", "") or ""
        substantive_text = ""
        if ocr_text and len(ocr_text.strip()) > 15:
            substantive_text = ocr_text.strip()
        elif content_text and not content_text.strip().startswith("[Visual Page") and not content_text.strip().startswith("Visual page "):
            substantive_text = content_text.strip()

        overlap_ratio = 0.0
        extracted_strips = []
        if substantive_text:
            all_terms = re.findall(r"\w+", query.lower())
            meaningful_terms = [t for t in all_terms if t not in self.STOPWORDS and len(t) > 1]
            eval_terms = set(meaningful_terms) if meaningful_terms else set(all_terms)
            if eval_terms:
                matches = sum(1 for term in eval_terms if term in substantive_text.lower())
                overlap_ratio = matches / len(eval_terms)
                sentences = [s.strip() for s in re.split(r"[.!?\n]+", substantive_text) if len(s.strip()) > 10]
                extracted_strips = [s for s in sentences if any(term in s.lower() for term in eval_terms)][:3]

        if substantive_text and overlap_ratio > 0.0:
            boosted = max(base_score, 0.70 * base_score + 0.30 * overlap_ratio)
            final_score = round(min(1.0, boosted + 0.05 * overlap_ratio), 4)
            notes = f"Visual scoring: calibrated visual score {base_score:.2f}, OCR text overlap {overlap_ratio:.2f}"
        else:
            final_score = round(base_score, 4)
            notes = f"Visual scoring: calibrated visual score {base_score:.2f} (modality=visual_page)"

        page_num = getattr(candidate, "page_start", 1) or getattr(candidate, "page_number", 1)
        src_file = getattr(candidate, "source_filename", "document.pdf")
        if not extracted_strips:
            extracted_strips = [f"Visual evidence from page {page_num} of {src_file}"]

        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            relevance_score=final_score,
            is_relevant=final_score >= 0.50,
            extracted_strips=extracted_strips,
            notes=notes,
        )

    def evaluate_candidate(
        self, query: str, candidate: RetrievalCandidate
    ) -> CandidateEvaluation:
        # Route visual candidates directly to visual evidence evaluator
        is_visual = (
            getattr(candidate, "candidate_type", "") == "visual_page"
            or getattr(candidate, "modality", "") == "visual_page"
            or (getattr(candidate, "metadata", {}) or {}).get("modality") == "visual_page"
        )
        if is_visual:
            return self._evaluate_visual_candidate(query, candidate)

        content = candidate.get_evaluable_content().lower()
        all_terms = re.findall(r"\w+", query.lower())
        meaningful_terms = [t for t in all_terms if t not in self.STOPWORDS and len(t) > 1]
        eval_terms = set(meaningful_terms) if meaningful_terms else set(all_terms)

        if not eval_terms:
            overlap_ratio = 0.0
        else:
            matches = sum(1 for term in eval_terms if term in content)
            overlap_ratio = matches / len(eval_terms)

        # Combine candidate retrieval/reranker score with lexical overlap
        raw_score = candidate.retrieval_score if candidate.retrieval_score is not None else 0.5

        if 0.0 < raw_score <= 0.08:
            base_score = min(1.0, 0.50 + (raw_score / 0.033) * 0.45)
        elif raw_score > 1.0:
            base_score = min(raw_score / 10.0, 1.0)
        elif raw_score < 0.0:
            base_score = max(0.0, (raw_score + 10.0) / 20.0)
        else:
            base_score = raw_score

        relevance_score = round(0.4 * base_score + 0.6 * overlap_ratio, 4)
        is_relevant = relevance_score >= 0.5
        notes = f"Heuristic scoring: lexical overlap {overlap_ratio:.2f}, calibrated retriever score {base_score:.2f}"
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", content) if len(s.strip()) > 15]
        relevant_strips = [s for s in sentences if any(term in s for term in eval_terms)][:3]

        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            relevance_score=relevance_score,
            is_relevant=is_relevant,
            extracted_strips=relevant_strips,
            notes=notes,
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

        # 1. Partition visual candidates lacking substantive text from text candidates
        evaluations: list[CandidateEvaluation] = [None] * len(candidates)
        text_indices: list[int] = []
        text_candidates: list[RetrievalCandidate] = []

        for idx, cand in enumerate(candidates):
            is_vis = (
                getattr(cand, "candidate_type", "") == "visual_page"
                or getattr(cand, "modality", "") == "visual_page"
                or (getattr(cand, "metadata", {}) or {}).get("modality") == "visual_page"
            )
            raw_text = getattr(cand, "text", "") or ""
            has_substantive_text = bool(
                raw_text and len(raw_text.strip()) > 20 and not raw_text.strip().startswith("[Visual Page")
            )
            if is_vis and not has_substantive_text:
                # Pure visual candidate: evaluate via calibrated visual evidence strategy
                evaluations[idx] = self._fallback_evaluator.evaluate_candidate(query, cand)
            else:
                text_indices.append(idx)
                text_candidates.append(cand)

        # If all candidates are pure visual, return evaluations immediately without loading T5!
        if not text_candidates:
            return evaluations

        if not self._is_loaded:
            try:
                self.load_model()
            except Exception:
                pass

        # If model failed to load and fallback is enabled, use heuristic for text candidates
        if not self._is_loaded:
            if self.fallback_on_error:
                for idx, cand in zip(text_indices, text_candidates):
                    evaluations[idx] = self._fallback_evaluator.evaluate_candidate(query, cand)
                return evaluations
            raise RuntimeError("T5 CRAG model is not loaded.")

        try:
            import torch

            # 2. Tokenize and evaluate text candidates with T5
            input_texts = [
                f"{query} [SEP] {cand.get_evaluable_content()}"
                for cand in text_candidates
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
                    is_regression = (
                        getattr(self.model.config, "problem_type", None) == "regression"
                        or getattr(self.model.config, "num_labels", None) == 1
                    )
                    if logits.dim() == 2:
                        if logits.shape[1] == 1 or is_regression:
                            raw = logits.squeeze(-1)
                            raw_list = raw.cpu().tolist() if hasattr(raw, "cpu") else [float(raw)]
                            if not isinstance(raw_list, list):
                                raw_list = [raw_list]
                            # Monotonic, batch-independent logistic sigmoid calibration
                            scores = [
                                round(1.0 / (1.0 + math.exp(-max(-15.0, min(15.0, float(s))))), 4)
                                for s in raw_list
                            ]
                        else:
                            probs = torch.softmax(logits, dim=-1)[:, 1]
                            scores = probs.cpu().tolist()
                    elif logits.dim() == 1:
                        raw_list = logits.cpu().tolist() if hasattr(logits, "cpu") else [float(logits)]
                        if not isinstance(raw_list, list):
                            raw_list = [raw_list]
                        scores = [
                            round(1.0 / (1.0 + math.exp(-max(-15.0, min(15.0, float(s))))), 4)
                            for s in raw_list
                        ]
                    elif logits.dim() == 3:
                        # Seq2Seq first token logits fallback
                        first_token_logits = logits[:, 0, :]
                        probs = torch.softmax(first_token_logits, dim=-1).max(dim=-1).values
                        scores = probs.cpu().tolist()
                    else:
                        scores = [0.5] * len(text_candidates)
                    if isinstance(scores, float):
                        scores = [scores]
                else:
                    scores = [0.5] * len(text_candidates)

            for cand, score, orig_idx in zip(text_candidates, scores, text_indices):
                norm_score = max(0.0, min(1.0, float(score)))
                content = cand.get_evaluable_content()
                sentences = [s.strip() for s in re.split(r"[.!?\n]+", content) if len(s.strip()) > 15]
                query_terms = set(re.findall(r"\w+", query.lower()))
                strips = [s for s in sentences if any(t in s.lower() for t in query_terms)][:3]

                evaluations[orig_idx] = CandidateEvaluation(
                    candidate_id=cand.candidate_id,
                    relevance_score=round(norm_score, 4),
                    is_relevant=norm_score >= 0.5,
                    extracted_strips=strips,
                    notes=f"T5 CRAG model confidence: {norm_score:.4f}",
                )
            return evaluations

        except Exception as e:
            logger.error("Inference error with T5 CRAG evaluator: %s", e)
            if self.fallback_on_error:
                return self._fallback_evaluator.evaluate_batch(query, candidates)
            raise
