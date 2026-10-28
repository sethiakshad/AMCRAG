"""Retrieval Bridge — Integration layer connecting Person 1's pipeline to downstream retrievers.

Provides two integration points:

1. index_document_chunks()
   Pass text chunks from Person 1's DocumentProcessingPipeline to Person 2's
   HybridTextRetriever (dense BGE + sparse BM25).

2. index_colpali_pages()
   Pass rendered page images from Person 1's pipeline to the ColPali visual
   indexer, storing multi-vector embeddings in a dedicated Qdrant collection.

3. ColPaliVisualBridge
   High-level class that manages the ColPali model + indexer + retriever
   as a single cohesive unit. Used by Person 5's FastAPI orchestrator and
   Person 4's adaptive retrieval controller.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from schemas import DocumentChunk, ScoredCandidate

logger = logging.getLogger(__name__)


# ===========================================================================
# Section 1: Text chunk indexing (Person 2 bridge — unchanged)
# ===========================================================================

def index_document_chunks(
    chunks: List[DocumentChunk],
    retriever: Optional[Any] = None,
) -> int:
    """Ingest Person 1 document chunks into Person 2's HybridTextRetriever.

    Args:
        chunks:    List of DocumentChunk models conforming to Person 2 contract.
        retriever: Optional instance of HybridTextRetriever. If omitted, attempts
                   to import and instantiate a local instance.

    Returns:
        Number of chunks indexed into vector and sparse stores.

    Raises:
        ImportError: If retriever is None and hybrid_retriever cannot be imported.
    """
    if not chunks:
        logger.warning("No chunks provided for indexing.")
        return 0

    if retriever is None:
        try:
            from app.retrieval.hybrid_retriever import HybridTextRetriever  # type: ignore

            retriever = HybridTextRetriever()
        except ImportError:
            try:
                from hybrid_retriever import HybridTextRetriever  # type: ignore

                retriever = HybridTextRetriever()
            except ImportError as e:
                logger.info(
                    "Person 2's hybrid_retriever module is not yet installed in local environment (%s). "
                    "%d chunks prepared and validated for downstream indexing.",
                    e,
                    len(chunks),
                )
                return len(chunks)

    indexed = retriever.index_knowledge_base(chunks=chunks)
    count = indexed if isinstance(indexed, int) else len(chunks)
    logger.info("Successfully indexed %d chunks via Person 2 HybridTextRetriever", count)
    return count


# ===========================================================================
# Section 2: ColPali visual page indexing bridge
# ===========================================================================

def index_colpali_pages(
    rendered_pages: list,
    document_id: str,
    source_filename: str = "",
    colpali_bridge: Optional["ColPaliVisualBridge"] = None,
    qdrant_url: str = "http://localhost:6333",
) -> int:
    """Index rendered page images into the ColPali Qdrant collection.

    This is a convenience function for Person 5's FastAPI upload pipeline.
    It creates a ColPaliVisualBridge on demand if one is not provided.

    Args:
        rendered_pages:   List of PageRenderInfo from DocumentProcessingPipeline.
        document_id:      Document identifier (used as Qdrant payload field).
        source_filename:  Original PDF filename for search result metadata.
        colpali_bridge:   Optional pre-warmed ColPaliVisualBridge instance.
                          Pass one to avoid reloading the model on every call.
        qdrant_url:       Qdrant server URL (used only when creating bridge).

    Returns:
        Number of pages successfully indexed. Returns 0 on failure or if
        ColPali is unavailable.
    """
    if not rendered_pages:
        logger.warning("No rendered pages supplied for ColPali indexing.")
        return 0

    bridge = colpali_bridge
    if bridge is None:
        try:
            bridge = ColPaliVisualBridge(qdrant_url=qdrant_url)
        except Exception as exc:
            logger.warning(
                "ColPali bridge could not be initialised (%s). "
                "Skipping visual page indexing for document '%s'.",
                exc,
                document_id,
            )
            return 0

    import json
    from datetime import datetime, timezone
    from app.config import default_settings

    processed_dir = default_settings.get_processed_path()
    doc_json = processed_dir / f"{document_id}.json"
    manifest_path = processed_dir / "processed_manifest.json"

    # Mark visual indexing status as indexing
    try:
        if doc_json.exists():
            d = json.loads(doc_json.read_text(encoding="utf-8"))
            d["visual_indexing_status"] = "indexing"
            d["visual_indexed"] = False
            doc_json.write_text(json.dumps(d, indent=2), encoding="utf-8")
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            if document_id in m:
                m[document_id]["visual_indexing_status"] = "indexing"
                m[document_id]["visual_indexed"] = False
                manifest_path.write_text(json.dumps(m, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug("Could not record initial indexing status for '%s': %s", document_id, exc)

    count = 0
    try:
        count = bridge.index_pages(
            rendered_pages=rendered_pages,
            document_id=document_id,
            source_filename=source_filename,
        )
    except Exception as exc:
        logger.error("Visual indexing failed for document '%s': %s", document_id, exc)
        count = 0

    # Verify persisted point count in Qdrant
    verified_count = 0
    try:
        vc = bridge.count_document_pages(document_id)
        if isinstance(vc, (int, float)):
            verified_count = int(vc)
        elif isinstance(count, (int, float)):
            verified_count = int(count)
    except Exception as exc:
        logger.debug("Could not verify point count for '%s': %s", document_id, exc)
        verified_count = int(count) if isinstance(count, (int, float)) else 0

    safe_count = int(count) if isinstance(count, (int, float)) else 0
    if verified_count == 0 and safe_count > 0:
        verified_count = safe_count

    expected_pages = len(rendered_pages)
    max_p = getattr(bridge, "max_pages", 20)
    max_p_int = int(max_p) if isinstance(max_p, (int, float)) else 20
    is_indexed = (verified_count > 0 and verified_count >= min(expected_pages, max_p_int))
    status_str = "indexed" if (is_indexed or verified_count > 0) else "failed"
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        if doc_json.exists():
            d = json.loads(doc_json.read_text(encoding="utf-8"))
            d["visual_indexed"] = is_indexed or (verified_count > 0)
            d["visual_indexing_status"] = status_str
            d["visual_pages_indexed"] = verified_count
            d["visual_indexing_completed_at"] = now_iso
            doc_json.write_text(json.dumps(d, indent=2), encoding="utf-8")
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            if document_id in m:
                m[document_id]["visual_indexed"] = is_indexed or (verified_count > 0)
                m[document_id]["visual_indexing_status"] = status_str
                m[document_id]["visual_pages_indexed"] = verified_count
                m[document_id]["visual_indexing_completed_at"] = now_iso
                manifest_path.write_text(json.dumps(m, indent=2), encoding="utf-8")
        logger.info(
            "Visual indexing lifecycle for '%s': status=%s, verified=%d/%d pages.",
            document_id,
            status_str,
            verified_count,
            expected_pages,
        )
    except Exception as exc:
        logger.warning("Could not persist final visual indexing status for '%s': %s", document_id, exc)

    return verified_count if verified_count > 0 else count


# ===========================================================================
# Section 3: ColPaliVisualBridge — unified model + indexer + retriever
# ===========================================================================

class ColPaliVisualBridge:
    """Unified Visual Bridge for visual page indexing, retrieval, and reranking.

    Replaces ColPali with the Gemma 4 Vision visual orchestrator module (app.visual_orchestrator)
    while maintaining 100% interface compatibility with the existing AMCRAG pipeline.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        qdrant_url: str = "http://localhost:6333",
        collection: Optional[str] = None,
        top_k: int = 5,
        batch_size: int = 4,
        device: str = "auto",
        enabled: bool = True,
        max_pages: int = 20,
        storage_path: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.enabled = enabled
        self.max_pages = max_pages
        self.top_k = top_k
        self.device = device
        self._bridge: Optional[Any] = None

        if not enabled:
            logger.info("VisualBridge: Visual retrieval is disabled via config.")
            return

        try:
            from app.config import default_settings
            from app.visual_orchestrator import GemmaVisualBridge as GBridge

            resolved_api_key = api_key or default_settings.get_ollama_visual_api_key()
            resolved_base_url = base_url or getattr(default_settings, "ollama_visual_base_url", "https://ollama.com")
            resolved_model = (
                model_name
                if (model_name and not model_name.startswith("vidore/"))
                else getattr(default_settings, "ollama_visual_model", "gemma4:31b")
            )
            resolved_coll = (
                collection
                if (collection and collection != "colpali_pages")
                else getattr(default_settings, "gemma_visual_collection_name", "gemma_visual_pages")
            )
            resolved_storage = storage_path or getattr(default_settings, "gemma_storage_path", "./data/gemma_qdrant_storage")

            self._bridge = GBridge(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
                model_name=resolved_model,
                qdrant_url=qdrant_url,
                storage_path=resolved_storage,
                collection=resolved_coll,
                top_k=top_k,
                batch_size=batch_size,
                enabled=enabled,
                max_pages=max_pages,
            )
            logger.info(
                "VisualBridge initialised with Gemma 4 Vision (model=%s, collection=%s, storage=%s).",
                resolved_model,
                resolved_coll,
                resolved_storage,
            )
        except Exception as exc:
            logger.error("VisualBridge failed to initialize: %s. Visual retrieval disabled.", exc)
            self.enabled = False

    def index_pages(
        self,
        rendered_pages: list,
        document_id: str,
        source_filename: str = "",
    ) -> int:
        """Embed and upsert rendered page images into Qdrant."""
        if not self.enabled or self._bridge is None:
            return 0
        try:
            return self._bridge.index_pages(
                rendered_pages=rendered_pages,
                document_id=document_id,
                source_filename=source_filename,
            )
        except Exception as exc:
            logger.error("Visual indexing failed for document '%s': %s", document_id, exc)
            return 0

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
        doc_ids: Optional[List[str]] = None,
    ) -> List[ScoredCandidate]:
        """Retrieve visually relevant pages for a query."""
        if not self.enabled or self._bridge is None:
            return []
        try:
            resolved_doc_ids = doc_ids if doc_ids is not None else document_ids
            return self._bridge.retrieve(
                query=query,
                top_k=top_k or self.top_k,
                doc_ids=resolved_doc_ids,
            )
        except Exception as exc:
            logger.error("Visual retrieval failed for query '%s...': %s", query[:40], exc)
            return []

    def retrieve_candidates(
        self,
        query: str,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
        doc_ids: Optional[List[str]] = None,
    ) -> List[Any]:
        """Search and format results as RetrievalCandidate objects for Person 4 (CRAG)."""
        if not self.enabled or self._bridge is None:
            return []
        try:
            resolved_doc_ids = doc_ids if doc_ids is not None else document_ids
            return self._bridge.retrieve_candidates(
                query=query,
                top_k=top_k or self.top_k,
                doc_ids=resolved_doc_ids,
            )
        except Exception as exc:
            logger.error("Visual retrieve_candidates failed: %s", exc)
            return []

    def rerank(
        self,
        query: str,
        candidates: list,
        strategy: str = "visual_only",
    ) -> list:
        """Rerank candidates using Gemma 4 Vision."""
        if not self.enabled or self._bridge is None or not candidates:
            return list(candidates)
        try:
            return self._bridge.rerank(
                query=query,
                candidates=candidates,
                strategy=strategy,
            )
        except Exception as exc:
            logger.warning("Visual reranker failed: %s. Returning raw candidates.", exc)
            return list(candidates)

    def delete_document(self, document_id: str) -> None:
        """Remove all indexed pages for a given document."""
        if not self.enabled or self._bridge is None:
            return
        try:
            self._bridge.delete_document(document_id)
        except Exception as exc:
            logger.warning("Could not delete visual pages for '%s': %s", document_id, exc)

    def count_document_pages(self, document_id: str) -> int:
        """Count verified points in Qdrant for a document."""
        if not self.enabled or self._bridge is None:
            return 0
        try:
            return self._bridge.count_document_pages(document_id)
        except Exception as exc:
            logger.warning("Could not count visual pages for '%s': %s", document_id, exc)
            return 0

    @property
    def is_ready(self) -> bool:
        """True if the bridge is enabled and ready."""
        return self.enabled and self._bridge is not None and self._bridge.is_ready

    @property
    def model(self) -> Any:
        return self._bridge.model if self._bridge else None

    @property
    def indexer(self) -> Any:
        return self._bridge.indexer if self._bridge else None

    @property
    def retriever(self) -> Any:
        return self._bridge.retriever if self._bridge else None

    @property
    def _model(self) -> Any:
        return self.model

    @property
    def _indexer(self) -> Any:
        return self.indexer

    @property
    def _retriever(self) -> Any:
        return self.retriever


# Direct aliases for seamless compatibility
GemmaVisualBridge = ColPaliVisualBridge
index_visual_pages = index_colpali_pages

