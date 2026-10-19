"""ColPali Visual Reranker — Milestone 8.

After RRF fusion produces a mixed candidate list (text chunks + visual pages),
this reranker uses ColPali to compute precise MaxSim scores for the visual_page
candidates and re-orders the final list.

Two reranking strategies:
  1. visual_only  — Only reranks the visual_page candidates using ColPali scores.
                    Text candidates keep their RRF fused_score unchanged.
  2. full_blend   — Normalises both text (BGE reranker) and visual (ColPali)
                    scores to [0, 1] then sorts the entire combined list.

The reranker accepts List[RetrievalResult] (from RRF fusion output) and returns
a reranked List[RetrievalResult] with updated scores, conforming to the same
schema that Person 4's CRAG evaluator expects.

Usage:
    from app.colpali.colpali_reranker import ColPaliReranker
    from app.colpali.colpali_model import ColPaliModel
    from schemas import RetrievalResult

    model    = ColPaliModel()
    reranker = ColPaliReranker(model=model)

    reranked = reranker.rerank(
        query="Show me the accuracy chart",
        candidates=rrf_results,      # List[RetrievalResult]
        strategy="visual_only",
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Literal, Optional, TYPE_CHECKING

from schemas import RetrievalResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports
# ---------------------------------------------------------------------------
try:
    from PIL import Image as PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    PILImage = None  # type: ignore

if TYPE_CHECKING:
    from app.colpali.colpali_model import ColPaliModel


RerankerStrategy = Literal["visual_only", "full_blend"]


class ColPaliReranker:
    """Reranks a mixed candidate list using ColPali scores for visual pages.

    Args:
        model:    Loaded ColPaliModel for computing MaxSim scores on-the-fly.
        strategy: "visual_only" (default) or "full_blend".
        enabled:  Set False to skip reranking (returns input unchanged).
    """

    def __init__(
        self,
        model: "ColPaliModel",
        strategy: RerankerStrategy = "visual_only",
        enabled: bool = True,
    ) -> None:
        self.model = model
        self.strategy = strategy
        self.enabled = enabled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        strategy: Optional[RerankerStrategy] = None,
    ) -> List[RetrievalResult]:
        """Rerank a fused candidate list, boosting visual pages via ColPali.

        Args:
            query:      Original user query string.
            candidates: Mixed list of text_chunk + visual_page RetrievalResults.
            strategy:   Override instance strategy for this call.

        Returns:
            Reranked list of RetrievalResult sorted by descending relevance.
            All candidates are returned (no truncation here).
        """
        if not self.enabled or not candidates:
            return candidates

        active_strategy = strategy or self.strategy

        # Separate candidates by modality
        visual = [c for c in candidates if c.modality == "visual_page"]
        text   = [c for c in candidates if c.modality != "visual_page"]

        if not visual:
            logger.debug("No visual_page candidates found, returning candidates unchanged.")
            return candidates

        # Score visual candidates using ColPali MaxSim
        visual = self._score_visual_candidates(query, visual)

        if active_strategy == "visual_only":
            return self._merge_visual_only(text, visual)
        elif active_strategy == "full_blend":
            return self._merge_full_blend(text, visual)
        else:
            logger.warning("Unknown reranker strategy '%s', using visual_only.", active_strategy)
            return self._merge_visual_only(text, visual)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_visual_candidates(
        self,
        query: str,
        visual_candidates: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """Compute ColPali MaxSim score for each visual_page candidate.

        Loads the page image from disk (path stored in metadata["image_path"]),
        computes MaxSim against the query embedding, and writes the score
        back into the candidate's fused_score field.
        """
        try:
            query_vectors = self.model.embed_query(query)
        except Exception as exc:
            logger.error("ColPali reranker failed to embed query: %s. Returning unscored.", exc)
            return visual_candidates

        scored: List[RetrievalResult] = []
        for candidate in visual_candidates:
            image_path = candidate.metadata.get("image_path", "")
            colpali_score = self._compute_page_score(query_vectors, image_path)

            # Build updated candidate with ColPali score as fused_score
            updated_data = candidate.model_dump()
            updated_data["fused_score"] = colpali_score
            updated_data["metadata"] = dict(candidate.metadata)
            updated_data["metadata"]["colpali_rerank_score"] = colpali_score

            scored.append(RetrievalResult(**updated_data))

        return scored

    def _compute_page_score(
        self,
        query_vectors: List[List[float]],
        image_path: str,
    ) -> float:
        """Load image from disk and compute MaxSim score against query."""
        if not image_path:
            logger.debug("No image_path in candidate metadata, score=0.0")
            return 0.0

        path = Path(image_path)
        if not path.exists():
            logger.warning("Image file not found for reranking: %s", path)
            return 0.0

        if not _PIL_AVAILABLE:
            logger.warning("Pillow not installed; cannot load image for reranking.")
            return 0.0

        try:
            image = PILImage.open(path).convert("RGB")
            page_vectors = self.model.embed_image(image)
            return self.model.score(query_vectors, page_vectors)
        except Exception as exc:
            logger.warning("ColPali reranking failed for '%s': %s", path, exc)
            return 0.0

    # ------------------------------------------------------------------
    # Merge strategies
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_visual_only(
        text: List[RetrievalResult],
        visual: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """Sort visual by ColPali score, keep text scores as-is, then interleave.

        Text candidates keep their RRF fused_score.
        Visual candidates are re-sorted by ColPali fused_score.
        Final order: sort all by fused_score descending.
        """
        visual_sorted = sorted(visual, key=lambda c: c.fused_score, reverse=True)
        combined = text + visual_sorted
        return sorted(combined, key=lambda c: c.fused_score, reverse=True)

    @staticmethod
    def _merge_full_blend(
        text: List[RetrievalResult],
        visual: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """Normalise both score ranges to [0,1] then sort the full list.

        Handles the case where BGE reranker scores and ColPali MaxSim scores
        have different numeric ranges.
        """
        def _normalize(items: List[RetrievalResult]) -> List[RetrievalResult]:
            if not items:
                return items
            scores = [c.fused_score for c in items]
            min_s, max_s = min(scores), max(scores)
            denom = max_s - min_s if max_s != min_s else 1.0
            normalized = []
            for c in items:
                data = c.model_dump()
                data["fused_score"] = (c.fused_score - min_s) / denom
                normalized.append(RetrievalResult(**data))
            return normalized

        norm_text   = _normalize(text)
        norm_visual = _normalize(visual)
        combined    = norm_text + norm_visual
        return sorted(combined, key=lambda c: c.fused_score, reverse=True)
