"""normalizer.py — Universal Ingestion & Evidence Normalization.

Converts heterogeneous upstream retrieval outputs, CRAG evaluation results,
and legacy candidate representations into canonical EvidenceItem instances.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Union

from app.context_builder.schemas import EvidenceItem, EvidenceModality

logger = logging.getLogger("AMCRAG.ContextBuilder.Normalizer")


class EvidenceNormalizer:
    """Normalizes heterogeneous upstream payloads into uniform EvidenceItem instances."""

    def normalize(
        self,
        accepted_evidence: Union[Any, List[Any], Dict[str, Any]],
    ) -> List[EvidenceItem]:
        """Normalize heterogeneous retrieval/CRAG outputs into a list of EvidenceItem instances.

        Supports:
          1. CRAGResult (Pydantic model or dictionary with 'accepted_candidates' & 'decision').
          2. Sequence of RetrievalCandidate objects (Pydantic models).
          3. Legacy TSLE evaluation payloads (with 'selected_evidence').
          4. Generic list of candidate dictionaries.

        Args:
            accepted_evidence: Upstream payload in any supported format.

        Returns:
            List of normalized EvidenceItem instances.
        """
        if not accepted_evidence:
            return []

        raw_items: List[Any] = []
        strips_map: Dict[str, List[str]] = {}

        # 1. Unpack top-level container
        if hasattr(accepted_evidence, "accepted_candidates"):
            # Pydantic CRAGResult object
            raw_items = list(getattr(accepted_evidence, "accepted_candidates", []) or [])
            decision = getattr(accepted_evidence, "decision", None)
            if decision and hasattr(decision, "candidate_evaluations"):
                for eval_item in decision.candidate_evaluations:
                    cid = getattr(eval_item, "candidate_id", None)
                    strips = getattr(eval_item, "extracted_strips", [])
                    if cid and strips:
                        strips_map[str(cid)] = list(strips)

        elif isinstance(accepted_evidence, (list, tuple)):
            raw_items = list(accepted_evidence)
        elif isinstance(accepted_evidence, dict):
            raw_items = [accepted_evidence]
        else:
            logger.warning("Unsupported accepted_evidence type: %s", type(accepted_evidence))
            return []

        # 2. Flatten any nested envelopes (e.g. legacy {"selected_evidence": [...]}, CRAG dicts, or {"candidates": [...]})
        flattened_items: List[Any] = []
        for item in raw_items:
            if isinstance(item, dict):
                if "accepted_candidates" in item and isinstance(item["accepted_candidates"], list):
                    dec = item.get("decision") or {}
                    evals = dec.get("candidate_evaluations", []) if isinstance(dec, dict) else []
                    for eval_item in evals:
                        if isinstance(eval_item, dict):
                            cid = eval_item.get("candidate_id")
                            strips = eval_item.get("extracted_strips", [])
                            if cid and strips:
                                strips_map[str(cid)] = list(strips)
                    flattened_items.extend(item["accepted_candidates"])
                elif "selected_evidence" in item and isinstance(item["selected_evidence"], list):
                    flattened_items.extend(item["selected_evidence"])
                elif "candidates" in item and isinstance(item["candidates"], list):
                    flattened_items.extend(item["candidates"])
                else:
                    flattened_items.append(item)
            elif hasattr(item, "accepted_candidates") and isinstance(item.accepted_candidates, list):
                # Nested Pydantic CRAGResult inside a list
                flattened_items.extend(item.accepted_candidates)
                dec = getattr(item, "decision", None)
                if dec and hasattr(dec, "candidate_evaluations"):
                    for eval_item in dec.candidate_evaluations:
                        cid = getattr(eval_item, "candidate_id", None)
                        strips = getattr(eval_item, "extracted_strips", [])
                        if cid and strips:
                            strips_map[str(cid)] = list(strips)
            else:
                flattened_items.append(item)

        # 3. Normalize each item
        normalized: List[EvidenceItem] = []
        for idx, item in enumerate(flattened_items, start=1):
            try:
                norm_item = self._normalize_single_item(item, fallback_rank=idx, strips_map=strips_map)
                if norm_item:
                    normalized.append(norm_item)
            except Exception as e:
                logger.error("Failed to normalize evidence item %s: %s", item, e, exc_info=True)

        return normalized

    def _normalize_single_item(
        self,
        item: Any,
        fallback_rank: int,
        strips_map: Dict[str, List[str]],
    ) -> Optional[EvidenceItem]:
        """Convert a single candidate object or dictionary into an EvidenceItem."""
        if item is None:
            return None

        # Case A: Pydantic RetrievalCandidate or similar object
        if hasattr(item, "candidate_id") or hasattr(item, "chunk_id"):
            evidence_id = str(getattr(item, "candidate_id", None) or getattr(item, "chunk_id", None) or f"ev_{fallback_rank}")
            document_id = getattr(item, "document_id", None)
            source_filename = getattr(item, "source_filename", None) or getattr(item, "document_name", None) or document_id or "Unknown Document"
            page_start = getattr(item, "page_start", None)
            if page_start is None:
                page_start = getattr(item, "page_number", None)
            page_num = self._safe_page_number(page_start)

            # Determine modality
            cand_type = str(getattr(item, "candidate_type", "")).strip().lower()
            modality_attr = str(getattr(item, "modality", "")).strip().lower()
            is_visual = (cand_type == "visual_page") or (modality_attr in ("visual", "visual_page", "image"))
            modality = EvidenceModality.VISUAL if is_visual else EvidenceModality.TEXT

            content = getattr(item, "text", "") or ""
            if not content and hasattr(item, "get_evaluable_content"):
                content = item.get_evaluable_content() or ""

            rank = getattr(item, "retrieval_rank", None) or fallback_rank
            score = getattr(item, "retrieval_score", None)
            if score is None:
                score = getattr(item, "score", None) or getattr(item, "fused_score", None)

            source_ref = source_filename or document_id
            metadata = getattr(item, "metadata", {}) or {}
            if hasattr(metadata, "model_dump"):
                metadata = metadata.model_dump()
            elif not isinstance(metadata, dict):
                metadata = {}

            image_ref = (
                getattr(item, "page_reference", None)
                or getattr(item, "image_ref", None)
                or getattr(item, "image_path", None)
                or metadata.get("image_path")
                or metadata.get("page_reference")
            )
            image_desc = metadata.get("caption") or metadata.get("title") or metadata.get("description")
            spans = strips_map.get(evidence_id, [])

            return EvidenceItem(
                evidence_id=evidence_id,
                content=str(content),
                document_name=str(source_filename),
                document_id=str(document_id) if document_id else None,
                page_number=page_num,
                modality=modality,
                rank=int(rank),
                score=float(score) if score is not None else None,
                source_ref=str(source_ref) if source_ref else None,
                image_ref=str(image_ref) if image_ref else None,
                image_description=str(image_desc) if image_desc else None,
                evidence_spans=spans,
                raw_metadata=metadata,
            )

        # Case B: Dictionary representation
        if isinstance(item, dict):
            evidence_id = str(
                item.get("candidate_id")
                or item.get("chunk_id")
                or item.get("evidence_id")
                or item.get("id")
                or f"ev_{fallback_rank}"
            )
            document_id = item.get("document_id")
            source_filename = (
                item.get("source_filename")
                or item.get("document_title")
                or item.get("document_name")
                or item.get("document")
                or document_id
                or "Unknown Document"
            )

            raw_page = (
                item.get("page_start")
                if item.get("page_start") is not None
                else item.get("page_number", item.get("page"))
            )
            page_num = self._safe_page_number(raw_page)

            # Determine modality
            cand_type = str(item.get("candidate_type", "")).strip().lower()
            raw_modality = str(item.get("modality", "")).strip().lower()
            is_visual = (cand_type == "visual_page") or (raw_modality in ("visual", "visual_page", "image"))
            modality = EvidenceModality.VISUAL if is_visual else EvidenceModality.TEXT

            content = item.get("text") or item.get("content") or item.get("chunk_text") or ""

            rank = item.get("retrieval_rank") or item.get("rank") or fallback_rank
            retrieval_meta = item.get("retrieval") or {}
            score = (
                item.get("retrieval_score")
                or item.get("score")
                or item.get("fused_score")
                or retrieval_meta.get("reranker_score")
                or retrieval_meta.get("fusion_score")
            )

            source_ref = item.get("source_url") or item.get("source_ref") or source_filename or document_id
            metadata = item.get("metadata") or {}
            if hasattr(metadata, "model_dump"):
                metadata = metadata.model_dump()
            elif not isinstance(metadata, dict):
                metadata = {}

            image_ref = (
                item.get("page_reference")
                or item.get("image_ref")
                or item.get("image_path")
                or metadata.get("image_path")
                or metadata.get("page_reference")
            )

            image_desc = (
                item.get("image_description")
                or item.get("caption")
                or metadata.get("caption")
                or metadata.get("title")
                or metadata.get("description")
            )

            spans = strips_map.get(evidence_id, item.get("evidence_spans", []))

            return EvidenceItem(
                evidence_id=evidence_id,
                content=str(content),
                document_name=str(source_filename),
                document_id=str(document_id) if document_id else None,
                page_number=page_num,
                modality=modality,
                rank=int(rank),
                score=float(score) if score is not None else None,
                source_ref=str(source_ref) if source_ref else None,
                image_ref=str(image_ref) if image_ref else None,
                image_description=str(image_desc) if image_desc else None,
                evidence_spans=list(spans) if spans else [],
                raw_metadata=item,
            )

        logger.warning("Unrecognized item type for evidence: %s", type(item))
        return None

    @staticmethod
    def _safe_page_number(raw_val: Any) -> Optional[int]:
        """Safely convert raw page value to a 1-indexed positive int, or None."""
        if raw_val is None:
            return None
        if isinstance(raw_val, float) and (math.isinf(raw_val) or math.isnan(raw_val)):
            return None
        try:
            val = int(raw_val)
            return val if val > 0 else None
        except (ValueError, TypeError, OverflowError):
            return None

