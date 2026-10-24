"""multimodal.py — Multimodal Modality Resolution & Visual Binding.

Resolves visual vs text evidence based on downstream generator capability:
  - For Vision LLMs: Resolves image references and populates visual_inputs.
  - For Text LLMs: Uses captions, OCR, or table data; leaves visual_inputs empty.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from app.context_builder.schemas import (
    EvidenceItem,
    EvidenceModality,
    ModelModality,
)

logger = logging.getLogger("AMCRAG.ContextBuilder.Multimodal")


class MultimodalResolver:
    """Resolves visual vs text evidence based on the generator model's modality."""

    def __init__(self, model_modality: ModelModality = ModelModality.TEXT):
        self.model_modality = model_modality

    def resolve(
        self, items: List[EvidenceItem]
    ) -> Tuple[List[EvidenceItem], List[str]]:
        """Resolve evidence items according to target generator modality.

        Args:
            items: Organized list of EvidenceItem instances.

        Returns:
            Tuple of:
              - processed_items: Evidence items with modality-appropriate content representations.
              - visual_inputs: List of resolvable image paths/URIs (only populated in VISION mode).
        """
        if not items:
            return [], []

        visual_inputs: List[str] = []
        processed_items: List[EvidenceItem] = []

        for item in items:
            if item.modality == EvidenceModality.VISUAL:
                if self.model_modality == ModelModality.VISION:
                    # --- VISION MODEL MODE ---
                    # 1. Collect resolvable visual image path
                    if item.image_ref and item.image_ref.strip():
                        visual_inputs.append(item.image_ref.strip())

                    # 2. Build modality-appropriate text context
                    # If description exists, preserve it alongside visual indicator
                    desc = item.image_description or ""
                    page_str = f"Page {item.page_number}" if item.page_number else "Page N/A"
                    visual_tag = f"Visual input: <Image from {item.document_name}, {page_str}>"

                    if desc and desc.strip():
                        text_repr = f"{desc.strip()}\n{visual_tag}"
                    elif item.content and item.content.strip():
                        text_repr = f"{item.content.strip()}\n{visual_tag}"
                    else:
                        text_repr = visual_tag

                    # Create a cloned item with updated content
                    updated_item = item.model_copy(update={"content": text_repr})
                    processed_items.append(updated_item)

                else:
                    # --- TEXT-ONLY MODEL MODE ---
                    # Visual inputs must remain strictly empty
                    # Rely on caption, description, OCR, or evaluable content
                    text_content = item.content.strip() if item.content else ""
                    desc = item.image_description.strip() if item.image_description else ""

                    if desc and text_content:
                        text_repr = f"{desc}\n{text_content}"
                    elif desc:
                        text_repr = desc
                    elif text_content:
                        text_repr = text_content
                    else:
                        page_str = f"page {item.page_number}" if item.page_number else "unspecified page"
                        text_repr = (
                            f"[Visual content from {item.document_name}, {page_str}: "
                            f"no text transcript available]"
                        )
                        logger.warning(
                            "Visual item %s lacks text description in TEXT-ONLY mode; fallback applied",
                            item.evidence_id,
                        )

                    # For text models, suppress image_ref in prompt rendering
                    updated_item = item.model_copy(
                        update={"content": text_repr, "image_ref": None}
                    )
                    processed_items.append(updated_item)

            else:
                # --- STANDARD TEXT CHUNK ---
                processed_items.append(item)

        return processed_items, visual_inputs
