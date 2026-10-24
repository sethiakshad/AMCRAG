"""organizer.py — Relevance Sorting & Structural Document Grouping.

Orders evidence passages by relevance rank and score, with optional
contiguous document and page grouping for enhanced LLM reading comprehension.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import List, Optional

from app.context_builder.schemas import ContextBuilderConfig, EvidenceItem

logger = logging.getLogger("AMCRAG.ContextBuilder.Organizer")


class EvidenceOrganizer:
    """Sorts and structurally groups evidence items based on configuration."""

    def __init__(self, config: Optional[ContextBuilderConfig] = None):
        self.config = config or ContextBuilderConfig()

    def organize(self, items: List[EvidenceItem]) -> List[EvidenceItem]:
        """Order evidence items by relevance rank and apply document grouping if configured.

        Args:
            items: Deduplicated evidence items.

        Returns:
            Sorted and optionally document-grouped list of EvidenceItem instances.
        """
        if not items:
            return []

        # 1. Base primary sorting: rank ascending (1, 2, ...), fallback to score descending
        sorted_by_relevance = sorted(
            items,
            key=lambda x: (
                x.rank if (x.rank is not None and x.rank > 0) else 999999,
                -(x.score if x.score is not None else -999999.0),
            ),
        )

        # 2. Structural Document Grouping
        if self.config.group_by_document:
            organized = self._group_by_document_and_page(sorted_by_relevance)
        else:
            organized = sorted_by_relevance

        # 3. Apply optional max_evidence_items limit
        if self.config.max_evidence_items and self.config.max_evidence_items > 0:
            logger.debug(
                "Capping evidence items from %d to %d",
                len(organized),
                self.config.max_evidence_items,
            )
            organized = organized[: self.config.max_evidence_items]

        return organized

    def _group_by_document_and_page(
        self, items: List[EvidenceItem]
    ) -> List[EvidenceItem]:
        """Group items by document, keeping documents ordered by their highest-ranked item,

        and chunks within each document ordered by page number.
        """
        # Bucket by document identifier
        doc_buckets = defaultdict(list)
        doc_best_rank = {}

        for item in items:
            doc_key = item.document_id or item.document_name or "unknown"
            doc_buckets[doc_key].append(item)
            # Track best rank seen for this document
            current_rank = item.rank if (item.rank is not None and item.rank > 0) else 999999
            if doc_key not in doc_best_rank or current_rank < doc_best_rank[doc_key]:
                doc_best_rank[doc_key] = current_rank

        # Sort documents by their best candidate's rank
        sorted_doc_keys = sorted(doc_buckets.keys(), key=lambda d: doc_best_rank[d])

        # Within each document, sort chunks by page_number ascending, then by rank
        grouped_result: List[EvidenceItem] = []
        for doc_key in sorted_doc_keys:
            doc_items = doc_buckets[doc_key]
            sorted_doc_items = sorted(
                doc_items,
                key=lambda x: (
                    x.page_number if (x.page_number is not None and x.page_number > 0) else 999999,
                    x.rank if (x.rank is not None and x.rank > 0) else 999999,
                ),
            )
            grouped_result.extend(sorted_doc_items)

        return grouped_result
