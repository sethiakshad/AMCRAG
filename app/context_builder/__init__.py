"""app.context_builder — Context Builder & Prompt Grounding Subsystem for AMCRAG.

Coordinates evidence normalization, deduplication, structural grouping,
multimodal routing, and token budget enforcement for the answer-generation LLM.
"""

from app.context_builder.budget import TokenBudgetEngine
from app.context_builder.builder import ContextBuilder
from app.context_builder.deduplicator import EvidenceDeduplicator
from app.context_builder.formatter import ContextFormatter
from app.context_builder.multimodal import MultimodalResolver
from app.context_builder.normalizer import EvidenceNormalizer
from app.context_builder.organizer import EvidenceOrganizer
from app.context_builder.schemas import (
    ContextBuilderConfig,
    ContextResponse,
    EvidenceItem,
    EvidenceModality,
    ModelModality,
    SourceMetadata,
)
from app.context_builder.tokenizer import TokenCounter

__all__ = [
    "ContextBuilder",
    "ContextBuilderConfig",
    "ContextFormatter",
    "ContextResponse",
    "EvidenceDeduplicator",
    "EvidenceItem",
    "EvidenceModality",
    "EvidenceNormalizer",
    "EvidenceOrganizer",
    "ModelModality",
    "MultimodalResolver",
    "SourceMetadata",
    "TokenBudgetEngine",
    "TokenCounter",
]
