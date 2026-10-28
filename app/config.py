"""Configuration management for Document Processing & Knowledge Base module."""

import os
from pathlib import Path
from typing import Optional
import dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load environment variables from .env file if present
dotenv.load_dotenv(override=False)


class Settings(BaseSettings):
    """Central configuration for pipeline execution and file paths."""

    # Base workspace directory (defaults to current working directory)
    base_dir: Path = Field(default_factory=Path.cwd)

    # Directories relative to base_dir or absolute
    uploads_dir: Path = Field(default=Path("data/uploads"))
    processed_dir: Path = Field(default=Path("data/processed"))
    page_images_dir: Path = Field(default=Path("data/page_images"))

    # Chunking parameters
    chunk_size: int = Field(
        default=800,
        description="Target maximum characters per chunk",
        gt=50,
    )
    chunk_overlap: int = Field(
        default=150,
        description="Character overlap between consecutive chunks",
        ge=0,
    )

    # ColPali Rendering parameters
    render_dpi: int = Field(
        default=150,
        description="DPI resolution for rendering PDF pages to images for ColPali",
        ge=72,
        le=600,
    )
    image_format: str = Field(default="png", description="Format of rendered images")

    # -----------------------------------------------------------------------
    # ColPali Visual Retrieval Settings
    # -----------------------------------------------------------------------
    colpali_enabled: bool = Field(
        default=True,
        description="Enable ColPali visual page retrieval. Set False to skip on CPU-only machines.",
    )
    colpali_model_name: str = Field(
        default="vidore/colpali-v1.2",
        description="HuggingFace model ID for the ColPali vision-language model.",
    )
    colpali_collection_name: str = Field(
        default="colpali_pages",
        description="Qdrant collection name for multi-vector ColPali page embeddings.",
    )
    colpali_top_k: int = Field(
        default=5,
        description="Number of visually relevant pages to retrieve per query.",
        gt=0,
    )
    colpali_batch_size: int = Field(
        default=4,
        description="Number of page images embedded per GPU forward pass (controls VRAM usage).",
        gt=0,
    )
    colpali_device: str = Field(
        default="auto",
        description="Inference device: 'cuda', 'cpu', or 'auto' (selects cuda if available).",
    )
    colpali_reranker_strategy: str = Field(
        default="visual_only",
        description="Reranking strategy: 'visual_only' or 'full_blend'.",
    )
    colpali_max_pages_per_doc: int = Field(
        default=20,
        description="Maximum pages to embed visually with ColPali per document (prevents CPU lockup on large documents; 0 for unlimited).",
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="URL of the running Qdrant server.",
    )

    # -----------------------------------------------------------------------
    # Visual Orchestrator (Ollama Cloud Gemma 4 Vision) Settings
    # -----------------------------------------------------------------------
    ollama_visual_api_key: Optional[str] = Field(
        default=None,
        description="Dedicated API key for Ollama Cloud Gemma 4 Vision module (OLLAMA_VISUAL_API_KEY).",
    )
    ollama_visual_model: str = Field(
        default="gemma4:31b",
        description="Ollama Cloud visual model for multimodal page embeddings and reranking.",
    )
    ollama_visual_base_url: str = Field(
        default="https://ollama.com",
        description="Base URL for Ollama Cloud API.",
    )
    gemma_visual_collection_name: str = Field(
        default="gemma_visual_pages",
        description="Qdrant collection name for Gemma 4 visual page embeddings.",
    )
    gemma_storage_path: str = Field(
        default="./data/gemma_qdrant_storage",
        description="Local storage path for embedded Qdrant visual page embeddings.",
    )

    # Scanned PDF detection heuristics
    ocr_min_chars_per_page: int = Field(
        default=40,
        description="Minimum extracted characters before flagging page/document as potentially scanned/requiring OCR",
    )
    ocr_min_doc_chars: int = Field(
        default=100,
        description="Minimum total extracted characters across all pages to pass scanned check",
    )

    # Extraction settings
    prefer_docling: bool = Field(
        default=True,
        description="Whether to attempt Docling extraction first before falling back to PyMuPDF",
    )

    # -----------------------------------------------------------------------
    # LLM & Generation Settings (Google Gemini / Ollama Cloud / Fallback)
    # -----------------------------------------------------------------------
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key. Can also be set via GEMINI_API_KEY or GOOGLE_API_KEY in .env",
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model name to use (e.g. 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-3.8-flash')",
    )
    ollama_api_key: Optional[str] = Field(
        default=None,
        description="Ollama Cloud API key. Can also be set via OLLAMA_API_KEY or OLLAMA_CLOUD_API_KEY in .env",
    )
    ollama_model: str = Field(
        default="gemma4:31b",
        description="Ollama model name (e.g. 'gemma4:31b', 'llama3.2', 'deepseek-r1', 'gpt-oss:120b')",
    )
    ollama_base_url: str = Field(
        default="https://ollama.com",
        description="Ollama server URL ('https://ollama.com' for Ollama Cloud, or 'http://localhost:11434' for local)",
    )
    llm_provider: str = Field(
        default="ollama",
        description="Default LLM provider: 'ollama', 'gemini', 'openai', or 'mock'",
    )
    llm_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="LLM generation temperature (low value ensures factual grounding)",
    )
    llm_max_tokens: int = Field(
        default=2048,
        ge=64,
        le=8192,
        description="Maximum generation tokens",
    )

    model_config = {
        "env_prefix": "AMCRAG_",
        "env_file": ".env",
        "extra": "ignore",
        "arbitrary_types_allowed": True,
    }

    def get_gemini_api_key(self) -> Optional[str]:
        """Retrieve Gemini API key checking Settings, GEMINI_API_KEY, GOOGLE_API_KEY, and AMCRAG_GEMINI_API_KEY."""
        if self.gemini_api_key:
            return self.gemini_api_key
        return (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("AMCRAG_GEMINI_API_KEY")
        )

    def get_ollama_api_key(self) -> Optional[str]:
        """Retrieve Ollama Cloud API key checking Settings, OLLAMA_API_KEY, OLLAMA_CLOUD_API_KEY, and AMCRAG_OLLAMA_API_KEY."""
        if self.ollama_api_key:
            return self.ollama_api_key
        return (
            os.environ.get("OLLAMA_API_KEY")
            or os.environ.get("OLLAMA_CLOUD_API_KEY")
            or os.environ.get("AMCRAG_OLLAMA_API_KEY")
        )

    def get_ollama_visual_api_key(self) -> Optional[str]:
        """Retrieve Ollama Visual API key checking Settings, OLLAMA_VISUAL_API_KEY, AMCRAG_OLLAMA_VISUAL_API_KEY, and OLLAMA_API_KEY."""
        if self.ollama_visual_api_key:
            return self.ollama_visual_api_key
        return (
            os.environ.get("OLLAMA_VISUAL_API_KEY")
            or os.environ.get("AMCRAG_OLLAMA_VISUAL_API_KEY")
            or self.get_ollama_api_key()
        )

    def get_uploads_path(self) -> Path:
        """Resolve and ensure uploads directory exists."""
        p = self.uploads_dir if self.uploads_dir.is_absolute() else self.base_dir / self.uploads_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_processed_path(self) -> Path:
        """Resolve and ensure processed directory exists."""
        p = self.processed_dir if self.processed_dir.is_absolute() else self.base_dir / self.processed_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_page_images_path(self) -> Path:
        """Resolve and ensure page images directory exists."""
        p = self.page_images_dir if self.page_images_dir.is_absolute() else self.base_dir / self.page_images_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_colpali_index_path(self) -> Path:
        """Resolve and ensure ColPali local index cache directory exists."""
        p = self.base_dir / "data" / "colpali_index"
        p.mkdir(parents=True, exist_ok=True)
        return p


default_settings = Settings()
