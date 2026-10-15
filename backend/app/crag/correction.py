"""Corrective retrieval loop and query reformulation for AMCRAG.

Follows Sections 4.8, 10.5, 14, and 16 of AMCRAG Central Project Documentation.
"""

import re
from typing import Sequence
from pydantic import BaseModel, Field

from app.schemas.crag import EvidenceDecision
from app.schemas.retrieval import RetrievalCandidate


class CorrectionConfig(BaseModel):
    """Configuration for query reformulation and retry bounds."""

    max_attempts: int = Field(
        default=2,
        description="Maximum number of correction attempts allowed (default 2 retries)",
    )
    strip_conversational_prefixes: bool = Field(
        default=True,
        description="Strip filler phrases like 'can you tell me' to improve retrieval precision",
    )
    detect_visual_intent: bool = Field(
        default=True,
        description="Detect and reinforce visual keywords (figure, table, chart, diagram)",
    )


class QueryReformulator:
    """Reformulates queries when evidence is inadequate and prevents retrieval cycles."""

    CONVERSATIONAL_PREFIXES = [
        r"^(can you|could you|would you)\s+(please\s+)?(tell me|explain|find|show|describe)\s*(what\s+is|what\s+are|what\s+was|what\s+were|how|where|which)?\s*",
        r"^(please\s+)?(tell me|explain|find|show|describe)\s*(what\s+is|what\s+are|what\s+was|what\s+were|how|where|which)?\s*",
        r"^(what is|what are|what was|what were)\s+",
        r"^(i would like to know|i want to know|tell me about)\s+",
        r"^(give me an overview of|summarize)\s+",
    ]

    VISUAL_KEYWORDS = ["figure", "table", "chart", "diagram", "plot", "graph", "layout"]

    def __init__(self, config: CorrectionConfig | None = None):
        self.config = config or CorrectionConfig()
        # History of generated queries per original query to prevent looping
        self._query_history: dict[str, list[str]] = {}

    def reformulate_query(
        self,
        original_query: str,
        candidates: Sequence[RetrievalCandidate],
        decision: EvidenceDecision,
        attempt_number: int,
    ) -> str:
        """Generates a reformulated or expanded query based on failure analysis.

        Preserves original question intent while removing noise and adding specific search signals.

        Args:
            original_query: The user's original raw question.
            candidates: Current retrieved candidates that were judged inadequate.
            decision: The EvidenceDecision explaining why retrieval failed.
            attempt_number: Current retry iteration index.

        Returns:
            A refined query string for the next retrieval attempt.
        """
        history = self._query_history.setdefault(original_query, [original_query])

        clean_query = self._clean_query(original_query)
        visual_intent = self._detect_visual_intent(original_query)

        # Attempt Strategy 1: Targeted keyword extraction + visual cue reinforcement
        if attempt_number == 0:
            reformulated = self._strategy_keyword_isolation(clean_query, visual_intent)
        # Attempt Strategy 2: Query expansion with candidate context or broader synonyms
        else:
            reformulated = self._strategy_expanded_search(
                clean_query, candidates, visual_intent, attempt_number
            )

        # Cycle avoidance: If the reformulated query has already been used, generate an alternate variation
        if reformulated in history or reformulated == original_query:
            reformulated = self._generate_fallback_variation(clean_query, visual_intent, len(history))

        history.append(reformulated)
        return reformulated

    def _clean_query(self, query: str) -> str:
        """Removes conversational filler and punctuation to extract core search terms."""
        cleaned = query.strip()
        if self.config.strip_conversational_prefixes:
            for pattern in self.CONVERSATIONAL_PREFIXES:
                cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        # Remove trailing question marks or periods
        cleaned = re.sub(r"[?!.]+$", "", cleaned).strip()
        return cleaned if cleaned else query

    def _detect_visual_intent(self, query: str) -> bool:
        """Detects if the query targets a visual element (chart, figure, table)."""
        if not self.config.detect_visual_intent:
            return False
        q_lower = query.lower()
        return any(k in q_lower for k in self.VISUAL_KEYWORDS)

    def _strategy_keyword_isolation(self, cleaned_query: str, is_visual: bool) -> str:
        """Extracts high-information keywords and ensures visual terms are explicit."""
        words = [w for w in cleaned_query.split() if len(w) > 2]
        base = " ".join(words)
        if is_visual and not any(k in base.lower() for k in self.VISUAL_KEYWORDS):
            return f"{base} figure table chart"
        return base

    def _strategy_expanded_search(
        self,
        cleaned_query: str,
        candidates: Sequence[RetrievalCandidate],
        is_visual: bool,
        attempt: int,
    ) -> str:
        """Expands the query with domain terms or terms from the highest-scoring candidate."""
        # Try to extract a useful topic term from candidate titles/metadata if available
        context_cues: list[str] = []
        for cand in candidates[:2]:
            title = cand.metadata.get("title") or cand.metadata.get("section")
            if title and isinstance(title, str) and title not in context_cues:
                context_cues.append(title)

        if context_cues:
            return f"{cleaned_query} {' '.join(context_cues[:2])}"

        if is_visual:
            return f"{cleaned_query} diagram visual layout results"

        return f"{cleaned_query} overview key findings"

    def _generate_fallback_variation(
        self, cleaned_query: str, is_visual: bool, history_len: int
    ) -> str:
        """Ensures that identical queries are never repeated in a retrieval cycle."""
        variations = [
            f"{cleaned_query} specific details",
            f"{cleaned_query} summary data",
            f"{cleaned_query} metrics comparison",
        ]
        chosen = variations[(history_len - 1) % len(variations)]
        if is_visual:
            chosen += " figure"
        return chosen

    def clear_history(self, original_query: str | None = None) -> None:
        """Clears query reformulation history."""
        if original_query:
            self._query_history.pop(original_query, None)
        else:
            self._query_history.clear()
