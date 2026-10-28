"""Visual Orchestrator Module (Ollama Cloud Gemma 4 Vision).

Experimental, isolated drop-in alternative to ColPali for visual page indexing,
retrieval, and reranking powered by Gemma 4 Vision (gemma4:31b) on Ollama Cloud.

Main Classes:
- OllamaVisualClient: Direct client for Ollama Cloud multimodal vision chat.
- GemmaVisualModel: Replicates ColPaliModel (embed_image, embed_query, score).
- GemmaVisualIndexer: Replicates ColPaliIndexer (indexes pages into Qdrant).
- GemmaVisualRetriever: Replicates ColPaliRetriever (retrieves visually relevant pages).
- GemmaVisualReranker: Replicates ColPaliReranker (reranks candidates using vision scores).
- GemmaVisualBridge: Replicates ColPaliVisualBridge (unified high-level facade).
"""

from app.visual_orchestrator.client import OllamaVisualClient
from app.visual_orchestrator.model import GemmaVisualModel
from app.visual_orchestrator.indexer import GemmaVisualIndexer, GEMMA_VISUAL_COLLECTION
from app.visual_orchestrator.retriever import GemmaVisualRetriever
from app.visual_orchestrator.reranker import GemmaVisualReranker
from app.visual_orchestrator.bridge import GemmaVisualBridge

__all__ = [
    "OllamaVisualClient",
    "GemmaVisualModel",
    "GemmaVisualIndexer",
    "GemmaVisualRetriever",
    "GemmaVisualReranker",
    "GemmaVisualBridge",
    "GEMMA_VISUAL_COLLECTION",
]
