"""Configuration management for Document Processing & Knowledge Base module."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


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

    model_config = {
        "env_prefix": "AMCRAG_",
        "arbitrary_types_allowed": True,
    }

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


default_settings = Settings()
