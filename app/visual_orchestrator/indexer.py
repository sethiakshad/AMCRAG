"""Gemma 4 Visual Page Indexer.

Replicates the functionality of ColPaliIndexer:
- Extracts multimodal descriptions using Ollama Cloud Gemma 4 Vision
- Indexes multi-vector / dense representations into a dedicated Qdrant collection ("gemma_visual_pages")
- Stores rich visual payloads (page_number, document_id, image_path, modality="visual_page")
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.visual_orchestrator.model import GemmaVisualModel

logger = logging.getLogger("AMCRAG.VisualOrchestrator.Indexer")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False
    QdrantClient = None  # type: ignore
    qmodels = None  # type: ignore

GEMMA_VISUAL_COLLECTION = "gemma_visual_pages"
DEFAULT_VECTOR_DIM = 768


class GemmaVisualIndexer:
    """Indexes rendered PDF page images into Qdrant using Gemma 4 Vision representations."""

    def __init__(
        self,
        model: Optional[GemmaVisualModel] = None,
        qdrant_url: str = "http://localhost:6333",
        storage_path: Optional[str] = "./data/gemma_qdrant_storage",
        collection: str = GEMMA_VISUAL_COLLECTION,
        batch_size: int = 4,
        recreate: bool = False,
        client: Optional[Any] = None,
    ) -> None:
        self.model = model or GemmaVisualModel()
        self.collection = collection
        self.batch_size = batch_size
        self.client = client
        if self.client is None:
            if storage_path and (not qdrant_url or storage_path != "./data/gemma_qdrant_storage"):
                try:
                    Path(storage_path).mkdir(parents=True, exist_ok=True)
                    self.client = QdrantClient(path=storage_path)
                except Exception as exc:
                    logger.warning("Local Qdrant storage at %s locked/unavailable (%s). Using memory.", storage_path, exc)
                    self.client = QdrantClient(location=":memory:")
            else:
                self._init_qdrant(qdrant_url, storage_path, recreate)
        self._ensure_collection(recreate)

    def _init_qdrant(self, qdrant_url: str, storage_path: Optional[str], recreate: bool) -> None:
        """Connect to Qdrant server or fallback to embedded local disk / memory."""
        if not _QDRANT_AVAILABLE:
            logger.warning("qdrant-client not installed; visual indexer in mock mode.")
            return

        try:
            # First attempt connection to external Qdrant server
            client = QdrantClient(url=qdrant_url, timeout=3.0)
            client.get_collections()
            self.client = client
            logger.info("GemmaVisualIndexer connected to external Qdrant at %s", qdrant_url)
        except Exception as exc:
            logger.info("External Qdrant at %s unreachable (%s). Using local storage at %s", qdrant_url, exc, storage_path)
            try:
                if storage_path:
                    Path(storage_path).mkdir(parents=True, exist_ok=True)
                    self.client = QdrantClient(path=storage_path)
                else:
                    self.client = QdrantClient(location=":memory:")
            except Exception as e2:
                logger.warning("Could not initialize local Qdrant storage: %s. Using in-memory fallback.", e2)
                self.client = QdrantClient(location=":memory:")

        self._ensure_collection(recreate)

    def _ensure_collection(self, recreate: bool = False) -> None:
        """Create the Qdrant collection for Gemma visual pages if not already existing."""
        if not self.client:
            return

        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if recreate and self.collection in existing:
                self.client.delete_collection(self.collection)
                existing.remove(self.collection)

            if self.collection not in existing:
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=qmodels.VectorParams(
                        size=DEFAULT_VECTOR_DIM,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection '%s' (dim=%d)", self.collection, DEFAULT_VECTOR_DIM)
        except Exception as exc:
            logger.warning("Error ensuring collection '%s': %s", self.collection, exc)

    def index_page(
        self,
        image_path: str | Path,
        page_number: int,
        document_id: str,
        source_filename: str,
        page_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Index a single rendered PDF page image into Qdrant."""
        path = Path(image_path)
        if not path.exists():
            logger.warning("Cannot index missing page image: %s", image_path)
            return False

        # Generate vectors via GemmaVisualModel
        vectors = self.model.embed_image(path)
        if not vectors:
            return False

        # Use mean vector for dense point representation, with full multi-vector stored in payload
        primary_vec = vectors[0] if len(vectors) == 1 else [
            float(sum(col) / len(vectors)) for col in zip(*vectors)
        ]

        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}_page_{page_number}"))
        payload = {
            "page_number": int(page_number),
            "document_id": str(document_id),
            "source_filename": str(source_filename),
            "image_path": str(path.resolve()),
            "modality": "visual_page",
            "candidate_type": "visual_page",
            "visual_engine": "ollama_gemma4_31b",
            "extracted_text": page_text or "",
            "multi_vectors": vectors,  # Persist all patch vectors for late-interaction MaxSim
            "metadata": metadata or {},
        }

        if self.client:
            try:
                self.client.upsert(
                    collection_name=self.collection,
                    points=[
                        qmodels.PointStruct(
                            id=point_id,
                            vector=primary_vec,
                            payload=payload,
                        )
                    ],
                )
                return True
            except Exception as exc:
                logger.error("Failed to upsert page %d of document '%s': %s", page_number, document_id, exc)
                return False

        return True

    def index_rendered_pages(
        self,
        rendered_pages: List[Any],
        document_id: str,
        source_filename: Optional[str] = None,
    ) -> int:
        """Index a list of PageRenderInfo objects into Qdrant. Matches ColPaliIndexer API."""
        if not rendered_pages:
            print(f"[VisualOrchestrator] No visual chunks provided for document '{document_id}'.")
            return 0

        doc_filename = source_filename or f"{document_id}.pdf"
        total_pages = len(rendered_pages)

        print(f"[VisualOrchestrator] Ingesting {total_pages} visual chunks into Knowledge Stores...")
        print(f"[VisualEngine] Computing embeddings for {total_pages} visual chunks...")

        try:
            from tqdm import tqdm
            pbar = tqdm(total=total_pages, desc="Batches", unit="chunk", leave=True)
        except Exception:
            pbar = None

        indexed_count = 0

        for idx, page_info in enumerate(rendered_pages, start=1):
            img_path = getattr(page_info, "image_path", None)
            page_num = getattr(page_info, "page_number", idx)
            page_text = getattr(page_info, "extracted_text", None)
            meta = getattr(page_info, "metadata", {}) or {}

            if not img_path:
                if pbar:
                    pbar.update(1)
                continue

            success = self.index_page(
                image_path=img_path,
                page_number=page_num,
                document_id=document_id,
                source_filename=doc_filename,
                page_text=page_text,
                metadata=meta,
            )
            if success:
                indexed_count += 1
            if pbar:
                pbar.update(1)

        if pbar:
            pbar.close()

        print(f"[VisualEngine] Successfully indexed {indexed_count} visual vectors in Qdrant.")
        print(f"[VisualOrchestrator] Visual Knowledge Base indexing completed successfully.")

        logger.info(
            "GemmaVisualIndexer: Indexed %d/%d pages for document '%s'",
            indexed_count,
            total_pages,
            document_id,
        )
        return indexed_count

    def delete_document(self, document_id: str) -> bool:
        """Delete all indexed visual pages for a given document_id."""
        if not self.client:
            return False

        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="document_id",
                                match=qmodels.MatchValue(value=document_id),
                            )
                        ]
                    )
                ),
            )
            logger.info("Deleted visual pages for document '%s'", document_id)
            return True
        except Exception as exc:
            logger.error("Failed to delete visual pages for document '%s': %s", document_id, exc)
            return False

    def count_document_pages(self, document_id: str) -> int:
        """Count the number of indexed pages for a given document_id."""
        if not self.client:
            return 0

        try:
            res = self.client.count(
                collection_name=self.collection,
                count_filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]
                ),
            )
            return res.count
        except Exception as exc:
            logger.debug("Failed to count pages for document '%s': %s", document_id, exc)
            return 0
