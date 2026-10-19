"""ColPali Visual Retriever — Milestone 7.

Given a user query, searches the Qdrant "colpali_pages" collection using
ColPali multi-vector MaxSim scoring to return the most visually relevant
PDF pages.

Returns results as List[ScoredCandidate] with modality="visual_page" so
they integrate directly into the existing AMCRAG RRF fusion pipeline
(Person 2 / Person 4's HybridTextRetriever).

Supports:
  - Query-time document filtering (restrict search to specific documents)
  - Configurable top-K
  - Graceful fallback: returns [] when ColPali is disabled or unavailable

Usage:
    from app.colpali.colpali_retriever import ColPaliRetriever
    from app.colpali.colpali_model import ColPaliModel

    model     = ColPaliModel()
    retriever = ColPaliRetriever(model=model)

    results = retriever.retrieve(
        query="What does the accuracy comparison chart show?",
        top_k=5,
    )
    # results: List[ScoredCandidate]  with modality="visual_page"
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from schemas import ScoredCandidate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports
# ---------------------------------------------------------------------------
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False
    QdrantClient = None  # type: ignore
    qmodels = None  # type: ignore

if TYPE_CHECKING:
    from app.colpali.colpali_model import ColPaliModel


COLPALI_COLLECTION = "colpali_pages"


class ColPaliRetriever:
    """Retrieves visually relevant PDF pages using ColPali multi-vector MaxSim search.

    Args:
        model:       Loaded ColPaliModel instance.
        qdrant_url:  URL of the running Qdrant server.
        collection:  Qdrant collection name (must match ColPaliIndexer's collection).
        top_k:       Default number of pages to return per query.
        enabled:     Set False to skip ColPali retrieval (returns empty list).
    """

    def __init__(
        self,
        model: "ColPaliModel",
        qdrant_url: str = "http://localhost:6333",
        collection: str = COLPALI_COLLECTION,
        top_k: int = 5,
        enabled: bool = True,
    ) -> None:
        self.model = model
        self.collection = collection
        self.top_k = top_k
        self.enabled = enabled

        if not _QDRANT_AVAILABLE:
            raise ImportError(
                "qdrant-client is not installed. Run: pip install qdrant-client"
            )

        self._client = QdrantClient(url=qdrant_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[ScoredCandidate]:
        """Find the most visually relevant PDF pages for a query.

        Args:
            query:        Natural language query string.
            top_k:        Number of results to return (overrides instance default).
            document_ids: If provided, search only within these document IDs.

        Returns:
            List of ScoredCandidate with modality="visual_page", sorted by
            descending MaxSim score. Returns [] if disabled or on error.
        """
        if not self.enabled:
            logger.debug("ColPali retrieval is disabled, returning empty results.")
            return []

        k = top_k if top_k is not None else self.top_k

        try:
            query_vectors = self.model.embed_query(query)
        except Exception as exc:
            logger.error("ColPali query embedding failed: %s", exc)
            return []

        # Build optional document filter for Qdrant
        search_filter = self._build_filter(document_ids)

        try:
            hits = self._client.query_points(
                collection_name=self.collection,
                query=query_vectors,          # multi-vector query → Qdrant uses MaxSim
                limit=k,
                query_filter=search_filter,
                with_payload=True,
            ).points
        except Exception as exc:
            logger.error("ColPali Qdrant search failed: %s", exc)
            return []

        candidates = self._hits_to_candidates(hits)
        logger.info(
            "ColPali retrieved %d visual page candidate(s) for query: '%s...'",
            len(candidates),
            query[:60],
        )
        return candidates

    def retrieve_for_documents(
        self,
        query: str,
        document_ids: List[str],
        top_k: Optional[int] = None,
    ) -> List[ScoredCandidate]:
        """Convenience wrapper: retrieve only within specific documents."""
        return self.retrieve(query=query, top_k=top_k, document_ids=document_ids)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_filter(document_ids: Optional[List[str]]):
        """Build a Qdrant payload filter restricted to given document_ids."""
        if not document_ids or not _QDRANT_AVAILABLE:
            return None
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchAny(any=document_ids),
                )
            ]
        )

    @staticmethod
    def _hits_to_candidates(hits: list) -> List[ScoredCandidate]:
        """Convert Qdrant ScoredPoint hits to ScoredCandidate schema objects."""
        candidates: List[ScoredCandidate] = []
        for rank, hit in enumerate(hits, start=1):
            payload = hit.payload or {}
            candidates.append(
                ScoredCandidate(
                    chunk_id=payload.get(
                        "chunk_id",
                        f"{payload.get('document_id', 'unknown')}_page_{payload.get('page_number', 0):04d}",
                    ),
                    score=float(hit.score),
                    rank=rank,
                    modality="visual_page",
                    document_id=payload.get("document_id", ""),
                    page_number=int(payload.get("page_number", 1)),
                    text="",  # Visual pages have no raw text in this retrieval path
                    source_filename=payload.get("source_filename", ""),
                    page_start=int(payload.get("page_number", 1)),
                    page_end=int(payload.get("page_number", 1)),
                    metadata={
                        "image_path":    payload.get("image_path", ""),
                        "width":         payload.get("width", 0),
                        "height":        payload.get("height", 0),
                        "dpi":           payload.get("dpi", 0),
                        "title":         payload.get("title", ""),
                        "caption":       payload.get("caption", ""),
                        "colpali_score": float(hit.score),
                        "colpali_rank":  rank,
                    },
                )
            )
        return candidates
