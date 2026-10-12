"""chunk_text.py - Milestone 2: Text Chunking with Source Metadata.

Module: Person 1 (Document Processing & Knowledge Base Preparation)
Project: AMCRAG (Adaptive Multimodal Corrective RAG)

Usage:
    python chunk_text.py data/sample.pdf
    python chunk_text.py data/sample.pdf --chunk-size 500 --chunk-overlap 100
    python chunk_text.py data/processed/sample_extracted.json --overwrite
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from extract_pdf import extract_page_text


def build_word_stream(pages: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    """Flatten non-empty pages into a stream of (word, page_number) tokens.

    Preserves exact page provenance for every word in document sequence.

    Args:
        pages: List of page dictionaries, each containing 'page_number' and 'text'.

    Returns:
        List of tuples: (word_string, 1_based_page_number).
    """
    token_stream: List[Tuple[str, int]] = []
    for page_record in pages:
        page_num = page_record.get("page_number", 1)
        text = page_record.get("text", "").strip()
        if not text:
            continue

        words = text.split()
        for w in words:
            token_stream.append((w, page_num))

    return token_stream


def chunk_extracted_document(
    extracted_data: Dict[str, Any],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> Dict[str, Any]:
    """Split extracted page text into overlapping chunks with source metadata.

    Args:
        extracted_data: Dictionary produced by extract_pdf (source_file, pages).
        chunk_size: Maximum character length per chunk (must be > 0).
        chunk_overlap: Character overlap between consecutive chunks (0 <= overlap < chunk_size).

    Returns:
        Dictionary containing document metadata, chunk parameters, total_chunks,
        and the list of chunk objects.

    Raises:
        ValueError: If chunk_size <= 0 or chunk_overlap >= chunk_size or chunk_overlap < 0.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")

    if chunk_overlap < 0:
        raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")

    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})"
        )

    source_file = extracted_data.get("source_file", "unknown.pdf")
    file_stem = Path(source_file).stem
    pages = extracted_data.get("pages", [])
    total_pages = extracted_data.get("total_pages", len(pages))
    page_to_heading = {
        p.get("page_number", 1): (p.get("headings", [None])[0] if p.get("headings") else None)
        for p in pages
    }

    # 1. Flatten into token stream with page tags
    token_stream = build_word_stream(pages)

    chunks: List[Dict[str, Any]] = []

    # Handle empty document gracefully
    if not token_stream:
        return {
            "source_file": source_file,
            "total_pages": total_pages,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "total_chunks": 0,
            "chunks": [],
        }

    # 2. Sliding window over token stream
    token_count = len(token_stream)
    start_idx = 0
    chunk_seq = 1

    while start_idx < token_count:
        current_words: List[str] = []
        current_pages: List[int] = []
        current_chars = 0
        end_idx = start_idx

        # Accumulate words until character limit is reached
        while end_idx < token_count:
            word, page_num = token_stream[end_idx]
            # Length if we add this word (including 1 space if not first word)
            added_len = len(word) if not current_words else len(word) + 1

            if current_chars + added_len > chunk_size and current_words:
                break

            current_words.append(word)
            current_pages.append(page_num)
            current_chars += added_len
            end_idx += 1

        # Compose chunk
        chunk_text = " ".join(current_words)
        unique_pages = sorted(list(set(current_pages)))
        start_page = unique_pages[0] if unique_pages else 1
        end_page = unique_pages[-1] if unique_pages else 1

        chunk_id = f"{file_stem}_chunk_{chunk_seq:04d}"
        citation = (
            f"{source_file}, Page {start_page}"
            if start_page == end_page
            else f"{source_file}, Pages {start_page}-{end_page}"
        )
        heading = page_to_heading.get(start_page)

        chunk_record: Dict[str, Any] = {
            "chunk_id": chunk_id,
            "chunk_index": chunk_seq - 1,
            "chunk_text": chunk_text,
            "source_file": source_file,
            "start_page": start_page,
            "end_page": end_page,
            "page_numbers": unique_pages,
            "source_citation": citation,
            "section_heading": heading,
            "char_count": len(chunk_text),
            "word_count": len(current_words),
        }
        chunks.append(chunk_record)
        chunk_seq += 1

        # If we reached the end of the document, we are done
        if end_idx >= token_count:
            break

        # Calculate overlap for next chunk start
        if chunk_overlap == 0:
            next_start = end_idx
        else:
            # Step backward from end_idx to gather overlap characters
            overlap_chars = 0
            back_idx = end_idx - 1
            while back_idx > start_idx and overlap_chars < chunk_overlap:
                w, _ = token_stream[back_idx]
                overlap_chars += len(w) + 1
                back_idx -= 1

            next_start = back_idx + 1

        # Guarantee progress: next chunk MUST advance past current start_idx
        if next_start <= start_idx:
            next_start = start_idx + 1

        start_idx = next_start

    return {
        "source_file": source_file,
        "total_pages": total_pages,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }


