"""deduplicator.py — High-Fidelity Evidence Deduplication.

Eliminates true duplicate chunks and redundant page references while strictly
preserving distinct text passages originating from the same document page.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import List, Set, Tuple

from app.context_builder.schemas import EvidenceItem, EvidenceModality

logger = logging.getLogger("AMCRAG.ContextBuilder.Deduplicator")


class EvidenceDeduplicator:
    """Multi-level deduplication engine preserving unique information."""

    def deduplicate(self, items: List[EvidenceItem]) -> List[EvidenceItem]:
        """Deduplicate a list of EvidenceItem instances.

        Rules applied:
          1. ID deduplication: If identical evidence_id is found, keep the first / top-ranked.
          2. Text content hash: If two text items have identical normalized text, retain only the top-ranked.
          3. Visual page deduplication: If multiple visual items refer to the same (doc, page) or image path,
             retain only the top-ranked visual entry.
          4. SAME-PAGE PRESERVATION GUARANTEE: Distinct text chunks from the same page are retained.

        Args:
            items: Normalized evidence items.

        Returns:
            Filtered list of EvidenceItem instances with duplicates removed.
        """
        if not items:
            return []

        # 1. Pair each item with its original input index
        indexed_items = list(enumerate(items))

        # 2. Sort by quality: lowest rank (best) first, then highest score
        def _quality_key(entry: Tuple[int, EvidenceItem]):
            _, it = entry
            rank_val = it.rank if (it.rank is not None and it.rank > 0) else 999999
            score_val = -(it.score if it.score is not None else -999999.0)
            return (rank_val, score_val)

        sorted_by_quality = sorted(indexed_items, key=_quality_key)

        seen_ids: Set[str] = set()
        seen_text_hashes: Set[str] = set()
        seen_visual_pages: Set[Tuple[str, int]] = set()
        seen_visual_paths: Set[str] = set()

        retained: List[Tuple[int, EvidenceItem]] = []

        for orig_idx, item in sorted_by_quality:
            # Check 1: Candidate / Chunk ID deduplication
            if item.evidence_id in seen_ids:
                logger.debug(
                    "Deduplicated identical evidence_id: %s (rank=%d, keeping higher-quality candidate)",
                    item.evidence_id,
                    item.rank,
                )
                continue

            # Check 2: Visual page deduplication
            if item.modality == EvidenceModality.VISUAL:
                doc_key = item.document_id or item.document_name
                page_key = item.page_number or -1
                visual_tuple = (doc_key, page_key)

                if visual_tuple in seen_visual_pages and page_key > 0:
                    logger.debug(
                        "Deduplicated redundant visual page for %s page %d (item %s)",
                        doc_key,
                        page_key,
                        item.evidence_id,
                    )
                    continue

                if item.image_ref and item.image_ref in seen_visual_paths:
                    logger.debug("Deduplicated redundant visual path %s", item.image_ref)
                    continue

                # Mark visual keys as seen
                if page_key > 0:
                    seen_visual_pages.add(visual_tuple)
                if item.image_ref:
                    seen_visual_paths.add(item.image_ref)

            # Check 3: Text content hash deduplication
            elif item.content and item.content.strip():
                norm_hash = self._compute_text_hash(item.content)
                if norm_hash in seen_text_hashes:
                    logger.debug(
                        "Deduplicated identical text content in item %s (matches higher-quality chunk)",
                        item.evidence_id,
                    )
                    continue
                seen_text_hashes.add(norm_hash)

            # If all checks pass, retain item
            seen_ids.add(item.evidence_id)
            retained.append((orig_idx, item))

        # 3. Restore original order of appearance
        retained.sort(key=lambda x: x[0])
        return [item for _, item in retained]

    @staticmethod
    def _compute_text_hash(text: str) -> str:
        """Compute an MD5 hash over normalized, case-folded, whitespace-collapsed text."""
        # Lowercase, collapse whitespace without expensive regex
        cleaned = " ".join(text.lower().split())
        return hashlib.md5(cleaned.encode("utf-8")).hexdigest()

