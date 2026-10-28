"""End-to-end Document Processing and Knowledge Base pipeline orchestrator."""

import json
import logging
from pathlib import Path
from typing import List, Optional

from app.chunking.text_chunker import TextChunker
from app.config import Settings, default_settings
from app.extractors.base import BaseExtractor
from app.extractors.fallback_extractor import FallbackExtractor
from app.schemas.chunk import ProcessedDocumentOutput
from app.schemas.document import DocumentMetadata
from app.services.duplicate_detector import DuplicateDetector
from app.services.page_renderer import PageRenderer

logger = logging.getLogger(__name__)


class DocumentProcessingPipeline:
    """End-to-end pipeline for PDF ingestion, extraction, chunking, and ColPali rendering."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        extractor: Optional[BaseExtractor] = None,
        chunker: Optional[TextChunker] = None,
        renderer: Optional[PageRenderer] = None,
        duplicate_detector: Optional[DuplicateDetector] = None,
    ):
        self.settings = settings or default_settings
        self.extractor = extractor or FallbackExtractor(self.settings)
        self.chunker = chunker or TextChunker(settings=self.settings)
        self.renderer = renderer or PageRenderer(settings=self.settings)
        self.duplicate_detector = duplicate_detector or DuplicateDetector(self.settings)

    def process_file(
        self,
        pdf_path: Path,
        force_reprocess: bool = False,
    ) -> ProcessedDocumentOutput:
        """Process a single PDF through extraction, chunking, and rendering."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Input file not found: {pdf_path}")

        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file must be a PDF, got: {pdf_path.name}")

        # 1. Duplicate check
        is_dup, doc_id, existing_path = self.duplicate_detector.check_duplicate(pdf_path)
        if is_dup and not force_reprocess and existing_path and existing_path.exists():
            logger.info("Skipping re-processing for duplicate document: %s (ID: %s)", pdf_path.name, doc_id)
            try:
                with existing_path.open("r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    output = ProcessedDocumentOutput.model_validate(cached_data)
                    output.status = "duplicate_skipped"
                    return output
            except Exception as e:
                logger.warning("Could not read cached output %s: %s. Reprocessing.", existing_path, e)

        # 2. Extract structured content
        try:
            extraction_result = self.extractor.extract(pdf_path)
        except Exception as e:
            logger.error("Extraction error processing %s: %s", pdf_path.name, e)
            failed_output = ProcessedDocumentOutput(
                document_id=doc_id,
                document_name=pdf_path.name,
                metadata=DocumentMetadata(
                    document_id=doc_id,
                    document_name=pdf_path.name,
                    file_path=str(pdf_path.resolve()),
                    file_size_bytes=pdf_path.stat().st_size if pdf_path.exists() else 0,
                    page_count=0,
                    upload_timestamp="",
                    content_hash=doc_id.replace("doc_", ""),
                ),
                status="failed",
                is_scanned=False,
                ocr_needed=False,
                extraction_method="failed",
                error_message=str(e),
                warnings=[f"Failed extraction: {e}"],
            )
            return failed_output

        # 3. Render pages as images for ColPali
        try:
            rendered_pages = self.renderer.render_document(
                pdf_path=pdf_path,
                document_id=extraction_result.metadata.document_id,
            )
        except Exception as e:
            logger.warning("Page rendering failed for %s: %s", pdf_path.name, e)
            rendered_pages = []
            extraction_result.warnings.append(f"Page rendering warning: {e}")

        # 4. Chunk document text preserving section heading and page metadata
        chunks = self.chunker.chunk_document(extraction_result)

        # 5. Determine overall processing status
        status = "success"
        if len(chunks) == 0:
            extraction_result.is_scanned = True
            extraction_result.ocr_needed = True
            status = "visual_only"
            extraction_result.warnings.append("0 text chunks extracted. Routed to visual_orchestrator module.")
        elif extraction_result.is_scanned or extraction_result.ocr_needed:
            status = "warning_ocr_needed"

        output = ProcessedDocumentOutput(
            document_id=extraction_result.metadata.document_id,
            document_name=extraction_result.metadata.document_name,
            metadata=extraction_result.metadata,
            status=status,
            is_scanned=extraction_result.is_scanned,
            ocr_needed=extraction_result.ocr_needed,
            extraction_method=extraction_result.extraction_method.value,
            rendered_pages=rendered_pages,
            chunks=chunks,
            total_chunks=len(chunks),
            tables=extraction_result.tables,
            warnings=extraction_result.warnings,
            error_message=extraction_result.error_message,
        )

        # 6. Save structured output JSON
        self._save_output(output)

        # 7. Register in duplicate detector ledger
        self.duplicate_detector.register_processed(
            document_id=output.document_id,
            document_name=output.document_name,
            total_chunks=output.total_chunks,
            status=output.status,
        )

        return output

    def _save_output(self, output: ProcessedDocumentOutput) -> Path:
        """Write processed output contract to data/processed/{doc_id}.json."""
        out_file = self.settings.get_processed_path() / f"{output.document_id}.json"
        with out_file.open("w", encoding="utf-8") as f:
            f.write(output.model_dump_json(indent=2))
        logger.info("Saved processed document JSON to %s", out_file)
        return out_file

    def process_directory(
        self,
        directory_path: Path,
        force_reprocess: bool = False,
    ) -> List[ProcessedDocumentOutput]:
        """Batch process all PDF files found in target directory."""
        dir_p = Path(directory_path)
        if not dir_p.exists() or not dir_p.is_dir():
            raise NotADirectoryError(f"Directory not found: {directory_path}")

        pdf_files = sorted(dir_p.glob("*.pdf"))
        logger.info("Found %d PDF file(s) in %s", len(pdf_files), dir_p)

        results: List[ProcessedDocumentOutput] = []
        for pdf_path in pdf_files:
            res = self.process_file(pdf_path, force_reprocess=force_reprocess)
            results.append(res)
        return results
