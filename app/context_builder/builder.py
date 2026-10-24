"""builder.py — Unified Facade Coordinator for Context Builder.

Coordinates evidence normalization, deduplication, structural grouping,
multimodal resolution, token budgeting, prompt synthesis, and citation extraction.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from app.context_builder.budget import TokenBudgetEngine
from app.context_builder.deduplicator import EvidenceDeduplicator
from app.context_builder.formatter import ContextFormatter
from app.context_builder.multimodal import MultimodalResolver
from app.context_builder.normalizer import EvidenceNormalizer
from app.context_builder.organizer import EvidenceOrganizer
from app.context_builder.schemas import (
    ContextBuilderConfig,
    ContextResponse,
    EvidenceItem,
    ModelModality,
)

logger = logging.getLogger("AMCRAG.ContextBuilder")


class ContextBuilder:
    """Main coordinator facade for assembling grounded LLM prompt contexts."""

    def __init__(self, config: Optional[ContextBuilderConfig] = None):
        """Initialize the ContextBuilder pipeline with configuration options.

        Args:
            config: ContextBuilderConfig instance. If None, default settings are used.
        """
        self.config = config or ContextBuilderConfig()
        self.normalizer = EvidenceNormalizer()
        self.deduplicator = EvidenceDeduplicator()
        self.organizer = EvidenceOrganizer(self.config)
        self.multimodal = MultimodalResolver(self.config.model_modality)
        self.budget_engine = TokenBudgetEngine(self.config)
        self.formatter = ContextFormatter(self.config)

        logger.info(
            "Initialized ContextBuilder (budget=%d tokens, modality=%s, group_by_doc=%s)",
            self.config.token_budget,
            self.config.model_modality.value,
            self.config.group_by_document,
        )

    def build(
        self,
        query: str,
        accepted_evidence: Union[Any, List[Any], Dict[str, Any]],
    ) -> ContextResponse:
        """Execute the end-to-end context building pipeline.

        Steps:
          1. Schema Normalization: Ingest CRAGResult, RetrievalCandidate list, or raw dicts.
          2. Evidence Deduplication: Filter duplicate IDs and identical text-hashes.
          3. Relevance Ordering & Grouping: Sort by rank or group contiguously by document.
          4. Multimodal Resolution: Route images to vision inputs or captions to text.
          5. Token Budget Enforcement: Greedily fit candidates; log and track omitted IDs.
          6. Prompt Synthesis: Assemble [E#] labeled prompt with grounding constraints.
          7. Structured Citations: Extract 1-to-1 citation metadata for frontend rendering.
          8. Token Accounting: Compute final token estimate.

        Args:
            query: User's original or active query.
            accepted_evidence: Upstream accepted evidence payload.

        Returns:
            ContextResponse instance ready for downstream LLM and frontend.
        """
        logger.debug("Building context for query: '%s'", query)

        # Step 1: Normalization
        raw_items: List[EvidenceItem] = self.normalizer.normalize(accepted_evidence)

        # Step 2: Deduplication
        deduped_items: List[EvidenceItem] = self.deduplicator.deduplicate(raw_items)

        # Step 3: Organization & Relevance Sorting
        organized_items: List[EvidenceItem] = self.organizer.organize(deduped_items)

        # Step 4: Multimodal Modality Resolution
        processed_items, visual_inputs = self.multimodal.resolve(organized_items)

        # Step 5: Token Budget Enforcement
        included_items, omitted_ids = self.budget_engine.enforce(query, processed_items)

        # Step 6: Prompt Context Assembly
        prompt_context: str = self.formatter.format_prompt(query, included_items)

        # Step 7: Citation Metadata Extraction
        sources = self.formatter.extract_sources(included_items)

        # Step 8: Token Estimation of final context
        total_tokens = self.budget_engine.count_tokens(prompt_context)

        # Extract upstream decision label if present
        crag_label = self._extract_crag_decision_label(accepted_evidence)

        return ContextResponse(
            query=query,
            context=prompt_context,
            visual_inputs=visual_inputs,
            sources=sources,
            included_evidence_ids=[item.evidence_id for item in included_items],
            omitted_evidence_ids=omitted_ids,
            token_estimate=total_tokens,
            crag_decision=crag_label,
        )

    def to_downstream_payload(self, response: ContextResponse) -> Dict[str, Any]:
        """Convert ContextResponse into a simplified dictionary structure for legacy downstream adapters.

        Args:
            response: Canonical ContextResponse output from build().

        Returns:
            Dictionary matching legacy downstream expectations.
        """
        return {
            "query": response.query,
            "answering_policy": self.config.system_instruction,
            "context": [
                {
                    "content": src.source_ref or src.document,
                    "citation": {
                        "document": src.document,
                        "page": src.page,
                        "chunk_id": src.chunk_id,
                    },
                }
                for src in response.sources
            ],
            "visual_inputs": response.visual_inputs,
            "token_estimate": response.token_estimate,
        }

    @staticmethod
    def _extract_crag_decision_label(evidence_payload: Any) -> Optional[str]:
        """Safely extract CRAG decision label from heterogeneous evidence payloads."""
        if hasattr(evidence_payload, "decision"):
            decision = getattr(evidence_payload, "decision", None)
            if hasattr(decision, "label"):
                return str(getattr(decision, "label"))
            if isinstance(decision, dict) and "label" in decision:
                return str(decision["label"])

        if isinstance(evidence_payload, dict):
            if "decision" in evidence_payload:
                dec = evidence_payload["decision"]
                if isinstance(dec, dict):
                    return dec.get("label")
                if isinstance(dec, str):
                    return dec
            if "label" in evidence_payload:
                return str(evidence_payload["label"])

        return None
