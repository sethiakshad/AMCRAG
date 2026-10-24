"""
Pluggability Demonstration: How the Text Retrieval merges seamlessly
with Teammate's ColPali Visual Page Retrieval before reaching the BGE Reranker.
"""
from typing import List
from schemas import RetrievalResult


class MultimodalFusionBridge:
    """
    Demonstrates how downstream integrates:
    - Om's Hybrid Text Retrieval Results (bge + bm25)
    - Teammate's ColPali Visual Retrieval Results
    """
    @staticmethod
    def merge_text_and_visual(
        text_results: List[RetrievalResult],
        visual_results: List[RetrievalResult],
        text_weight: float = 0.6,
        visual_weight: float = 0.4,
        final_top_k: int = 10
    ) -> List[RetrievalResult]:
        """
        Performs cross-modal combination. Because both outputs conform
        to the exact same `RetrievalResult` schema, this is clean, robust,
        and completely decoupled.
        """
        combined: List[RetrievalResult] = []
        seen_keys = {}

        # Scale fused scores by modality weights
        for item in text_results:
            scaled_item = item.model_copy(deep=True)
            scaled_item.fused_score = item.fused_score * text_weight
            key = f"{item.document_id}_p{item.page_number}"
            seen_keys[key] = scaled_item
            combined.append(scaled_item)

        for item in visual_results:
            key = f"{item.document_id}_p{item.page_number}"
            scaled_visual_score = item.fused_score * visual_weight
            # If the same page is found in both text and visual, boost its confidence
            if key in seen_keys:
                seen_keys[key].fused_score += scaled_visual_score
            else:
                scaled_item = item.model_copy(deep=True)
                scaled_item.fused_score = scaled_visual_score
                combined.append(scaled_item)

        # Sort combined results
        combined.sort(key=lambda x: x.fused_score, reverse=True)
        return combined[:final_top_k]
