"""tokenizer.py — Token Counting Engine for Context Budgeting.

Provides multi-tiered token counting:
  1. tiktoken encoding (e.g. cl100k_base) if available.
  2. HuggingFace AutoTokenizer if transformers is available.
  3. High-accuracy characters-to-tokens heuristic fallback (~3.8 chars/token).
"""

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger("AMCRAG.ContextBuilder.Tokenizer")


class TokenCounter:
    """Calculates or estimates token counts across context blocks."""

    def __init__(self, tokenizer_name: str = "cl100k_base"):
        self.tokenizer_name = tokenizer_name
        self._tokenizer = None
        self._backend = "heuristic"
        self._init_tokenizer()

    def _init_tokenizer(self) -> None:
        """Attempt to initialize tiktoken or transformers tokenizer."""
        # Try tiktoken
        try:
            import tiktoken  # type: ignore

            try:
                self._tokenizer = tiktoken.get_encoding(self.tokenizer_name)
                self._backend = "tiktoken"
                logger.debug("Initialized tiktoken encoding '%s'", self.tokenizer_name)
                return
            except Exception:
                try:
                    self._tokenizer = tiktoken.encoding_for_model(self.tokenizer_name)
                    self._backend = "tiktoken"
                    logger.debug("Initialized tiktoken for model '%s'", self.tokenizer_name)
                    return
                except Exception:
                    pass
        except ImportError:
            pass

        # Try HuggingFace transformers (only if not an OpenAI tiktoken encoding)
        TIKTOKEN_ENCODINGS = {"cl100k_base", "p50k_base", "r50k_base", "o200k_base"}
        if self.tokenizer_name not in TIKTOKEN_ENCODINGS:
            try:
                from transformers import AutoTokenizer  # type: ignore

                try:
                    self._tokenizer = AutoTokenizer.from_pretrained(
                        self.tokenizer_name,
                        local_files_only=False,
                    )
                    self._backend = "transformers"
                    logger.debug("Initialized HuggingFace tokenizer '%s'", self.tokenizer_name)
                    return
                except Exception:
                    pass
            except ImportError:
                pass


        # Fallback heuristic
        self._backend = "heuristic"
        logger.debug(
            "Using robust heuristic token counter (~3.8 chars/token) for '%s'",
            self.tokenizer_name,
        )

    def count_tokens(self, text: Optional[str]) -> int:
        """Count or estimate the number of tokens in the given text.

        Args:
            text: Input string.

        Returns:
            Non-negative integer token count.
        """
        if not text:
            return 0

        if self._backend == "tiktoken" and self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception as e:
                logger.warning("tiktoken encode failed, using heuristic: %s", e)

        if self._backend == "transformers" and self._tokenizer:
            try:
                return len(self._tokenizer.encode(text, add_special_tokens=False))
            except Exception as e:
                logger.warning("transformers encode failed, using heuristic: %s", e)

        # Heuristic fallback:
        # Standard OpenAI / BGE ratio is approximately 3.8 to 4.0 characters per token in English.
        # We use ceil(len(text) / 3.8), guaranteeing at least 1 token for non-empty text.
        return max(1, math.ceil(len(text) / 3.8))

    @property
    def backend(self) -> str:
        """Return the active tokenizer backend ('tiktoken', 'transformers', or 'heuristic')."""
        return self._backend
