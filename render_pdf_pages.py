"""render_pdf_pages.py - Milestone 4: PDF Page Rendering for Downstream Visual Retrieval.

Module: Person 1 (Document Processing & Knowledge Base Preparation)
Project: AMCRAG (Adaptive Multimodal Corrective RAG)

Usage:
    python render_pdf_pages.py data/sample.pdf
    python render_pdf_pages.py data/sample.pdf --dpi 200 --output-dir data/page_images
    python render_pdf_pages.py data/sample.pdf --overwrite
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf as fitz


def get_image_filename(pdf_stem: str, page_number: int, image_format: str = "png") -> str:
    """Generate a collision-safe, predictable filename for a rendered page image.

    Format: <pdf_stem>_page_<04d_page_number>.<format>
    Example: 'sample_paper_page_0001.png'

    Args:
        pdf_stem: Filename without extension.
        page_number: 1-based page number.
        image_format: Image file extension (default: 'png').

    Returns:
        A predictable, formatted filename string.
    """
    return f"{pdf_stem}_page_{page_number:04d}.{image_format.lower()}"


def render_pdf_pages(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    dpi: int = 150,
    image_format: str = "png",
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Render all pages of a PDF into individual image files one at a time.

    Memory-efficient: Each page's pixmap is rasterized, written to disk,
    and immediately deallocated before moving to the next page.

    Args:
        pdf_path: Filesystem path to the input PDF.
        output_dir: Destination directory. Defaults to 'data/page_images/<pdf_stem>'.
        dpi: Rendering resolution in dots per inch (default: 150).
        image_format: Image format extension ('png', 'jpeg', etc.).
        overwrite: Whether to overwrite existing files.

    Returns:
        A manifest dictionary mapping each page to its image file and dimensions.

    Raises:
        FileNotFoundError: If pdf_path does not exist.
        ValueError: If file is not a valid PDF or has 0 pages.
        FileExistsError: If destination files exist and overwrite is False.
    """
    if not str(pdf_path).strip():
        raise ValueError("PDF file path cannot be empty.")

    if not pdf_path.exists():
        raise FileNotFoundError(f"File not found: '{pdf_path.resolve()}'")

    if not pdf_path.is_file():
        raise ValueError(f"Path is not a file: '{pdf_path.resolve()}'")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Unsupported file type '{pdf_path.suffix}'. Please provide a file with a '.pdf' extension."
        )

    if pdf_path.stat().st_size == 0:
        raise ValueError(f"PDF file is empty (0 bytes): '{pdf_path.name}'")

    if dpi <= 0:
        raise ValueError(f"Rendering DPI must be positive, got {dpi}")

    image_format = image_format.lower()
    if image_format not in ("png", "jpg", "jpeg", "webp"):
        raise ValueError(f"Unsupported image format '{image_format}'. Use 'png', 'jpg', or 'webp'.")

    pdf_stem = pdf_path.stem

    # Default output dir: data/page_images/<pdf_stem>
    target_dir = output_dir or (Path("data/page_images") / pdf_stem)
    target_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = target_dir / f"{pdf_stem}_manifest.json"
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(
            f"Render manifest already exists at '{manifest_path.resolve()}'. "
            "Pass '--overwrite' to allow replacing existing images."
        )

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise ValueError(
            f"Cannot open '{pdf_path.name}'. The file may be corrupted or not a valid PDF: {exc}"
        ) from exc

    try:
        if doc.is_encrypted:
            raise ValueError(
                f"PDF '{pdf_path.name}' is password-protected or encrypted. Please decrypt it first."
            )

        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError(f"PDF '{pdf_path.name}' contains 0 pages.")

        page_records: List[Dict[str, Any]] = []

        # Iterate page by page; stream to disk to keep memory O(1)
        for page_index in range(total_pages):
            page_number = page_index + 1
            page = doc[page_index]

            filename = get_image_filename(pdf_stem, page_number, image_format)
            image_dest = target_dir / filename

            if image_dest.exists() and not overwrite:
                raise FileExistsError(
                    f"Image file '{image_dest.resolve()}' already exists. "
                    "Pass '--overwrite' to allow replacing."
                )

            # Rasterize page at configured DPI
            pix = page.get_pixmap(dpi=dpi)
            pix.save(str(image_dest))

            width = pix.width
            height = pix.height

            # Release pixmap memory immediately
            del pix

            page_records.append(
                {
                    "page_number": page_number,
                    "image_filename": filename,
                    "image_path": str(image_dest.resolve()),
                    "width": width,
                    "height": height,
                    "dpi": dpi,
                }
            )

        manifest: Dict[str, Any] = {
            "source_file": pdf_path.name,
            "total_pages": total_pages,
            "render_settings": {
                "dpi": dpi,
                "image_format": image_format,
            },
            "output_directory": str(target_dir.resolve()),
            "total_rendered_images": len(page_records),
            "pages": page_records,
        }

        # Save manifest JSON to destination directory
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        manifest["manifest_path"] = str(manifest_path.resolve())
        return manifest

    finally:
        doc.close()


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for page rendering CLI."""
    parser = argparse.ArgumentParser(
        description="Render PDF pages into high-resolution images for AMCRAG visual retrieval (Milestone 4)."
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to the PDF file to render (e.g. data/sample.pdf)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help="Target directory for rendered images (default: data/page_images/<pdf_stem>)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Rendering resolution DPI (default: 150)",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="png",
        choices=["png", "jpg", "jpeg", "webp"],
        help="Image format (default: png)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing rendered images and manifest",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint for page rendering."""
    args = parse_arguments()
    input_pdf: Path = args.pdf_path

    print(f"\n[AMCRAG Milestone 4] Rendering pages for: '{input_pdf}'...")
    print(f" Settings: DPI={args.dpi}, Format={args.format.upper()}")

    try:
        manifest = render_pdf_pages(
            pdf_path=input_pdf,
            output_dir=args.output_dir,
            dpi=args.dpi,
            image_format=args.format,
            overwrite=args.overwrite,
        )

        total_rendered = manifest["total_rendered_images"]
        print("\n" + "=" * 60)
        print(" PAGE RENDERING SUCCESSFUL")
        print("=" * 60)
        print(f" Source File     : {manifest['source_file']}")
        print(f" Total Pages     : {manifest['total_pages']}")
        print(f" Rendered Images : {total_rendered} images ({manifest['render_settings']['dpi']} DPI)")
        print(f" Output Folder   : {manifest['output_directory']}")
        print(f" Manifest JSON   : {manifest.get('manifest_path', '')}")
        print("-" * 60)

        for p in manifest["pages"]:
            print(f" - Page {p['page_number']:>2}: {p['image_filename']} ({p['width']}x{p['height']} px)")

        print("=" * 60 + "\n")

    except FileExistsError as err:
        print(f"\n[Error] {err}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as err:
        print(f"\n[Error] {err}", file=sys.stderr)
        sys.exit(1)
    except ValueError as err:
        print(f"\n[Error] {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"\n[Unexpected Error] An unexpected error occurred: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
