"""Gemma 4 Visual Reranker.

Replicates the functionality of ColPaliReranker:
- Re-scores visual page candidates using Gemma 4 Vision multimodal relevance scoring
- Supports 'visual_only' and 'full_blend' strategies
- Returns re-ordered List[RetrievalResult] conforming to schemas.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Literal, Optional

from app.visual_orchestrator.client import OllamaVisualClient
from schemas import RetrievalResult

logger = logging.getLogger("AMCRAG.VisualOrchestrator.Reranker")

RerankerStrategy = Literal["visual_only", "full_blend"]


class GemmaVisualReranker:
    """Reranks candidate pools using Gemma 4 Vision multimodal scoring for visual pages."""

    def __init__(
        self,
        client: Optional[OllamaVisualClient] = None,
        strategy: RerankerStrategy = "visual_only",
    ) -> None:
        self.client = client or OllamaVisualClient()
        self.default_strategy = strategy

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        strategy: Optional[RerankerStrategy] = None,
    ) -> List[RetrievalResult]:
        """Rerank a candidate list using Gemma 4 Vision for visual page items.

        Args:
            query: The user query.
            candidates: List of RetrievalResult items (text chunks + visual pages).
            strategy: 'visual_only' (rescore only visual candidates) or
                      'full_blend' (normalize both text and visual scores to [0, 1]).

        Returns:
            Reordered list of RetrievalResult items with updated scores.
        """
        if not candidates or not query.strip():
            return list(candidates)

        active_strategy = strategy or self.default_strategy
        visual_candidates: List[RetrievalResult] = []
        text_candidates: List[RetrievalResult] = []

        for cand in candidates:
            is_visual = (
                getattr(cand, "retrieval_method", "") in ("colpali", "visual", "visual_gemma")
                or getattr(cand, "candidate_type", "") == "visual_page"
                or getattr(cand, "modality", "") == "visual_page"
                or bool(getattr(cand, "image_path", None))
            )
            if is_visual:
                visual_candidates.append(cand)
            else:
                text_candidates.append(cand)

        logger.debug(
            "GemmaVisualReranker: Processing %d visual and %d text candidates (strategy=%s)",
            len(visual_candidates),
            len(text_candidates),
            active_strategy,
        )

        # Score visual candidates using Gemma 4 Vision
        for cand in visual_candidates:
            img_path = getattr(cand, "image_path", None)
            if not img_path:
                meta = getattr(cand, "metadata", {}) or {}
                img_path = meta.get("image_path")

            if img_path and Path(img_path).exists():
                v_score = self.client.score_visual_relevance(
                    query=query,
                    image_path=img_path,
                    page_context=cand.text,
                )
                cand.score = round(v_score, 4)
                cand.fused_score = round(v_score, 4)

        if active_strategy == "visual_only":
            # Sort visual candidates among themselves, keep text candidates unchanged
            visual_candidates.sort(key=lambda c: c.score or 0.0, reverse=True)
            # Reconstruct combined list preserving relative order of text and top visuals
            combined = visual_candidates + text_candidates
            return combined

        # Strategy: full_blend — Normalize both text and visual scores to [0, 1]
        all_candidates = visual_candidates + text_candidates
        scores = [c.score if c.score is not None else 0.5 for c in all_candidates]
        min_s, max_s = min(scores), max(scores)

        for cand in all_candidates:
            raw = cand.score if cand.score is not None else 0.5
            if max_s > min_s:
                norm = (raw - min_s) / (max_s - min_s)
            else:
                norm = raw
            cand.fused_score = round(float(norm), 4)

        all_candidates.sort(key=lambda c: c.fused_score or 0.0, reverse=True)
        return all_candidates
