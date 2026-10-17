"""Abstract base class interface for document extractors."""

from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.document import DocumentExtractionResult


class BaseExtractor(ABC):
    """Abstract interface for PDF document extractors."""

    @abstractmethod
    def extract(self, pdf_path: Path) -> DocumentExtractionResult:
        """Extract text, tables, and structure from a PDF file.

        Args:
            pdf_path: Filesystem path to the PDF file.

        Returns:
            DocumentExtractionResult containing pages, tables, scanned status, and metadata.

        Raises:
            FileNotFoundError: If the PDF path does not exist.
            ValueError: If the file is not a valid PDF.
            Exception: If unrecoverable extraction failure occurs.
        """
        pass
