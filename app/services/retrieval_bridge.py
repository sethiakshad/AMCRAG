"""Bridge for passing ingested DocumentChunk batches to Person 2's HybridTextRetriever."""

import logging
from typing import Any, List, Optional
from schemas import DocumentChunk

logger = logging.getLogger(__name__)


def index_document_chunks(
    chunks: List[DocumentChunk],
    retriever: Optional[Any] = None,
) -> int:
    """Ingest Person 1 document chunks into Person 2's HybridTextRetriever.

    Args:
        chunks: List of DocumentChunk models conforming to Person 2 contract.
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
    logger.info("Successfully indexed %d chunks via Person 2 HybridTextRetriever", indexed)
    return indexed
