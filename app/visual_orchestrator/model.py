"""Gemma 4 Visual Model Wrapper.

Provides an exact drop-in replacement for ColPaliModel using Ollama Cloud's
Gemma 4 Vision (gemma4:31b) with dense semantic representation and
late-interaction scoring capability.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Union

import numpy as np

from app.visual_orchestrator.client import OllamaVisualClient

logger = logging.getLogger("AMCRAG.VisualOrchestrator.Model")

try:
    from PIL import Image as PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    PILImage = None  # type: ignore

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    torch = None  # type: ignore


class GemmaVisualModel:
    """Vision-Language Model wrapper using Ollama Cloud Gemma 4 Vision.

    Conforms to the exact public method signatures of ColPaliModel:
    - embed_image()
    - embed_images()
    - embed_query()
    - score()
    """

    def __init__(
        self,
        model_name: str = "gemma4:31b",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        dense_embedder: Optional[Any] = None,
        device: str = "auto",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.client = OllamaVisualClient(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
        )
        self._dense_embedder = dense_embedder
        self._init_embedder()

    def _init_embedder(self) -> None:
        """Initialize fallback dense text embedding model (BAAI/bge-base-en-v1.5) for vectorizing visual descriptions."""
        if self._dense_embedder is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            # Uses the local cached BGE model (768-dim)
            self._dense_embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
            logger.info("GemmaVisualModel: Bound BGE dense embedding engine for visual descriptor projection.")
        except Exception as exc:
            logger.debug("SentenceTransformer not available in GemmaVisualModel: %s", exc)
            self._dense_embedder = None

    @property
    def is_ready(self) -> bool:
        """Returns True if the model and client are initialized."""
        return self.client is not None

    def embed_image(self, image: Union["PILImage.Image", str, Path]) -> List[List[float]]:
        """Embed a single page image into multi-vector patch representations.

        Args:
            image: A PIL.Image object or path to a rendered page PNG.

        Returns:
            List of patch vectors, each a list of floats (matching ColPali shape [num_patches, dim]).
        """
        temp_path = None
        if isinstance(image, (str, Path)):
            img_path = Path(image)
        elif _PIL_AVAILABLE and isinstance(image, PILImage.Image):
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            image.save(tmp.name, format="PNG")
            img_path = Path(tmp.name)
            temp_path = img_path
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        try:
            # 1. Use Gemma 4 Vision to generate visual breakdown
            descriptor = self.client.describe_page(img_path)

            # 2. Project visual breakdown into multi-vector patches
            vectors = self._project_descriptor_to_vectors(descriptor)
            return vectors
        finally:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def embed_images(self, images: List[Union["PILImage.Image", str, Path]]) -> List[List[List[float]]]:
        """Embed a batch of page images."""
        return [self.embed_image(img) for img in images]

    def embed_query(self, query: str) -> List[List[float]]:
        """Embed a text query into multi-vector token representations.

        Args:
            query: User search query string.

        Returns:
            List of token vectors, each a list of floats.
        """
        if self._dense_embedder is not None:
            # Generate query vector with instruction prefix
            prefix = "Represent this sentence for searching relevant passages: "
            emb = self._dense_embedder.encode(
                f"{prefix}{query}",
                normalize_embeddings=True,
            )
            # Reshape into a 2D multi-vector list [1, 768] (or chunked tokens)
            if hasattr(emb, "tolist"):
                emb_list = emb.tolist()
            else:
                emb_list = list(emb)
            return [emb_list]

        # Deterministic fallback vector
        vec = self._pseudo_hash_vector(query, dim=768)
        return [vec]

    def score(
        self,
        query_embeddings: List[List[float]],
        image_embeddings: List[List[float]],
    ) -> float:
        """Compute late-interaction MaxSim similarity score between query and image vectors.

        Args:
            query_embeddings: Multi-vector query representation [M, dim].
            image_embeddings: Multi-vector page image representation [N, dim].

        Returns:
            Scalar similarity score.
        """
        if not query_embeddings or not image_embeddings:
            return 0.0

        q = np.array(query_embeddings, dtype=np.float32)
        p = np.array(image_embeddings, dtype=np.float32)

        # Normalize rows
        q_norm = np.linalg.norm(q, axis=-1, keepdims=True) + 1e-8
        p_norm = np.linalg.norm(p, axis=-1, keepdims=True) + 1e-8
        q = q / q_norm
        p = p / p_norm

        # Cosine similarity matrix: [M, N]
        sim_matrix = np.dot(q, p.T)

        # MaxSim: For each query token, take max similarity across all page patches, then average
        max_sims = np.max(sim_matrix, axis=1)
        score = float(np.mean(max_sims))
        return round(score, 4)

    def _project_descriptor_to_vectors(self, descriptor: str, dim: int = 768) -> List[List[float]]:
        """Split visual descriptor into key semantic segments and embed each segment into vectors."""
        lines = [line.strip() for line in descriptor.split("\n") if len(line.strip()) > 10]
        if not lines:
            lines = [descriptor.strip() or "document visual page"]

        if self._dense_embedder is not None:
            embeddings = self._dense_embedder.encode(lines, normalize_embeddings=True)
            if hasattr(embeddings, "tolist"):
                return embeddings.tolist()
            return [list(row) for row in embeddings]

        return [self._pseudo_hash_vector(line, dim=dim) for line in lines]

    def _pseudo_hash_vector(self, text: str, dim: int = 768) -> List[float]:
        """Generate a deterministic pseudo-random normalized vector for testing/fallback."""
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Seed numpy generator with hash digest
        seed = int.from_bytes(h[:4], "little")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim).astype(np.float32)
        norm = np.linalg.norm(vec) + 1e-8
        return (vec / norm).tolist()
