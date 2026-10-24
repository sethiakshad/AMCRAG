"""schemas.py — Pydantic Data Contracts & Schemas for Context Builder.

Defines normalized evidence items, configuration options, and structured
response contracts for prompt synthesis and frontend citation rendering.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ModelModality(str, Enum):
    """Target generator LLM modality capability."""

    TEXT = "text"
    VISION = "vision"


class EvidenceModality(str, Enum):
    """Modality of an ingested evidence item."""

    TEXT = "text"
    VISUAL = "visual"


class SourceMetadata(BaseModel):
    """Structured provenance citation record for frontend citation rendering

    and downstream factual verification.
    """

    evidence_id: str = Field(..., description="Prompt label, e.g. 'E1', 'E2'")
    chunk_id: str = Field(..., description="Underlying candidate / chunk ID")
    document: str = Field(..., description="Human-readable filename or document title")
    page: Optional[int] = Field(default=None, description="1-indexed page number")
    type: str = Field(default="text", description="'text' or 'visual'")
    source_ref: Optional[str] = Field(default=None, description="Source URI or relative path")
    rank: Optional[int] = Field(default=None, description="Ordinal rank position")

    model_config = {"extra": "allow"}


class EvidenceItem(BaseModel):
    """Internal normalized representation of a single evidence passage or visual page."""

    evidence_id: str = Field(..., description="Unique chunk or candidate identifier")
    content: str = Field(default="", description="Textual body content or OCR text")
    document_name: str = Field(default="Unknown Document", description="Source document filename")
    document_id: Optional[str] = Field(default=None, description="Parent document identifier")
    page_number: Optional[int] = Field(default=None, description="1-indexed page number")
    modality: EvidenceModality = Field(default=EvidenceModality.TEXT, description="Modality type")
    rank: int = Field(default=1, description="Ordinal rank position (1-indexed)")
    score: Optional[float] = Field(default=None, description="Relevance or fusion score")
    source_ref: Optional[str] = Field(default=None, description="Source path or URI")
    image_ref: Optional[str] = Field(default=None, description="Path to rendered page image")
    image_description: Optional[str] = Field(default=None, description="Caption or table description")
    evidence_spans: List[str] = Field(default_factory=list, description="Extracted sentence strips")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Auxiliary metadata")

    model_config = {"extra": "allow"}


class ContextBuilderConfig(BaseModel):
    """Configuration options for the Context Builder pipeline."""

    token_budget: int = Field(default=4096, description="Max token allowance for final prompt")
    model_modality: ModelModality = Field(
        default=ModelModality.TEXT, description="Capability of downstream generator LLM"
    )
    max_evidence_items: Optional[int] = Field(
        default=None, description="Optional cap on the number of evidence items"
    )
    group_by_document: bool = Field(
        default=False, description="Whether to group items by document and page"
    )
    preserve_extracted_strips: bool = Field(
        default=True, description="Inject CRAG-decomposed sentence strips when available"
    )
    tokenizer_name: str = Field(default="cl100k_base", description="Tokenizer identifier")
    system_instruction: str = Field(
        default=(
            "Instruction: Answer the question using ONLY the numbered evidence above. "
            "Cite claims with source labels (e.g., [E1], document.pdf, Page 12). "
            "If evidence is insufficient, contradictory, or absent, state clearly that the "
            "evidence does not support an answer. Do not hallucinate facts or citations."
        ),
        description="System prompt grounding constraint appended to prompt",
    )

    model_config = {"extra": "allow"}


class ContextResponse(BaseModel):
    """Canonical output contract returned to the downstream Answer LLM and FastAPI orchestrator."""

    query: str = Field(..., description="Original user query")
    context: str = Field(..., description="Prompt-ready context string with numbered labels")
    visual_inputs: List[str] = Field(
        default_factory=list, description="Resolvable image paths for vision models"
    )
    sources: List[SourceMetadata] = Field(
        default_factory=list, description="Structured citation metadata"
    )
    included_evidence_ids: List[str] = Field(
        default_factory=list, description="IDs of evidence items that fit within token budget"
    )
    omitted_evidence_ids: List[str] = Field(
        default_factory=list, description="IDs of evidence items omitted due to budget constraints"
    )
    token_estimate: int = Field(default=0, description="Estimated token count of prompt context")
    crag_decision: Optional[str] = Field(
        default=None, description="Decision label from upstream CRAG (e.g. 'CORRECT')"
    )

    model_config = {"extra": "allow"}
