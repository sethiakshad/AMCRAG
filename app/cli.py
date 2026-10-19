"""Command line interface for Document Processing and Knowledge Base preparation."""

import argparse
import logging
import sys
from pathlib import Path

# Enable direct script execution (e.g., `python app/cli.py`)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.config import Settings
from app.services.pipeline import DocumentProcessingPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("AMCRAG-CLI")


def main():
    parser = argparse.ArgumentParser(
        description="AMCRAG Document Processing & Knowledge Base Preparation (Person 1)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--file", "-f", type=Path, help="Process a single PDF file")
    group.add_argument(
        "--dir",
        "-d",
        type=Path,
        help="Process all PDF files in a directory (default: data/uploads)",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Maximum characters per chunk (default: 800)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=150,
        help="Overlap characters between chunks (default: 150)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Rendering resolution DPI for ColPali page images (default: 150)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing even if document is already indexed",
    )

    args = parser.parse_args()

    settings = Settings(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        render_dpi=args.dpi,
    )
    pipeline = DocumentProcessingPipeline(settings=settings)

    if args.file:
        target_file = args.file
        if not target_file.exists():
            logger.error("File not found: %s", target_file)
            sys.exit(1)

        logger.info("Processing single file: %s", target_file)
        result = pipeline.process_file(target_file, force_reprocess=args.force)

        print("\n" + "=" * 60)
        print(f"DOCUMENT ID       : {result.document_id}")
        print(f"STATUS            : {result.status}")
        print(f"EXTRACTION METHOD : {result.extraction_method}")
        print(f"PAGES             : {result.metadata.page_count}")
        print(f"CHUNKS GENERATED  : {result.total_chunks}")
        print(f"TABLES EXTRACTED  : {len(result.tables)}")
        print(f"RENDERED IMAGES   : {len(result.rendered_pages)}")
        print(f"SCANNED / OCR REQ : {result.is_scanned} / {result.ocr_needed}")
        if result.warnings:
            print("WARNINGS          :")
            for w in result.warnings:
                print(f"  - {w}")
        print(f"OUTPUT SAVED TO   : data/processed/{result.document_id}.json")
        print("=" * 60 + "\n")

    else:
        target_dir = args.dir or settings.get_uploads_path()
        logger.info("Processing directory: %s", target_dir)
        results = pipeline.process_directory(target_dir, force_reprocess=args.force)

        print("\n" + "=" * 60)
        print(f"BATCH PROCESSING SUMMARY ({len(results)} file(s))")
        print("=" * 60)
        for r in results:
            print(
                f"- {r.document_name} | ID: {r.document_id} | Status: {r.status} "
                f"| Chunks: {r.total_chunks} | Pages: {r.metadata.page_count}"
            )
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
