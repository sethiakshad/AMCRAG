"""ColPali Page Indexer — Milestone 6.

Reads rendered page images (produced by Person 1's PageRenderer / render_pdf_pages.py)
and stores their multi-vector ColPali embeddings in a dedicated Qdrant collection.

Key design decisions:
  - Separate Qdrant collection "colpali_pages" uses MultiVectorConfig so each
    point stores N patch vectors instead of a single flat vector.
  - Points carry rich payload (page_number, document_id, source_filename,
    image_path, modality="visual_page") so downstream modules can build
    ScoredCandidate / RetrievalResult objects directly from search hits.
  - Indexing is idempotent: re-indexing the same page_id overwrites the old
    point without raising an error.
  - GPU batch size is configurable to avoid OOM on smaller GPUs.

Usage:
    from app.colpali.colpali_indexer import ColPaliIndexer
    from app.colpali.colpali_model import ColPaliModel

    model   = ColPaliModel()
    indexer = ColPaliIndexer(model=model)
    count   = indexer.index_rendered_pages(rendered_pages, document_id="doc_abc")
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports
# ---------------------------------------------------------------------------
try:
    from PIL import Image as PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    PILImage = None  # type: ignore

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
    from app.schemas.document import PageRenderInfo


COLPALI_COLLECTION = "colpali_pages"
COLPALI_VECTOR_DIM = 128          # Each ColPali patch embedding dimension
COLPALI_DISTANCE   = "Cosine"     # Distance metric for Qdrant


class ColPaliIndexer:
    """Indexes rendered PDF page images into Qdrant using ColPali multi-vector embeddings.

    Args:
        model:         Loaded ColPaliModel instance.
        qdrant_url:    URL of the running Qdrant server (default: localhost:6333).
        collection:    Qdrant collection name (default: "colpali_pages").
        batch_size:    Number of images embedded per GPU call.
        recreate:      If True, drops and recreates the collection on init.
    """

    def __init__(
        self,
        model: "ColPaliModel",
        qdrant_url: str = "http://localhost:6333",
        collection: str = COLPALI_COLLECTION,
        batch_size: int = 4,
        recreate: bool = False,
        client: Optional["QdrantClient"] = None,
        max_pages: int = 20,
    ) -> None:
        if not _QDRANT_AVAILABLE:
            raise ImportError(
                "qdrant-client is not installed. Run: pip install qdrant-client"
            )
        if not _PIL_AVAILABLE:
            raise ImportError(
                "Pillow is not installed. Run: pip install pillow"
            )

        self.model = model
        self.collection = collection
        self.batch_size = batch_size
        self.max_pages = max_pages
        if client is not None:
            self._client = client
        else:
            try:
                self._client = QdrantClient(url=qdrant_url, timeout=2.0)
                self._client.get_collections()
            except Exception as exc:
                logger.info(
                    "Qdrant server at %s unavailable (%s). Falling back to local embedded Qdrant storage at ./data/colpali_qdrant_storage.",
                    qdrant_url,
                    exc,
                )
                self._client = QdrantClient(path="./data/colpali_qdrant_storage")

        self._ensure_collection(recreate=recreate)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_rendered_pages(
        self,
        rendered_pages: List["PageRenderInfo"],
        document_id: str,
        source_filename: str = "",
    ) -> int:
        """Embed and upsert all rendered page images into Qdrant.

        Args:
            rendered_pages:   List of PageRenderInfo from Person 1's pipeline.
            document_id:      Unique document identifier (e.g. SHA-256 hash).
            source_filename:  Original PDF filename for payload metadata.

        Returns:
            Number of pages successfully indexed.
        """
        if not rendered_pages:
            logger.warning("No rendered pages provided to index for document '%s'.", document_id)
            return 0

        pages_to_index = rendered_pages
        if self.max_pages and len(rendered_pages) > self.max_pages:
            logger.warning(
                "Document '%s' has %d pages. Visual indexing is capped at the first %d pages on %s to prevent CPU delays.",
                document_id,
                len(rendered_pages),
                self.max_pages,
                getattr(self.model, "device", "cpu"),
            )
            pages_to_index = rendered_pages[: self.max_pages]

        logger.info(
            "Indexing %d page(s) for document '%s' into Qdrant collection '%s'.",
            len(pages_to_index),
            document_id,
            self.collection,
        )

        # Load all images upfront for batch embedding
        images, valid_pages = self._load_images(pages_to_index)
        if not images:
            logger.error("No valid images could be loaded for document '%s'.", document_id)
            return 0

        # Embed in batches
        all_embeddings = self.model.embed_images_batch(images, batch_size=self.batch_size)

        # Build Qdrant PointStructs and upsert
        points = []
        for page_info, page_vectors in zip(valid_pages, all_embeddings):
            page_num = getattr(page_info, "page_number", None) or (page_info.get("page_number", 1) if isinstance(page_info, dict) else 1)
            img_path = getattr(page_info, "image_path", "") or (page_info.get("image_path", "") if isinstance(page_info, dict) else "")
            width = getattr(page_info, "width", 0) or (page_info.get("width", 0) if isinstance(page_info, dict) else 0)
            height = getattr(page_info, "height", 0) or (page_info.get("height", 0) if isinstance(page_info, dict) else 0)
            dpi = getattr(page_info, "dpi", 150) or (page_info.get("dpi", 150) if isinstance(page_info, dict) else 150)
            title = getattr(page_info, "title", "") or (page_info.get("title", "") if isinstance(page_info, dict) else "")
            caption = getattr(page_info, "caption", "") or (page_info.get("caption", "") if isinstance(page_info, dict) else "")

            point_id = self._make_point_id(document_id, page_num)
            payload = {
                "document_id":    document_id,
                "page_number":    page_num,
                "source_filename": source_filename or "",
                "image_path":     img_path,
                "width":          width,
                "height":         height,
                "dpi":            dpi,
                "title":          title or "",
                "caption":        caption or "",
                "modality":       "visual_page",
                "chunk_id":       f"{document_id}_page_{page_num:04d}",
            }
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=page_vectors,   # list[list[float]] = multi-vector
                    payload=payload,
                )
            )

        self._client.upsert(collection_name=self.collection, points=points)
        logger.info(
            "Successfully upserted %d page embeddings for document '%s'.",
            len(points),
            document_id,
        )
        return len(points)

    def delete_document_pages(self, document_id: str) -> int:
        """Remove all indexed pages belonging to a document (for re-indexing).

        Args:
            document_id: The document whose pages should be removed.

        Returns:
            Number of points deleted (estimated from scroll count before deletion).
        """
        result = self._client.delete(
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
        logger.info("Deleted pages for document '%s' from ColPali index.", document_id)
        return 0  # Qdrant delete does not return a count directly

    def collection_count(self) -> int:
        """Return total number of indexed page points in the collection."""
        info = self._client.get_collection(self.collection)
        return info.points_count or 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_collection(self, recreate: bool = False) -> None:
        """Create the Qdrant multi-vector collection if it does not exist."""
        existing = [c.name for c in self._client.get_collections().collections]

        if recreate and self.collection in existing:
            logger.warning("Recreating Qdrant collection '%s'.", self.collection)
            self._client.delete_collection(self.collection)
            existing = []

        if self.collection not in existing:
            logger.info(
                "Creating Qdrant multi-vector collection '%s' (dim=%d).",
                self.collection,
                COLPALI_VECTOR_DIM,
            )
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(
                    size=COLPALI_VECTOR_DIM,
                    distance=qmodels.Distance.COSINE,
                    multivector_config=qmodels.MultiVectorConfig(
                        comparator=qmodels.MultiVectorComparator.MAX_SIM,
                    ),
                ),
            )
            # Create payload index for fast document_id filtering
            self._client.create_payload_index(
                collection_name=self.collection,
                field_name="document_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
            logger.info("Collection '%s' created successfully.", self.collection)
        else:
            logger.debug("Qdrant collection '%s' already exists.", self.collection)

    @staticmethod
    def _load_images(
        rendered_pages: List[Any],
    ) -> tuple[List, List[Any]]:
        """Load PIL images from disk, skipping missing files with a warning."""
        images = []
        valid_pages = []
        for page_info in rendered_pages:
            img_path_str = getattr(page_info, "image_path", None) or (page_info.get("image_path") if isinstance(page_info, dict) else None)
            page_num = getattr(page_info, "page_number", None) or (page_info.get("page_number", 1) if isinstance(page_info, dict) else 1)
            if not img_path_str:
                continue
            img_path = Path(img_path_str)
            if not img_path.exists():
                logger.warning(
                    "Rendered image not found, skipping page %d: %s",
                    page_num,
                    img_path,
                )
                continue
            try:
                img = PILImage.open(img_path).convert("RGB")
                images.append(img)
                valid_pages.append(page_info)
            except Exception as exc:
                logger.warning(
                    "Failed to open image for page %d (%s): %s",
                    page_num,
                    img_path,
                    exc,
                )
        return images, valid_pages

    @staticmethod
    def _make_point_id(document_id: str, page_number: int) -> str:
        """Generate a stable, unique string ID for a Qdrant point.

        Uses UUID5 (name-based deterministic UUID) so re-indexing the same
        page always produces the same point ID (idempotent upsert).
        """
        name = f"{document_id}__page__{page_number}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
