"""retriever.py — Standard top-k dense vector similarity retriever for Normal RAG."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Union

from app.normal_rag.config import NormalRAGConfig
from app.normal_rag.schemas import NormalRAGChunk
from schemas import DocumentChunk

logger = logging.getLogger("NormalRAG.Retriever")


class NormalRAGRetriever:
    """Conventional Dense Vector Similarity Retriever.

    Uses BAAI/bge-base-en-v1.5 text embeddings and Qdrant vector database
    for cosine similarity retrieval. Does NOT use ColPali visual retrieval,
    BM25 sparse retrieval, or RRF fusion.
    """

    def __init__(
        self,
        config: Optional[NormalRAGConfig] = None,
        dense_engine: Optional[Any] = None,
    ):
        self.config = config or NormalRAGConfig()
        self._dense_engine = dense_engine

        if self._dense_engine is None:
            self._init_dense_engine()

    def _init_dense_engine(self) -> None:
        """Initialize BGEDenseEngine with robust lock and fallback handling."""
        try:
            from app.retrieval.dense_engine import BGEDenseEngine

            self._dense_engine = BGEDenseEngine(
                model_name=self.config.dense_model_name,
                collection_name=self.config.collection_name,
                qdrant_path=self.config.qdrant_path,
                qdrant_url=self.config.qdrant_url,
                qdrant_api_key=self.config.qdrant_api_key,
                device=self.config.device,
            )
            logger.info(
                "Initialized NormalRAGRetriever with BGEDenseEngine (collection='%s', model='%s')",
                self.config.collection_name,
                self.config.dense_model_name,
            )
        except Exception as exc:
            # Handle potential Qdrant storage lock conflicts on Windows or missing dependencies
            logger.warning(
                "Could not initialize persistent Qdrant at path '%s': %s. Falling back to in-memory Qdrant.",
                self.config.qdrant_path,
                exc,
            )
            try:
                from app.retrieval.dense_engine import BGEDenseEngine

                self._dense_engine = BGEDenseEngine(
                    model_name=self.config.dense_model_name,
                    collection_name=self.config.collection_name,
                    qdrant_path=None,  # in-memory :memory:
                    device=self.config.device,
                )
                logger.info("NormalRAGRetriever fallback to in-memory Qdrant succeeded.")
            except Exception as inner_exc:
                logger.error("Failed to initialize in-memory BGEDenseEngine: %s", inner_exc)
                self._dense_engine = None

    @property
    def is_ready(self) -> bool:
        """True if dense vector engine is initialized."""
        return self._dense_engine is not None

    def index_chunks(self, chunks: Sequence[Union[DocumentChunk, Dict[str, Any]]]) -> int:
        """Index a batch of text chunks into the vector store.

        Args:
            chunks: Sequence of DocumentChunk objects or raw chunk dictionaries.

        Returns:
            Number of indexed chunks.
        """
        if not chunks:
            logger.warning("No chunks supplied for Normal RAG indexing.")
            return 0

        # Standardize chunks into DocumentChunk models
        standardized_chunks: List[DocumentChunk] = []
        for item in chunks:
            if isinstance(item, DocumentChunk):
                standardized_chunks.append(item)
            elif isinstance(item, dict):
                try:
                    standardized_chunks.append(DocumentChunk.model_validate(item))
                except Exception as e:
                    logger.warning("Could not parse chunk dict into DocumentChunk: %s", e)
            elif hasattr(item, "text") and hasattr(item, "chunk_id"):
                standardized_chunks.append(
                    DocumentChunk(
                        chunk_id=getattr(item, "chunk_id"),
                        document_id=getattr(item, "document_id", "doc"),
                        page_number=getattr(item, "page_number", 1),
                        page_start=getattr(item, "page_start", 1),
                        page_end=getattr(item, "page_end", 1),
                        text=getattr(item, "text", ""),
                        source_filename=getattr(item, "source_filename", None),
                        metadata=getattr(item, "metadata", {}) or {},
                    )
                )

        if not standardized_chunks:
            return 0

        if self._dense_engine is not None:
            self._dense_engine.index_chunks(standardized_chunks)
            logger.info("Indexed %d chunks into Normal RAG vector store.", len(standardized_chunks))
            return len(standardized_chunks)
        else:
            logger.error("Cannot index chunks: dense_engine is not initialized.")
            return 0

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[NormalRAGChunk]:
        """Execute top-k dense vector similarity search for the given query.

        Args:
            query: The user's search query text.
            top_k: Number of chunks to retrieve. Defaults to config.top_k.
            document_ids: Optional list of document identifiers to filter search scope.

        Returns:
            Rank-ordered list of NormalRAGChunk models.
        """
        if not query or not query.strip():
            return []

        if self._dense_engine is None:
            logger.warning("Dense engine is unavailable. Returning 0 candidates.")
            return []

        effective_top_k = top_k if (top_k is not None and top_k > 0) else self.config.top_k

        # Construct filters if document_ids are provided
        filters = None
        if document_ids and len(document_ids) == 1:
            filters = {"document_id": document_ids[0]}

        try:
            raw_candidates = self._dense_engine.search(
                query=query,
                top_k=effective_top_k,
                filters=filters,
            )
        except Exception as exc:
            logger.error("Dense vector search failed: %s", exc, exc_info=True)
            return []

        # If multi-document filtering was requested, filter post-retrieval if necessary
        if document_ids and len(document_ids) > 1:
            allowed_docs = set(document_ids)
            raw_candidates = [c for c in raw_candidates if getattr(c, "document_id", "") in allowed_docs]

        # Apply similarity threshold if configured
        if self.config.similarity_threshold is not None:
            raw_candidates = [
                c for c in raw_candidates if getattr(c, "score", 0.0) >= self.config.similarity_threshold
            ]

        results: List[NormalRAGChunk] = []
        for rank, item in enumerate(raw_candidates[:effective_top_k], start=1):
            meta = getattr(item, "metadata", {}) or {}
            if hasattr(meta, "model_dump"):
                meta = meta.model_dump()
            elif not isinstance(meta, dict):
                meta = dict(meta)

            chunk_id = getattr(item, "chunk_id", f"chunk_{rank}")
            doc_id = getattr(item, "document_id", "")
            page_num = getattr(item, "page_number", 1)
            page_start = getattr(item, "page_start", None) or page_num
            page_end = getattr(item, "page_end", None) or page_num
            text = getattr(item, "text", "") or ""
            score = float(getattr(item, "score", 0.0))
            source_file = (
                getattr(item, "source_filename", None)
                or meta.get("source_filename")
                or meta.get("document_name")
            )

            results.append(
                NormalRAGChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    source_filename=source_file,
                    page_number=page_num,
                    page_start=page_start,
                    page_end=page_end,
                    text=text,
                    score=round(score, 4),
                    rank=rank,
                    metadata=meta,
                )
            )

        return results
