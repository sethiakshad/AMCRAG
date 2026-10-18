"""Automated pytest test suite for render_pdf_pages.py (Milestone 4).

Covers:
1. Collision-safe, predictable filename generation.
2. Complete page rendering and manifest JSON schema creation.
3. Configurable DPI resolution scaling.
4. Error handling on missing, empty, and corrupted files.
5. Overwrite protection for both images and manifest.
6. CLI execution on sample PDF.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from render_pdf_pages import get_image_filename, render_pdf_pages


# ---------------------------------------------------------------------------
# 1. Filename Generation
# ---------------------------------------------------------------------------


def test_filename_generation_pattern():
    """Verify filename generation produces predictable zero-padded filenames."""
    assert get_image_filename("research_paper", 1, "png") == "research_paper_page_0001.png"
    assert get_image_filename("research_paper", 42, "png") == "research_paper_page_0042.png"
    assert get_image_filename("doc", 100, "webp") == "doc_page_0100.webp"
    assert get_image_filename("my file with spaces", 5, "jpg") == "my file with spaces_page_0005.jpg"


# ---------------------------------------------------------------------------
# 2. Page Rendering and Manifest Creation
# ---------------------------------------------------------------------------


def test_render_pages_and_manifest_creation(tmp_path: Path):
    """Verify rendering a 3-page PDF creates 3 image files and a valid manifest JSON."""
    sample_pdf = Path("data/sample.pdf")
    out_dir = tmp_path / "page_images"

    manifest = render_pdf_pages(
        pdf_path=sample_pdf,
        output_dir=out_dir,
        dpi=100,
        image_format="png",
        overwrite=False,
    )

    assert manifest["source_file"] == "sample.pdf"
    assert manifest["total_pages"] == 3
    assert manifest["total_rendered_images"] == 3
    assert manifest["render_settings"]["dpi"] == 100
    assert manifest["render_settings"]["image_format"] == "png"

    # Check that manifest file exists on disk
    manifest_on_disk = out_dir / "sample_manifest.json"
    assert manifest_on_disk.exists()

    with manifest_on_disk.open("r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data["source_file"] == "sample.pdf"
    assert len(disk_data["pages"]) == 3

    # Check each page record and its corresponding image file on disk
    for i, p_info in enumerate(manifest["pages"]):
        expected_page = i + 1
        assert p_info["page_number"] == expected_page
        assert p_info["dpi"] == 100
        assert p_info["width"] > 0
        assert p_info["height"] > 0

        img_file = Path(p_info["image_path"])
        assert img_file.exists(), f"Rendered image must exist on disk: {img_file}"
        assert img_file.name == f"sample_page_{expected_page:04d}.png"


# ---------------------------------------------------------------------------
# 3. Configurable DPI Scaling
# ---------------------------------------------------------------------------


def test_configurable_dpi_scaling(tmp_path: Path):
    """Verify that different DPI settings scale pixel dimensions proportionally."""
    sample_pdf = Path("data/sample.pdf")
    dir_low = tmp_path / "low_dpi"
    dir_high = tmp_path / "high_dpi"

    res_low = render_pdf_pages(sample_pdf, output_dir=dir_low, dpi=72)
    res_high = render_pdf_pages(sample_pdf, output_dir=dir_high, dpi=150)

    p1_low = res_low["pages"][0]
    p1_high = res_high["pages"][0]

    assert p1_high["width"] > p1_low["width"]
    assert p1_high["height"] > p1_low["height"]
    assert p1_high["dpi"] == 150
    assert p1_low["dpi"] == 72


# ---------------------------------------------------------------------------
# 4. Error Handling
# ---------------------------------------------------------------------------


def test_missing_file_raises_filenotfound(tmp_path: Path):
    """Verify missing file raises FileNotFoundError."""
    missing = tmp_path / "nonexistent.pdf"
    with pytest.raises(FileNotFoundError, match="File not found"):
        render_pdf_pages(missing)


def test_empty_0byte_file_raises_valueerror(tmp_path: Path):
    """Verify empty 0-byte file raises ValueError."""
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")
    with pytest.raises(ValueError, match="PDF file is empty \\(0 bytes\\)"):
        render_pdf_pages(empty_pdf)


def test_invalid_extension_raises_valueerror(tmp_path: Path):
    """Verify non-PDF file raises ValueError."""
    txt_file = tmp_path / "file.txt"
    txt_file.write_text("not a pdf")
    with pytest.raises(ValueError, match="Unsupported file type"):
        render_pdf_pages(txt_file)


def test_invalid_dpi_raises_valueerror():
    """Verify non-positive DPI raises ValueError."""
    with pytest.raises(ValueError, match="Rendering DPI must be positive"):
        render_pdf_pages(Path("data/sample.pdf"), dpi=0)


# ---------------------------------------------------------------------------
# 5. Overwrite Protection
# ---------------------------------------------------------------------------


def test_overwrite_protection(tmp_path: Path):
    """Verify existing rendered images/manifest raise FileExistsError without overwrite=True."""
    sample_pdf = Path("data/sample.pdf")
    out_dir = tmp_path / "overwrite_test"

    # First run succeeds
    render_pdf_pages(sample_pdf, output_dir=out_dir, overwrite=False)

    # Second run fails without overwrite flag
    with pytest.raises(FileExistsError, match="already exists"):
        render_pdf_pages(sample_pdf, output_dir=out_dir, overwrite=False)

    # Third run succeeds with overwrite=True
    res = render_pdf_pages(sample_pdf, output_dir=out_dir, overwrite=True)
    assert res["total_rendered_images"] == 3


# ---------------------------------------------------------------------------
# 6. CLI Execution
# ---------------------------------------------------------------------------


def test_cli_execution_success(tmp_path: Path):
    """Verify render_pdf_pages.py executes successfully from CLI."""
    out_dir = tmp_path / "cli_render_out"
    cmd = [
        sys.executable,
        "render_pdf_pages.py",
        "data/sample.pdf",
        "--output-dir",
        str(out_dir),
        "--dpi",
        "100",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "PAGE RENDERING SUCCESSFUL" in res.stdout
    assert (out_dir / "sample_manifest.json").exists()
