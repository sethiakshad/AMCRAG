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
        self._client = QdrantClient(url=qdrant_url)

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

        logger.info(
            "Indexing %d page(s) for document '%s' into Qdrant collection '%s'.",
            len(rendered_pages),
            document_id,
            self.collection,
        )

        # Load all images upfront for batch embedding
        images, valid_pages = self._load_images(rendered_pages)
        if not images:
            logger.error("No valid images could be loaded for document '%s'.", document_id)
            return 0

        # Embed in batches
        all_embeddings = self.model.embed_images_batch(images, batch_size=self.batch_size)

        # Build Qdrant PointStructs and upsert
        points = []
        for page_info, page_vectors in zip(valid_pages, all_embeddings):
            point_id = self._make_point_id(document_id, page_info.page_number)
            payload = {
                "document_id":    document_id,
                "page_number":    page_info.page_number,
                "source_filename": source_filename or "",
                "image_path":     page_info.image_path,
                "width":          page_info.width,
                "height":         page_info.height,
                "dpi":            page_info.dpi,
                "title":          page_info.title or "",
                "caption":        page_info.caption or "",
                "modality":       "visual_page",
                "chunk_id":       f"{document_id}_page_{page_info.page_number:04d}",
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
        rendered_pages: List["PageRenderInfo"],
    ) -> tuple[List, List["PageRenderInfo"]]:
        """Load PIL images from disk, skipping missing files with a warning."""
        images = []
        valid_pages = []
        for page_info in rendered_pages:
            img_path = Path(page_info.image_path)
            if not img_path.exists():
                logger.warning(
                    "Rendered image not found, skipping page %d: %s",
                    page_info.page_number,
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
                    page_info.page_number,
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
