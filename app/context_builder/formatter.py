"""formatter.py — Grounding Prompt Context Assembly & Structured Citations.

Formats prompt-ready numbered evidence blocks ([E1], [E2]...) with strict
anti-hallucination grounding instructions, and extracts 1-to-1 mapped
structured citation metadata for frontend rendering.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.context_builder.schemas import (
    ContextBuilderConfig,
    EvidenceItem,
    EvidenceModality,
    SourceMetadata,
)

logger = logging.getLogger("AMCRAG.ContextBuilder.Formatter")


class ContextFormatter:
    """Assembles the final prompt string and extracts structured citation records."""

    def __init__(self, config: Optional[ContextBuilderConfig] = None):
        self.config = config or ContextBuilderConfig()

    def format_prompt(self, query: str, items: List[EvidenceItem]) -> str:
        """Assemble the complete prompt string with question, numbered evidence blocks,

        and anti-hallucination instructions.

        Args:
            query: User's original query.
            items: Budget-checked evidence items in priority order.

        Returns:
            Formatted prompt text ready for downstream Answer LLM.
        """
        blocks: List[str] = [f"Question: {query.strip()}\n"]

        if not items:
            blocks.append("[No retrieved evidence available for this query]\n")
        else:
            for idx, item in enumerate(items, start=1):
                page_str = f"page {item.page_number}" if item.page_number is not None else "page N/A"
                type_str = "visual page" if item.modality == EvidenceModality.VISUAL else "text"
                header = f"[E{idx}] Source: {item.document_name}, {page_str} | Type: {type_str}"

                # Resolve content body with prioritized CRAG strips
                strips_part = ""
                if self.config.preserve_extracted_strips and item.evidence_spans:
                    valid_spans = [s.strip() for s in item.evidence_spans if s.strip()]
                    if valid_spans:
                        strips_part = "Key Extracted Strips:\n" + "\n".join(f"• {s}" for s in valid_spans)

                raw_body = item.content.strip() if item.content else ""
                if not raw_body and item.image_description:
                    raw_body = item.image_description.strip()

                if strips_part and raw_body:
                    body = f"{strips_part}\nContext:\n{raw_body}"
                elif strips_part:
                    body = strips_part
                elif raw_body:
                    body = raw_body
                else:
                    body = "[No content available]"

                blocks.append(f"{header}\n{body}\n")

        # Append mandatory grounding instruction
        blocks.append(self.config.system_instruction.strip())
        return "\n".join(blocks)

    def extract_sources(self, items: List[EvidenceItem]) -> List[SourceMetadata]:
        """Generate structured citation records mapped 1-to-1 with the prompt's [E#] labels.

        Args:
            items: Budget-checked evidence items.

        Returns:
            List of SourceMetadata instances for frontend rendering and verification.
        """
        sources: List[SourceMetadata] = []

        for idx, item in enumerate(items, start=1):
            source = SourceMetadata(
                evidence_id=f"E{idx}",
                chunk_id=item.evidence_id,
                document=item.document_name,
                page=item.page_number,
                type=item.modality.value,
                source_ref=item.source_ref or item.document_name,
                rank=item.rank,
            )
            sources.append(source)

        return sources
