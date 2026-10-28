"""Renders PDF pages into high-resolution image files for downstream ColPali visual indexing."""

import logging
from pathlib import Path
from typing import List, Optional

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

from app.config import Settings, default_settings
from app.schemas.document import PageRenderInfo

logger = logging.getLogger(__name__)


class PageRenderer:
    """Renders PDF pages as raster image files (PNG) for visual embedding models."""

    def __init__(self, settings: Optional[Settings] = None, dpi: Optional[int] = None):
        self.settings = settings or default_settings
        self.dpi = dpi if dpi is not None else self.settings.render_dpi

    def render_document(
        self,
        pdf_path: Path,
        document_id: str,
        max_pages: Optional[int] = None,
    ) -> List[PageRenderInfo]:
        """Render pages of the given PDF to images at the configured DPI.

        For large documents (e.g. 800-page pure-text PDFs), rendering is capped
        to max_pages (defaulting to settings.colpali_max_pages_per_doc) to prevent
        excessive disk usage and slow I/O.

        Args:
            pdf_path: Path to the target PDF file.
            document_id: Unique document identifier used to namespace the output directory.
            max_pages: Optional maximum page limit to render. If None, uses settings.colpali_max_pages_per_doc.

        Returns:
            List of PageRenderInfo detailing image paths, dimensions, and page numbers.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found for rendering: {pdf_path}")
        if fitz is None:
            raise ImportError("PyMuPDF is required to render PDF pages. Run: pip install pymupdf")

        output_dir = self.settings.get_page_images_path() / document_id
        output_dir.mkdir(parents=True, exist_ok=True)

        rendered_pages: List[PageRenderInfo] = []

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error("Failed to open PDF %s for page rendering: %s", pdf_path, e)
            raise ValueError(f"Unable to render PDF pages: {e}") from e

        try:
            total_pages = len(doc)
            limit = max_pages if max_pages is not None else getattr(self.settings, "colpali_max_pages_per_doc", 20)
            render_count = min(total_pages, limit) if (limit and limit > 0) else total_pages

            if total_pages > render_count:
                logger.info(
                    "Document %s has %d pages. Rendering first %d pages for visual representations.",
                    document_id,
                    total_pages,
                    render_count,
                )

            for page_idx in range(render_count):
                page_num = page_idx + 1
                page = doc[page_idx]

                # Render page to pixmap with target DPI
                pix = page.get_pixmap(dpi=self.dpi)
                image_filename = f"page_{page_num:03d}.{self.settings.image_format}"
                image_path = output_dir / image_filename

                pix.save(str(image_path))

                width = pix.width
                height = pix.height
                del pix

                rendered_pages.append(
                    PageRenderInfo(
                        page_number=page_num,
                        image_path=str(image_path.resolve()),
                        width=width,
                        height=height,
                        dpi=self.dpi,
                        title=f"{pdf_path.name} - Page {page_num}",
                        caption=f"Rendered visual representation of {pdf_path.name} (Page {page_num})",
                    )
                )

            logger.info(
                "Rendered %d pages for document %s at %d DPI to %s",
                len(rendered_pages),
                document_id,
                self.dpi,
                output_dir,
            )
            return rendered_pages

        finally:
            doc.close()
