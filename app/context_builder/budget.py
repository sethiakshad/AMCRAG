"""budget.py — Token Budget Enforcement & Omission Tracking.

Calculates fixed prompt overhead (query header and system instructions),
greedily fits evidence items in priority order within the remaining budget,
and explicitly tracks omitted items without silent truncation.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from app.context_builder.schemas import (
    ContextBuilderConfig,
    EvidenceItem,
    EvidenceModality,
)
from app.context_builder.tokenizer import TokenCounter

logger = logging.getLogger("AMCRAG.ContextBuilder.Budget")


class TokenBudgetEngine:
    """Enforces configurable token budgets and tracks omitted evidence."""

    def __init__(
        self,
        config: Optional[ContextBuilderConfig] = None,
        tokenizer: Optional[TokenCounter] = None,
    ):
        self.config = config or ContextBuilderConfig()
        self.tokenizer = tokenizer or TokenCounter(self.config.tokenizer_name)

    def calculate_fixed_overhead(self, query: str) -> int:
        """Calculate the token cost of static prompt framing (query header + system instruction)."""
        prompt_skeleton = f"Question: {query}\n\n{self.config.system_instruction}"
        return self.tokenizer.count_tokens(prompt_skeleton)

    def estimate_item_tokens(self, label_idx: int, item: EvidenceItem) -> int:
        """Estimate token count for a single evidence block with its [E#] header."""
        page_str = f"page {item.page_number}" if item.page_number is not None else "page N/A"
        type_str = "visual page" if item.modality == EvidenceModality.VISUAL else "text"
        header = f"[E{label_idx}] Source: {item.document_name}, {page_str} | Type: {type_str}\n"

        strips_part = ""
        if self.config.preserve_extracted_strips and item.evidence_spans:
            valid_spans = [s.strip() for s in item.evidence_spans if s.strip()]
            if valid_spans:
                strips_part = "Key Extracted Strips:\n" + "\n".join(f"• {s}" for s in valid_spans) + "\n"

        body = item.content or item.image_description or "[No content available]"
        block = f"{header}{strips_part}{body}\n\n"
        return self.tokenizer.count_tokens(block)

    def count_tokens(self, text: str) -> int:
        """Utility to count tokens for arbitrary text."""
        return self.tokenizer.count_tokens(text)

    def enforce(
        self, query: str, items: List[EvidenceItem]
    ) -> Tuple[List[EvidenceItem], List[str]]:
        """Greedily fits evidence items into token budget, tracking omitted items.

        Args:
            query: The user query string.
            items: Sorted and organized evidence items.

        Returns:
            Tuple of:
              - included_items: Evidence items that fit within the token budget.
              - omitted_evidence_ids: IDs of items omitted due to token constraints.
        """
        if not items:
            return [], []

        fixed_overhead = self.calculate_fixed_overhead(query)
        remaining_budget = max(0, self.config.token_budget - fixed_overhead)

        included: List[EvidenceItem] = []
        omitted_ids: List[str] = []

        current_tokens = 0
        for idx, item in enumerate(items):
            # Short-circuit if budget is exhausted (every item requires >= 7 tokens for header)
            if current_tokens >= remaining_budget:
                omitted_ids.extend(it.evidence_id for it in items[idx:])
                break

            label_idx = len(included) + 1
            item_tokens = self.estimate_item_tokens(label_idx, item)

            if current_tokens + item_tokens <= remaining_budget:
                included.append(item)
                current_tokens += item_tokens
            else:
                omitted_ids.append(item.evidence_id)
                logger.debug(
                    "Omitted evidence '%s' (tokens=%d, remaining_allowance=%d)",
                    item.evidence_id,
                    item_tokens,
                    remaining_budget - current_tokens,
                )

        return included, omitted_ids
