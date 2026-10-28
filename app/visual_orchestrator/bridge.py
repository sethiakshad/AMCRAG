"""Gemma 4 Visual Bridge Service.

Replicates the high-level interface of ColPaliVisualBridge:
- Bundles the Gemma 4 Vision client, model, indexer, retriever, and reranker
- Provides high-level index_pages(), retrieve(), and rerank() methods
- Completely isolated in app/visual_orchestrator/ for experimental benchmarking
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

from app.schemas.retrieval import RetrievalCandidate
from app.visual_orchestrator.client import OllamaVisualClient
from app.visual_orchestrator.indexer import GEMMA_VISUAL_COLLECTION, GemmaVisualIndexer
from app.visual_orchestrator.model import GemmaVisualModel
from app.visual_orchestrator.reranker import GemmaVisualReranker, RerankerStrategy
from app.visual_orchestrator.retriever import GemmaVisualRetriever
from schemas import RetrievalResult, ScoredCandidate

logger = logging.getLogger("AMCRAG.VisualOrchestrator.Bridge")


class GemmaVisualBridge:
    """High-level unified interface for Ollama Cloud Gemma 4 visual operations.

    Drop-in replacement for ColPaliVisualBridge.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: str = "gemma4:31b",
        qdrant_url: str = "http://localhost:6333",
        storage_path: Optional[str] = "./data/gemma_qdrant_storage",
        collection: str = GEMMA_VISUAL_COLLECTION,
        top_k: int = 5,
        batch_size: int = 4,
        enabled: bool = True,
        max_pages: int = 20,
    ) -> None:
        self.enabled = enabled
        self.top_k = top_k
        self.max_pages = max_pages
        self.collection = collection

        self.client = OllamaVisualClient(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
        )
        self.model = GemmaVisualModel(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
        )
        self.indexer = GemmaVisualIndexer(
            model=self.model,
            qdrant_url=qdrant_url,
            storage_path=storage_path,
            collection=collection,
            batch_size=batch_size,
        )
        self.retriever = GemmaVisualRetriever(
            model=self.model,
            qdrant_url=qdrant_url,
            storage_path=storage_path,
            collection=collection,
            top_k=top_k,
            enabled=enabled,
            client=self.indexer.client,
        )
        self.reranker = GemmaVisualReranker(
            client=self.client,
            strategy="visual_only",
        )
        logger.info(
            "GemmaVisualBridge initialized (model=%s, collection=%s, enabled=%s)",
            model_name,
            collection,
            enabled,
        )

    @property
    def is_ready(self) -> bool:
        """Returns True if the bridge is enabled and indexer/retriever are ready."""
        return self.enabled and self.model.is_ready

    def index_pages(
        self,
        rendered_pages: List[Any],
        document_id: str,
        source_filename: Optional[str] = None,
    ) -> int:
        """Index rendered PDF page images into the visual collection.

        Enforces max_pages limit to prevent excessive API quota usage on large documents.
        """
        if not self.enabled:
            logger.info("GemmaVisualBridge: Visual indexing is disabled.")
            return 0

        if not rendered_pages:
            logger.warning("No rendered pages provided to index for '%s'.", document_id)
            return 0

        pages_to_index = rendered_pages
        if self.max_pages > 0 and len(rendered_pages) > self.max_pages:
            logger.info(
                "GemmaVisualBridge: Document '%s' has %d pages; capping visual indexing to %d.",
                document_id,
                len(rendered_pages),
                self.max_pages,
            )
            pages_to_index = rendered_pages[:self.max_pages]

        return self.indexer.index_rendered_pages(
            rendered_pages=pages_to_index,
            document_id=document_id,
            source_filename=source_filename,
        )

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        doc_ids: Optional[List[str]] = None,
    ) -> List[ScoredCandidate]:
        """Search the visual collection for pages matching the query."""
        if not self.enabled:
            return []
        return self.retriever.retrieve(query=query, top_k=top_k, doc_ids=doc_ids)

    def retrieve_candidates(
        self,
        query: str,
        top_k: Optional[int] = None,
        doc_ids: Optional[List[str]] = None,
    ) -> List[RetrievalCandidate]:
        """Search and format results as RetrievalCandidate objects for Person 4 (CRAG)."""
        if not self.enabled:
            return []
        return self.retriever.retrieve_candidates(query=query, top_k=top_k, doc_ids=doc_ids)

    def rerank(
        self,
        query: str,
        candidates: List[RetrievalResult],
        strategy: RerankerStrategy = "visual_only",
    ) -> List[RetrievalResult]:
        """Rerank a mixed list of candidates using Gemma 4 Vision."""
        if not self.enabled or not candidates:
            return list(candidates)
        return self.reranker.rerank(query=query, candidates=candidates, strategy=strategy)

    def delete_document(self, document_id: str) -> bool:
        """Delete all indexed visual pages for the given document."""
        return self.indexer.delete_document(document_id)

    def count_document_pages(self, document_id: str) -> int:
        """Count the number of indexed pages for the document."""
        return self.indexer.count_document_pages(document_id)
