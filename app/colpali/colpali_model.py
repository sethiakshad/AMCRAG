"""ColPali Model Wrapper — Milestone 5.

Loads the ColPali vision-language model and provides methods to:
  - Embed PDF page images into multi-vector representations
  - Embed text queries into multi-vector representations

ColPali uses a late-interaction scoring (MaxSim) approach:
  - Each page image → N patch vectors  (e.g. 1024 × 128-dim)
  - Each query text → M token vectors  (e.g. 32 × 128-dim)
  - Score = mean over query tokens of max cosine similarity to any page patch

Model: vidore/colpali-v1.2  (PaliGemma-based, ~3B params, needs ~6 GB VRAM)

Usage:
    model = ColPaliModel()
    page_vectors = model.embed_image(Image.open("page_001.png"))  # list[list[float]]
    query_vectors = model.embed_query("What does the bar chart show?")
    score = model.score(query_vectors, page_vectors)
"""

from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import List, Optional

# Ensure OpenMP runtime and HuggingFace cache compatibility on Windows
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports — graceful failure when colpali-engine not installed
# ---------------------------------------------------------------------------
try:
    import torch
except ImportError:
    torch = None  # type: ignore

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

try:
    from colpali_engine.models import ColPali, ColPaliProcessor
    _COLPALI_AVAILABLE = True
except ImportError:
    _COLPALI_AVAILABLE = False
    ColPali = None  # type: ignore
    ColPaliProcessor = None  # type: ignore


class ColPaliModel:
    """Wraps the ColPali vision-language model for image and query embedding.

    Supports GPU (CUDA) and CPU inference. On CPU the model is slow but
    functional — acceptable for small document collections or CI testing.

    Args:
        model_name: HuggingFace model ID (default: vidore/colpali-v1.2).
        device:     "cuda", "cpu", or "auto" (auto selects cuda if available).
        torch_dtype: Torch dtype — use torch.bfloat16 on GPU for efficiency.
    """

    DEFAULT_MODEL = "vidore/colpali-v1.2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = "auto",
        torch_dtype: Optional[str] = None,
    ) -> None:
        if not _COLPALI_AVAILABLE:
            raise ImportError(
                "colpali-engine is not installed. "
                "Run: pip install colpali-engine torch pillow"
            )

        self.model_name = model_name
        self.device = self._resolve_device(device)
        self._dtype = self._resolve_dtype(torch_dtype)

        logger.info(
            "Loading ColPali model '%s' on device='%s' dtype='%s'",
            model_name,
            self.device,
            self._dtype,
        )

        self._model: ColPali = ColPali.from_pretrained(
            model_name,
            torch_dtype=self._dtype,
            device_map=self.device,
            low_cpu_mem_usage=True,
        ).eval()

        self._processor: ColPaliProcessor = ColPaliProcessor.from_pretrained(model_name)
        logger.info("ColPali model loaded successfully.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_image(self, image: "Image.Image") -> List[List[float]]:
        """Embed a single PIL image into multi-vector patch representations.

        Args:
            image: A PIL.Image.Image object (typically a PNG of a PDF page).

        Returns:
            List of patch vectors, each a list of floats.
            Shape: [num_patches, embedding_dim]  e.g. [1024, 128]
        """
        batch = self._processor.process_images([image]).to(self.device)
        with torch.no_grad():
            embeddings = self._model(**batch)  # (1, num_patches, dim)
        # Return as plain Python list for JSON-serialisability
        return embeddings[0].cpu().float().tolist()

    def embed_images_batch(
        self, images: List["Image.Image"], batch_size: int = 4
    ) -> List[List[List[float]]]:
        """Embed multiple images in batches to manage GPU memory.

        On CPU, processes images one-by-one to maximize CPU cache locality,
        reduce peak memory overhead, and provide continuous progress logging.

        Args:
            images:     List of PIL images.
            batch_size: Number of images per GPU forward pass.

        Returns:
            List of per-image multi-vector embeddings.
        """
        if self.device == "cpu" and torch is not None:
            # Prevent PyTorch OpenMP from starving the FastAPI event loop and OS
            torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))

        all_embeddings: List[List[List[float]]] = []
        total = len(images)
        step = 1 if self.device == "cpu" else max(1, batch_size)

        logger.info(
            "Embedding %d image(s) using ColPali on %s (batch_size=%d)...",
            total,
            self.device,
            step,
        )

        try:
            from tqdm import tqdm
            batch_iter = tqdm(range(0, total, step), desc="Batches", unit="chunk", leave=True)
        except Exception:
            batch_iter = range(0, total, step)

        for i in batch_iter:
            t0 = time.time()
            batch_imgs = images[i : i + step]
            batch = self._processor.process_images(batch_imgs).to(self.device)
            with torch.no_grad():
                embeddings = self._model(**batch)  # (B, num_patches, dim)
            all_embeddings.extend(embeddings.cpu().float().tolist())
            elapsed = time.time() - t0
            end_idx = min(i + step, total)
            logger.info(
                "ColPali: Embedded page %d/%d (took %.1fs).",
                end_idx,
                total,
                elapsed,
            )
        return all_embeddings

    def embed_query(self, query_text: str) -> List[List[float]]:
        """Embed a text query into multi-vector token representations.

        Args:
            query_text: Natural language query string.

        Returns:
            List of token vectors.
            Shape: [num_tokens, embedding_dim]  e.g. [32, 128]
        """
        batch = self._processor.process_queries([query_text]).to(self.device)
        with torch.no_grad():
            embeddings = self._model(**batch)  # (1, num_tokens, dim)
        return embeddings[0].cpu().float().tolist()

    def score(
        self,
        query_vectors: List[List[float]],
        page_vectors: List[List[float]],
    ) -> float:
        """Compute the MaxSim score between a query and a page.

        MaxSim: for each query token vector, find the maximum cosine similarity
        to any page patch vector, then average across all query tokens.

        Args:
            query_vectors: Token embeddings from embed_query().
            page_vectors:  Patch embeddings from embed_image().

        Returns:
            Scalar float relevance score (higher = more relevant).
        """
        import torch.nn.functional as F

        q = torch.tensor(query_vectors, dtype=torch.float32)  # (Q, D)
        p = torch.tensor(page_vectors, dtype=torch.float32)   # (P, D)

        # Normalise both to unit length for cosine similarity
        q = F.normalize(q, dim=-1)
        p = F.normalize(p, dim=-1)

        # (Q, P) similarity matrix
        sim = torch.matmul(q, p.T)

        # MaxSim: max over pages for each query token, then mean over query tokens
        return float(sim.max(dim=1).values.mean().item())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "auto":
            if torch is not None and torch.cuda.is_available():
                return "cuda"
            return "cpu"
        return device

    @staticmethod
    def _resolve_dtype(dtype_str: Optional[str]):
        if torch is None:
            return None
        if dtype_str is None or dtype_str == "auto":
            return getattr(torch, "bfloat16", torch.float32)
        mapping = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        return mapping.get(dtype_str, getattr(torch, "bfloat16", torch.float32))

    @property
    def is_available(self) -> bool:
        """True if colpali-engine is installed and model is loaded."""
        return _COLPALI_AVAILABLE and self._model is not None
