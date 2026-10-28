"""Gemma 4 Visual Page Retriever.

Replicates the functionality of ColPaliRetriever:
- Encodes queries into semantic vectors
- Searches Qdrant's 'gemma_visual_pages' collection
- Re-ranks hits using late-interaction MaxSim scoring or Gemma 4 visual relevance
- Returns candidates conforming to AMCRAG ScoredCandidate / RetrievalCandidate schema
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.retrieval import RetrievalCandidate
from app.visual_orchestrator.indexer import GEMMA_VISUAL_COLLECTION
from app.visual_orchestrator.model import GemmaVisualModel
from schemas import RetrievalResult, ScoredCandidate

logger = logging.getLogger("AMCRAG.VisualOrchestrator.Retriever")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False
    QdrantClient = None  # type: ignore
    qmodels = None  # type: ignore


class GemmaVisualRetriever:
    """Retrieves visually relevant PDF pages using Gemma 4 representations and Qdrant."""

    def __init__(
        self,
        model: Optional[GemmaVisualModel] = None,
        qdrant_url: str = "http://localhost:6333",
        storage_path: Optional[str] = "./data/gemma_qdrant_storage",
        collection: str = GEMMA_VISUAL_COLLECTION,
        top_k: int = 5,
        enabled: bool = True,
        client: Optional[Any] = None,
    ) -> None:
        self.model = model or GemmaVisualModel()
        self.collection = collection
        self.top_k = top_k
        self.enabled = enabled
        self.client = client
        if self.client is None:
            if storage_path and (not qdrant_url or storage_path != "./data/gemma_qdrant_storage"):
                self.client = QdrantClient(path=storage_path)
            else:
                self._init_qdrant(qdrant_url, storage_path)

    def _init_qdrant(self, qdrant_url: str, storage_path: Optional[str]) -> None:
        """Connect to Qdrant server or fallback to embedded local disk / memory."""
        if not _QDRANT_AVAILABLE:
            return

        try:
            client = QdrantClient(url=qdrant_url, timeout=3.0)
            client.get_collections()
            self.client = client
        except Exception:
            try:
                if storage_path and Path(storage_path).exists():
                    self.client = QdrantClient(path=storage_path)
                else:
                    self.client = QdrantClient(location=":memory:")
            except Exception:
                self.client = QdrantClient(location=":memory:")

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        doc_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[ScoredCandidate]:
        """Search for top visually relevant pages matching the query.

        Returns:
            List[ScoredCandidate] conforming to Person 2 / Person 3 schema.
        """
        if not self.enabled or not query.strip():
            return []

        if doc_ids is None and document_ids is not None:
            doc_ids = document_ids

        k = top_k or self.top_k
        candidates: List[ScoredCandidate] = []

        if not self.client:
            logger.warning("Qdrant client unavailable in GemmaVisualRetriever. Returning empty list.")
            return []

        try:
            # 1. Embed query
            q_vectors = self.model.embed_query(query)
            q_vec = q_vectors[0]

            # 2. Build doc_id filter if requested
            query_filter = None
            if doc_ids:
                query_filter = qmodels.Filter(
                    should=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=did),
                        )
                        for did in doc_ids
                    ]
                )

            # 3. Query Qdrant vector collection
            if hasattr(self.client, "query_points"):
                hits = self.client.query_points(
                    collection_name=self.collection,
                    query=q_vec,
                    query_filter=query_filter,
                    limit=min(k * 2, 20),
                    with_payload=True,
                ).points
            else:
                hits = self.client.search(
                    collection_name=self.collection,
                    query_vector=q_vec,
                    query_filter=query_filter,
                    limit=min(k * 2, 20),
                    with_payload=True,
                )

            for hit in hits:
                payload = hit.payload or {}
                doc_id = payload.get("document_id", "unknown_doc")
                page_num = payload.get("page_number", 1)
                source_fn = payload.get("source_filename", f"{doc_id}.pdf")
                img_path = payload.get("image_path", "")
                text = payload.get("extracted_text") or f"Visual page {page_num} from {source_fn}"

                # Calculate late-interaction MaxSim score if patch vectors are present
                multi_vecs = payload.get("multi_vectors")
                if multi_vecs:
                    score = self.model.score(q_vectors, multi_vecs)
                else:
                    score = float(hit.score)

                metadata = {
                    "document_id": doc_id,
                    "source_filename": source_fn,
                    "page_number": int(page_num),
                    "image_path": str(img_path),
                    "modality": "visual_page",
                    "retrieval_method": "visual_gemma",
                    "retrieval_rank": len(candidates) + 1,
                    **(payload.get("metadata") or {}),
                }

                candidates.append(
                    ScoredCandidate(
                        chunk_id=f"{doc_id}_page_{page_num}",
                        text=text,
                        metadata=metadata,
                        score=round(score, 4),
                        rank=len(candidates) + 1,
                        modality="visual_page",
                        candidate_type="visual_page",
                        document_id=doc_id,
                        page_number=int(page_num),
                        source_filename=source_fn,
                    )
                )

            # Sort descending by score and slice to top-k
            candidates.sort(key=lambda c: c.score, reverse=True)
            for idx, c in enumerate(candidates, start=1):
                c.rank = idx
            return candidates[:k]

        except Exception as exc:
            logger.error("Gemma visual retrieval failed for query '%s': %s", query[:50], exc)
            return []

    def retrieve_candidates(
        self,
        query: str,
        top_k: Optional[int] = None,
        doc_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[RetrievalCandidate]:
        """Returns results as List[RetrievalCandidate] conforming to Person 4 (CRAG) schema."""
        scored = self.retrieve(query=query, top_k=top_k, doc_ids=doc_ids, document_ids=document_ids)
        results: List[RetrievalCandidate] = []

        for rank, sc in enumerate(scored, start=1):
            meta = sc.metadata or {}
            results.append(
                RetrievalCandidate(
                    candidate_id=sc.chunk_id,
                    document_id=meta.get("document_id", "unknown"),
                    source_filename=meta.get("source_filename", "document.pdf"),
                    page_start=meta.get("page_number", 1),
                    page_end=meta.get("page_number", 1),
                    candidate_type="visual_page",
                    text=sc.text,
                    page_reference=meta.get("image_path"),
                    retrieval_method="visual_gemma",
                    retrieval_rank=rank,
                    retrieval_score=sc.score,
                    metadata=meta,
                )
            )
        return results

    def retrieve_results(
        self,
        query: str,
        top_k: Optional[int] = None,
        doc_ids: Optional[List[str]] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        """Returns results as List[RetrievalResult] conforming to Person 3 / schemas.py schema."""
        scored = self.retrieve(query=query, top_k=top_k, doc_ids=doc_ids, document_ids=document_ids)
        results: List[RetrievalResult] = []

        for rank, sc in enumerate(scored, start=1):
            meta = sc.metadata or {}
            results.append(
                RetrievalResult(
                    chunk_id=sc.chunk_id,
                    document_id=meta.get("document_id", "unknown"),
                    source_filename=meta.get("source_filename", "document.pdf"),
                    page_number=meta.get("page_number", 1),
                    retrieval_method="visual_gemma",
                    score=sc.score,
                    fused_score=sc.score,
                    text=sc.text,
                    image_path=meta.get("image_path"),
                    metadata=meta,
                )
            )
        return results
