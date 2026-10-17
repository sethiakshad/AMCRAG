"""Unit tests for PDF page rendering for ColPali downstream module."""

from pathlib import Path
from app.config import Settings
from app.services.page_renderer import PageRenderer


def test_page_rendering_creates_images(sample_text_pdf: Path, test_settings: Settings):
    """Verify that PageRenderer renders images for all pages and returns valid metadata."""
    renderer = PageRenderer(settings=test_settings, dpi=100)
    doc_id = "test_doc_render"

    rendered_pages = renderer.render_document(sample_text_pdf, doc_id)

    assert len(rendered_pages) == 2

    for p_info in rendered_pages:
        assert p_info.dpi == 100
        assert p_info.width > 0
        assert p_info.height > 0
        img_p = Path(p_info.image_path)
        assert img_p.exists()
        assert img_p.suffix == ".png"
        assert f"page_{p_info.page_number:03d}.png" in img_p.name


def test_configurable_dpi_scaling(sample_text_pdf: Path, test_settings: Settings):
    """Verify that higher DPI generates higher resolution images."""
    renderer_low = PageRenderer(settings=test_settings, dpi=72)
    renderer_high = PageRenderer(settings=test_settings, dpi=150)

    pages_low = renderer_low.render_document(sample_text_pdf, "doc_dpi_low")
    pages_high = renderer_high.render_document(sample_text_pdf, "doc_dpi_high")

    assert pages_high[0].width > pages_low[0].width
    assert pages_high[0].height > pages_low[0].height