def chunk_pdf(
    pdf_path: Path,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> Dict[str, Any]:
    """Convenience function: extract PDF text and chunk in one call."""
    extracted = extract_page_text(pdf_path)
    return chunk_extracted_document(extracted, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def save_chunk_output(
    data: Dict[str, Any],
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """Save chunk output dictionary to a UTF-8 JSON file."""
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: '{output_path.resolve()}'. "
            "Pass '--overwrite' to allow replacing existing files."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return output_path


def parse_arguments() -> argparse.Namespace:
    """Parse and validate command line arguments for chunking CLI."""
    parser = argparse.ArgumentParser(
        description="Chunk extracted PDF text with page-level metadata for AMCRAG (Milestone 2)."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to input PDF file (e.g. data/sample.pdf) or pre-extracted JSON file",
    )
    parser.add_argument(
        "--chunk-size",
        "-s",
        type=int,
        default=500,
        help="Target maximum character length per chunk (default: 500)",
    )
    parser.add_argument(
        "--chunk-overlap",
        "-o",
        type=int,
        default=100,
        help="Character overlap between consecutive chunks (default: 100)",
    )
    parser.add_argument(
        "--output-dir",
        "-d",
        type=Path,
        default=Path("data/processed"),
        help="Directory to save output chunk JSON (default: data/processed)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination JSON file if it already exists",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entrypoint for text chunking."""
    args = parse_arguments()
    input_path: Path = args.input_path
    output_dir: Path = args.output_dir

    print(f"\n[AMCRAG Milestone 2] Chunking: '{input_path}'...")
    print(f" Parameters: chunk_size={args.chunk_size}, chunk_overlap={args.chunk_overlap}")

    try:
        # Determine whether input is PDF or pre-extracted JSON
        if not input_path.exists():
            raise FileNotFoundError(f"File not found: '{input_path.resolve()}'")

        if input_path.suffix.lower() == ".json":
            with input_path.open("r", encoding="utf-8") as f:
                extracted_data = json.load(f)
            stem = Path(extracted_data.get("source_file", input_path.stem)).stem
            chunk_result = chunk_extracted_document(
                extracted_data,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            )
        elif input_path.suffix.lower() == ".pdf":
            stem = input_path.stem
            chunk_result = chunk_pdf(
                input_path,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            )
        else:
            raise ValueError(
                f"Unsupported file type '{input_path.suffix}'. Please provide a .pdf or .json file."
            )

        output_filename = f"{stem}_chunks.json"
        destination_file = output_dir / output_filename
        was_overwritten = destination_file.exists()

        saved_path = save_chunk_output(
            chunk_result,
            destination_file,
            overwrite=args.overwrite,
        )

        total_chunks = chunk_result["total_chunks"]
        print("\n" + "=" * 60)
        print(" CHUNKING SUCCESSFUL")
        print("=" * 60)
        print(f" Source File  : {chunk_result['source_file']}")
        print(f" Total Pages  : {chunk_result['total_pages']}")
        print(f" Total Chunks : {total_chunks}")
        overwrite_note = " (Overwrote existing file)" if was_overwritten else ""
        print(f" Output JSON  : {saved_path.resolve()}{overwrite_note}")
        print("-" * 60)

        # Print preview of first chunks
        preview_count = min(3, total_chunks)
        for i in range(preview_count):
            c = chunk_result["chunks"][i]
            page_info = f"Page {c['start_page']}" if c["start_page"] == c["end_page"] else f"Pages {c['start_page']}-{c['end_page']}"
            snippet = c["chunk_text"][:65] + "..." if len(c["chunk_text"]) > 65 else c["chunk_text"]
            print(f" - [{c['chunk_id']}] ({page_info}, {c['char_count']} chars): \"{snippet}\"")

        if total_chunks > preview_count:
            print(f"   ... and {total_chunks - preview_count} more chunk(s).")
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
