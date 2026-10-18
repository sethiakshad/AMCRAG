"""Fallback extraction orchestrator ensuring resilient parsing across complex PDFs."""

import logging
from pathlib import Path
from typing import Optional

from app.config import Settings, default_settings
from app.extractors.base import BaseExtractor
from app.extractors.docling_extractor import DoclingExtractor
from app.extractors.pymupdf_extractor import PyMuPDFExtractor
from app.schemas.document import DocumentExtractionResult, ExtractionMethod

logger = logging.getLogger(__name__)


class FallbackExtractor(BaseExtractor):
    """Orchestrates Docling with automatic fallback to PyMuPDF on failure.

    This guarantees that the document processing pipeline never completely crashes
    due to layout engine errors or uninstalled native models, while explicitly logging
    which extractor handled the file and why.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        docling_extractor: Optional[DoclingExtractor] = None,
        pymupdf_extractor: Optional[PyMuPDFExtractor] = None,
    ):
        self.settings = settings or default_settings
        self.pymupdf_extractor = pymupdf_extractor or PyMuPDFExtractor(self.settings)
        self.docling_extractor = docling_extractor or DoclingExtractor(self.settings)

    def extract(self, pdf_path: Path) -> DocumentExtractionResult:
        """Extract document contents using Docling if possible, falling back to PyMuPDF."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

        # If user explicitly disabled Docling or Docling is not installed
        if not self.settings.prefer_docling or not self.docling_extractor.is_available():
            reason = "prefer_docling=False" if not self.settings.prefer_docling else "docling library not installed"
            logger.info("Using PyMuPDF directly for %s (%s)", pdf_path.name, reason)
            return self.pymupdf_extractor.extract(pdf_path, method_label=ExtractionMethod.PYMUPDF)

        # Attempt Docling extraction
        try:
            logger.info("Attempting primary extraction with Docling for %s", pdf_path.name)
            result = self.docling_extractor.extract(pdf_path)
            logger.info("Docling extraction succeeded for %s (%d pages)", pdf_path.name, result.metadata.page_count)
            return result

        except Exception as exc:
            logger.warning(
                "Docling extraction failed for %s (%s: %s). Initiating fallback to PyMuPDF.",
                pdf_path.name,
                type(exc).__name__,
                exc,
            )

            # Engage fallback
            result = self.pymupdf_extractor.extract(
                pdf_path,
                method_label=ExtractionMethod.PYMUPDF_FALLBACK,
            )

            fallback_warning = (
                f"Primary Docling extraction failed with {type(exc).__name__}: {exc}. "
                f"Successfully recovered using PyMuPDF fallback."
            )
            result.warnings.append(fallback_warning)
            return result
