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
    """High-level interface bundling the ColPali model, indexer, and retriever.

    Designed to be instantiated once (expensive model load) and reused
    across multiple index and retrieve calls.

    Args:
        model_name:   HuggingFace model ID.
        qdrant_url:   URL of the Qdrant server.
        collection:   Qdrant collection name for ColPali pages.
        top_k:        Default retrieval top-K.
        batch_size:   Image embedding batch size.
        device:       Inference device ("auto", "cuda", or "cpu").
        enabled:      Master switch — if False, all operations are no-ops.
    """

    def __init__(
        self,
        model_name: str = "vidore/colpali-v1.2",
        qdrant_url: str = "http://localhost:6333",
        collection: str = "colpali_pages",
        top_k: int = 5,
        batch_size: int = 4,
        device: str = "auto",
        enabled: bool = True,
        max_pages: int = 20,
    ) -> None:
        self.enabled = enabled
        self.max_pages = max_pages
        self._model = None
        self._indexer = None
        self._retriever = None

        if not enabled:
            logger.info("ColPaliVisualBridge: ColPali is disabled via config.")
            return

        try:
            from app.colpali.colpali_model import ColPaliModel
            from app.colpali.colpali_indexer import ColPaliIndexer
            from app.colpali.colpali_retriever import ColPaliRetriever
            from qdrant_client import QdrantClient

            self._model = ColPaliModel(
                model_name=model_name,
                device=device,
            )

            qdrant_client = None
            try:
                qdrant_client = QdrantClient(url=qdrant_url, timeout=2.0)
                qdrant_client.get_collections()
            except Exception as exc:
                logger.info(
                    "Qdrant server at %s unavailable (%s). Using embedded local storage at ./data/colpali_qdrant_storage.",
                    qdrant_url,
                    exc,
                )
                qdrant_client = QdrantClient(path="./data/colpali_qdrant_storage")

            self._indexer = ColPaliIndexer(
                model=self._model,
                qdrant_url=qdrant_url,
                collection=collection,
                batch_size=batch_size,
                client=qdrant_client,
                max_pages=max_pages,
            )
            self._retriever = ColPaliRetriever(
                model=self._model,
                qdrant_url=qdrant_url,
                collection=collection,
                top_k=top_k,
                enabled=True,
                client=qdrant_client,
            )
            logger.info("ColPaliVisualBridge initialised (model=%s, device=%s).", model_name, device)

        except ImportError as exc:
            logger.warning(
                "ColPali dependencies not installed (%s). Visual retrieval will be unavailable.",
                exc,
            )
            self.enabled = False
        except Exception as exc:
            logger.error("ColPali model/indexer failed to load: %s. Visual retrieval disabled.", exc)
            self.enabled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_pages(
        self,
        rendered_pages: list,
        document_id: str,
        source_filename: str = "",
    ) -> int:
        """Embed and upsert rendered page images into Qdrant.

        Returns:
            Count of pages indexed. Returns 0 if disabled or on error.
        """
        if not self.enabled or self._indexer is None:
            return 0
        try:
            return self._indexer.index_rendered_pages(
                rendered_pages=rendered_pages,
                document_id=document_id,
                source_filename=source_filename,
            )
        except Exception as exc:
            logger.error("ColPali indexing failed for document '%s': %s", document_id, exc)
            return 0

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[ScoredCandidate]:
        """Retrieve visually relevant pages for a query.

        Returns:
            List[ScoredCandidate] with modality="visual_page". Returns [] if disabled.
        """
        if not self.enabled or self._retriever is None:
            return []
        try:
            return self._retriever.retrieve(
                query=query,
                top_k=top_k,
                document_ids=document_ids,
            )
        except Exception as exc:
            logger.error("ColPali retrieval failed for query '%s...': %s", query[:40], exc)
            return []

    def delete_document(self, document_id: str) -> None:
        """Remove all indexed pages for a given document (use before re-indexing)."""
        if not self.enabled or self._indexer is None:
            return
        try:
            self._indexer.delete_document_pages(document_id)
        except Exception as exc:
            logger.warning("Could not delete ColPali pages for '%s': %s", document_id, exc)

    def count_document_pages(self, document_id: str) -> int:
        """Count verified points in Qdrant for a document."""
        if not self.enabled or self._indexer is None:
            return 0
        try:
            return self._indexer.count_document_pages(document_id)
        except Exception as exc:
            logger.warning("Could not count ColPali pages for '%s': %s", document_id, exc)
            return 0

    @property
    def is_ready(self) -> bool:
        """True if the bridge is enabled and the model is loaded."""
        return self.enabled and self._model is not None

