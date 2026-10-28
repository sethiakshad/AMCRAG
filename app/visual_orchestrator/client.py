"""Ollama Cloud Gemma 4 Vision Client Wrapper.

Manages connection to Ollama Cloud using dedicated OLLAMA_VISUAL_API_KEY,
providing visual page analysis, structured diagram description, and visual
relevance scoring via Gemma 4 Vision (gemma4:31b).
"""

from __future__ import annotations

import base64
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import dotenv

# Ensure local .env is parsed
dotenv.load_dotenv(override=False)

logger = logging.getLogger("AMCRAG.VisualOrchestrator.Client")


class OllamaVisualClient:
    """Multimodal Vision Client for Ollama Cloud Gemma 4 Vision."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback_mode: bool = True,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("OLLAMA_VISUAL_API_KEY")
            or os.getenv("OLLAMA_API_KEY")
        )
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_VISUAL_BASE_URL")
            or os.getenv("OLLAMA_BASE_URL")
            or "https://ollama.com"
        )
        self.model_name = (
            model_name
            or os.getenv("OLLAMA_VISUAL_MODEL")
            or os.getenv("OLLAMA_MODEL")
            or "gemma4:31b"
        )
        self.fallback_mode = fallback_mode
        self._client: Optional[Any] = None
        self._init_client()

    def _init_client(self) -> None:
        """Instantiate the Ollama Client with Cloud Bearer auth header if provided."""
        try:
            import ollama

            headers: Dict[str, str] = {}
            if self.api_key:
                clean_key = self.api_key.strip().strip('"').strip("'")
                headers["Authorization"] = f"Bearer {clean_key}"

            self._client = ollama.Client(
                host=self.base_url,
                headers=headers if headers else None,
            )
            logger.info(
                "OllamaVisualClient initialized (host=%s, model=%s, has_key=%s)",
                self.base_url,
                self.model_name,
                bool(self.api_key),
            )
        except Exception as exc:
            logger.warning("Could not instantiate Ollama client: %s", exc)
            self._client = None

    @property
    def is_connected(self) -> bool:
        """True if Ollama client instance is available."""
        return self._client is not None

    def describe_page(
        self,
        image_path: str | Path,
        prompt: Optional[str] = None,
    ) -> str:
        """Use Gemma 4 Vision to generate a rich semantic description of a page image.

        Extracts:
        - Main text headings, paragraphs, and sections
        - Tables, columns, and numeric metrics
        - Visual charts, diagrams, legends, and curves
        """
        path = Path(image_path)
        if not path.exists():
            logger.warning("Page image does not exist: %s", image_path)
            return f"[Page image missing: {path.name}]"

        default_prompt = (
            "You are a multimodal document visual understanding specialist. "
            "Analyze this PDF page image in detail and produce a structured description:\n"
            "1. Main title, section headings, and key textual arguments.\n"
            "2. Any tables, columns, rows, numbers, or financial/technical statistics.\n"
            "3. Any charts (bar/line/pie), diagrams, system architectures, or flowcharts.\n"
            "4. A concise list of 5-10 semantic search keywords.\n"
            "Be factual, concise, and prioritize information visible in the graphics."
        )
        user_prompt = prompt or default_prompt

        if self._client:
            try:
                response = self._client.chat(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt,
                            "images": [str(path.resolve())],
                        }
                    ],
                    options={"temperature": 0.2, "num_predict": 768},
                )
                if hasattr(response, "message") and hasattr(response.message, "content"):
                    desc = (response.message.content or "").strip()
                    if desc:
                        return desc
                if isinstance(response, dict):
                    desc = (response.get("message", {}).get("content") or "").strip()
                    if desc:
                        return desc
            except Exception as exc:
                err_str = str(exc)
                if "402" in err_str or "credits" in err_str.lower():
                    logger.warning(
                        "Ollama Cloud quota/credits required for model '%s' (402). Using deterministic visual descriptor fallback.",
                        self.model_name,
                    )
                else:
                    logger.warning("Ollama Cloud visual chat failed: %s", exc)

        # Fallback descriptor when Cloud API is unavailable or quota is exhausted
        return self._fallback_describe(path)

    def score_visual_relevance(
        self,
        query: str,
        image_path: str | Path,
        page_context: Optional[str] = None,
    ) -> float:
        """Score the relevance of a page image to the user query using Gemma 4 Vision.

        Returns:
            Calibrated float in range [0.0, 1.0].
        """
        path = Path(image_path)
        if not path.exists():
            return 0.0

        score_prompt = (
            f"You are an evaluator assessing if this page image is relevant to answering the query:\n"
            f"QUERY: \"{query}\"\n"
            f"Inspect the text, charts, tables, numbers, and diagrams on this page image.\n"
            f"Rate how relevant this page is to answering the query on a continuous scale from 0.0 to 1.0:\n"
            f"- 1.0: Directly answers the query with explicit facts, charts, or tables.\n"
            f"- 0.7: Highly relevant context or partial answer.\n"
            f"- 0.4: Marginally related topic or mentions related terms.\n"
            f"- 0.0: Completely irrelevant.\n\n"
            f"Output ONLY a single number between 0.0 and 1.0 (e.g. 0.85). Do not write any other words."
        )

        if self._client:
            try:
                response = self._client.chat(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": score_prompt,
                            "images": [str(path.resolve())],
                        }
                    ],
                    options={"temperature": 0.0, "num_predict": 16},
                )
                content = ""
                if hasattr(response, "message") and hasattr(response.message, "content"):
                    content = response.message.content or ""
                elif isinstance(response, dict):
                    content = response.get("message", {}).get("content") or ""

                match = re.search(r"([0-1]\.\d+|\d\.\d+|1\.0|0\.0|[0-1])", content)
                if match:
                    score = float(match.group(1))
                    return max(0.0, min(1.0, score))
            except Exception as exc:
                logger.debug("Visual relevance scoring call failed: %s", exc)

        # Fallback scoring: lexical/semantic heuristic over page context
        return self._fallback_score(query, path, page_context)

    # -------------------------------------------------------------------------
    # Deterministic Fallbacks for Offline / Credit Exhaustion Resilience
    # -------------------------------------------------------------------------
    def _fallback_describe(self, image_path: Path) -> str:
        """Produce a structured fallback summary from image filename, metadata, and dimensions."""
        file_size_kb = image_path.stat().st_size / 1024 if image_path.exists() else 0
        page_num_match = re.search(r"page_(\d+)", image_path.stem)
        page_num = int(page_num_match.group(1)) if page_num_match else 1
        return (
            f"[Visual Representation: Page {page_num} rendered from {image_path.name}]\n"
            f"- Image Size: {file_size_kb:.1f} KB (PNG, 150 DPI)\n"
            f"- Layout: Multimodal document page with visual diagrams and content.\n"
            f"- Visual Focus: High-resolution raster evidence for Page {page_num}."
        )

    def _fallback_score(self, query: str, image_path: Path, page_context: Optional[str] = None) -> float:
        """Compute fallback relevance score using token overlap and visual page indicators."""
        q_terms = set(re.findall(r"\w+", query.lower()))
        if not q_terms:
            return 0.5

        context = (page_context or "").lower()
        if context:
            matches = sum(1 for t in q_terms if t in context and len(t) > 2)
            ratio = matches / len(q_terms)
            return round(min(1.0, 0.45 + (0.50 * ratio)), 4)

        # Baseline visual relevance for scanned/raster pages
        return 0.50
