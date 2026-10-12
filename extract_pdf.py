"""extract_pdf.py - Milestone 1: PDF to Page-wise Text Extraction and JSON Output.

Module: Person 1 (Document Processing & Knowledge Base Preparation)
Project: AMCRAG (Adaptive Multimodal Corrective RAG)

Usage:
    python extract_pdf.py data/sample.pdf
    python extract_pdf.py path/to/document.pdf --output-dir data/processed
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf as fitz


def extract_page_text(pdf_path: Path) -> Dict[str, Any]:
    """Extract text page-by-page from a PDF document using PyMuPDF.

    Args:
        pdf_path: Filesystem path to the input PDF file.

    Returns:
        A dictionary containing document metadata, total page count,
        a list of empty page indices, and page-wise text records.

    Raises:
        FileNotFoundError: If the specified PDF file does not exist.
        ValueError: If the file is not a valid or readable PDF.
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

        pages_data: List[Dict[str, Any]] = []
        empty_pages: List[int] = []

        # Iterate through all pages in original order (0-indexed internally, 1-indexed for humans)
        for page_index in range(total_pages):
            page_number = page_index + 1
            page = doc[page_index]

            # Extract raw text from the page
            raw_text = page.get_text("text")
            cleaned_text = raw_text.strip()

            # Check if text is empty or contains only whitespace / zero-width spaces
            is_empty = len(cleaned_text) == 0 or len(cleaned_text.replace("\u200b", "").strip()) == 0

            if is_empty:
                empty_pages.append(page_number)

            pages_data.append(
                {
                    "page_number": page_number,
                    "text": cleaned_text,
                    "char_count": len(cleaned_text),
                    "is_empty": is_empty,
                    "headings": [],
                    "paragraphs": [cleaned_text] if cleaned_text else [],
                    "tables": [],
                }
            )

        result: Dict[str, Any] = {
            "source_file": pdf_path.name,
            "total_pages": total_pages,
            "empty_pages": empty_pages,
            "has_empty_pages": len(empty_pages) > 0,
            "backend_used": "pymupdf",
            "fallback_occurred": False,
            "fallback_reason": None,
            "tables": [],
            "pages": pages_data,
        }

        return result

    finally:
        doc.close()


def save_json_output(
    data: Dict[str, Any],
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """Save extracted document data to a UTF-8 JSON file.

    Creates the parent directory if it does not exist.

    Args:
        data: The dictionary of extracted pages and metadata.
        output_path: Destination path for the JSON file.
        overwrite: Whether to overwrite an existing destination file. Defaults to False.

    Returns:
        The resolved Path of the saved file.

    Raises:
        FileExistsError: If output_path already exists and overwrite is False.
    """
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: '{output_path.resolve()}'. "
            "Pass '--overwrite' to allow replacing existing files."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2, ensure_ascii=False)
    return output_path


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract text page-by-page from PDF files for AMCRAG (Milestone 1 & 3)."
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to the PDF file to extract (e.g., data/sample.pdf)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("data/processed"),
        help="Directory where JSON output will be saved (default: data/processed)",
    )
    parser.add_argument(
        "--backend",
        "-b",
        choices=["pymupdf", "docling", "auto"],
        default="pymupdf",
        help="Extraction backend: 'pymupdf' (default), 'docling' (structured), or 'auto' (tries Docling, falls back to PyMuPDF)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination JSON file if it already exists",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint."""
    args = parse_arguments()
    input_pdf: Path = args.pdf_path
    output_directory: Path = args.output_dir

    print(f"\n[AMCRAG Extraction] Processing: '{input_pdf}' (Backend: {args.backend})...")

    try:
        # Step 1: Extract based on selected backend
        if args.backend == "docling":
            from docling_extractor import extract_docling_structured
            extraction_result = extract_docling_structured(input_pdf)
        elif args.backend == "auto":
            from docling_extractor import extract_with_fallback
            extraction_result = extract_with_fallback(input_pdf, prefer_docling=True)
        else:
            extraction_result = extract_page_text(input_pdf)

        # Step 2: Determine output JSON filename (<pdf_stem>_extracted.json)
        output_filename = f"{input_pdf.stem}_extracted.json"
        destination_file = output_directory / output_filename
        was_overwritten = destination_file.exists()

        # Step 3: Save UTF-8 JSON file
        saved_path = save_json_output(
            extraction_result,
            destination_file,
            overwrite=args.overwrite,
        )

        # Step 4: Display clear summary report
        total_pages = extraction_result["total_pages"]
        empty_pages = extraction_result["empty_pages"]
        backend_used = extraction_result.get("backend_used", args.backend)
        fallback_occurred = extraction_result.get("fallback_occurred", False)
        fallback_reason = extraction_result.get("fallback_reason")

        print("\n" + "=" * 55)
        print(" EXTRACTION SUCCESSFUL")
        print("=" * 55)
        print(f" Source File  : {extraction_result['source_file']}")
        print(f" Total Pages  : {total_pages}")
        print(f" Backend Used : {backend_used}")
        if fallback_occurred:
            print(f" [!] Fallback : Primary Docling failed ({fallback_reason}).")
            print("                Recovered gracefully using PyMuPDF fallback.")
        if extraction_result.get("tables"):
            print(f" Tables Found : {len(extraction_result['tables'])}")
        overwrite_note = " (Overwrote existing file)" if was_overwritten else ""
        print(f" Output JSON  : {saved_path.resolve()}{overwrite_note}")
        print("-" * 55)

        for page in extraction_result["pages"]:
            status_tag = "[EMPTY / NO TEXT]" if page["is_empty"] else f"[{page['char_count']} chars]"
            headings_tag = f" ({len(page.get('headings', []))} heading(s))" if page.get("headings") else ""
            print(f" - Page {page['page_number']:>2}: {status_tag}{headings_tag}")

        if empty_pages:
            print("-" * 55)
            print(f" [!] Notice: Page(s) {empty_pages} have no text or only whitespace.")
            print("     If these are scanned document pages, note that OCR was not performed.")
            print("     (Scanned PDF OCR is handled in a separate upcoming module).")
        print("=" * 55 + "\n")

    except FileExistsError as err:
        print(f"\n[Error] {err}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as err:
        print(f"\n[Error] {err}", file=sys.stderr)
        sys.exit(1)
    except ImportError as err:
        print(f"\n[Dependency Notice] {err}", file=sys.stderr)
        sys.exit(1)
    except ValueError as err:
        print(f"\n[Error] {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"\n[Unexpected Error] An unexpected error occurred: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
