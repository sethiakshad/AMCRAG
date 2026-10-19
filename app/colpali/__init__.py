"""ColPali Visual Retrieval Module for AMCRAG.

This package provides multimodal document retrieval using the ColPali
vision-language model family. It enables finding visually relevant PDF pages
(charts, tables, figures, diagrams) that text-only retrieval cannot find.

Modules:
    colpali_model    - Model loader and embedding utility (image + text → vectors)
    colpali_indexer  - Indexes rendered page images into Qdrant multi-vector collection
    colpali_retriever- Retrieves visually relevant pages for a text query
    colpali_reranker - Reranks a mixed candidate list using ColPali visual scores
"""

from app.colpali.colpali_model import ColPaliModel
from app.colpali.colpali_indexer import ColPaliIndexer
from app.colpali.colpali_retriever import ColPaliRetriever
from app.colpali.colpali_reranker import ColPaliReranker

__all__ = [
    "ColPaliModel",
    "ColPaliIndexer",
    "ColPaliRetriever",
    "ColPaliReranker",
]
