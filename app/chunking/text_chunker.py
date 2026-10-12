"""Configurable text chunking preserving document structure, headings, and citations."""

import logging
import re
from typing import List, Optional

from app.config import Settings, default_settings
from app.schemas.chunk import ChunkMetadata, DocumentChunk
from app.schemas.document import DocumentExtractionResult, PageExtraction

logger = logging.getLogger(__name__)


def format_citation(document_name: str, pages: List[int]) -> str:
    """Format human-readable source citation string for RAG answers."""
    sorted_pages = sorted(list(set(pages)))
    if not sorted_pages:
        return document_name
    if len(sorted_pages) == 1:
        return f"{document_name}, Page {sorted_pages[0]}"
    # Check if continuous range
    if sorted_pages[-1] - sorted_pages[0] == len(sorted_pages) - 1:
        return f"{document_name}, Pages {sorted_pages[0]}-{sorted_pages[-1]}"
    return f"{document_name}, Pages {', '.join(str(p) for p in sorted_pages)}"


class TextChunker:
    """Splits extracted document pages into configurable overlapping chunks with metadata."""

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or default_settings
        self.chunk_size = chunk_size if chunk_size is not None else self.settings.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else self.settings.chunk_overlap

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be strictly less than chunk_size ({self.chunk_size})"
            )

    def chunk_document(self, extraction_result: DocumentExtractionResult) -> List[DocumentChunk]:
        """Split document pages into traceable chunks with full metadata and citation references."""
        chunks: List[DocumentChunk] = []
        doc_id = extraction_result.metadata.document_id
        doc_name = extraction_result.metadata.document_name
        method_str = extraction_result.extraction_method.value

        global_chunk_idx = 0
        current_heading: Optional[str] = None

        for page in extraction_result.pages:
            if page.headings:
                current_heading = page.headings[0]

            page_text = page.text.strip()
            if not page_text:
                continue

            page_chunks = self._chunk_page(
                page=page,
                doc_id=doc_id,
                doc_name=doc_name,
                method_str=method_str,
                heading=current_heading,
                start_index=global_chunk_idx,
            )

            chunks.extend(page_chunks)
            global_chunk_idx += len(page_chunks)

        logger.info(
            "Generated %d chunks from %d pages for document %s",
            len(chunks),
            len(extraction_result.pages),
            doc_name,
        )
        return chunks

    def _chunk_page(
        self,
        page: PageExtraction,
        doc_id: str,
        doc_name: str,
        method_str: str,
        heading: Optional[str],
        start_index: int,
    ) -> List[DocumentChunk]:
        """Produce overlapping text chunks from a single page using sentence-aware splitting."""
        text = page.text.strip()
        if len(text) <= self.chunk_size:
            # Single chunk for this page
            c_id = f"{doc_id}_c{start_index:04d}"
            meta = ChunkMetadata(
                document_id=doc_id,
                document_name=doc_name,
                page_numbers=[page.page_number],
                chunk_id=c_id,
                chunk_index=start_index,
                section_heading=heading,
                extraction_method=method_str,
                source_citation=format_citation(doc_name, [page.page_number]),
                char_count=len(text),
                token_estimate=max(1, len(text) // 4),
            )
            return [DocumentChunk(chunk_id=c_id, chunk_text=text, metadata=meta)]

        # Sliding window with sentence/paragraph awareness
        segments = self._split_into_units(text)
        chunks: List[DocumentChunk] = []
        chunk_idx = start_index

        current_slice: List[str] = []
        current_len = 0

        i = 0
        while i < len(segments):
            seg = segments[i]
            seg_len = len(seg)

            if current_len + seg_len > self.chunk_size and current_slice:
                chunk_text = " ".join(current_slice).strip()
                if chunk_text:
                    c_id = f"{doc_id}_c{chunk_idx:04d}"
                    meta = ChunkMetadata(
                        document_id=doc_id,
                        document_name=doc_name,
                        page_numbers=[page.page_number],
                        chunk_id=c_id,
                        chunk_index=chunk_idx,
                        section_heading=heading,
                        extraction_method=method_str,
                        source_citation=format_citation(doc_name, [page.page_number]),
                        char_count=len(chunk_text),
                        token_estimate=max(1, len(chunk_text) // 4),
                    )
                    chunks.append(DocumentChunk(chunk_id=c_id, chunk_text=chunk_text, metadata=meta))
                    chunk_idx += 1

                # Calculate overlap backward
                overlap_slice: List[str] = []
                overlap_len = 0
                for prev_seg in reversed(current_slice):
                    if overlap_len + len(prev_seg) > self.chunk_overlap:
                        break
                    overlap_slice.insert(0, prev_seg)
                    overlap_len += len(prev_seg)

                current_slice = overlap_slice
                current_len = overlap_len

            current_slice.append(seg)
            current_len += seg_len + 1
            i += 1

        # Tail chunk
        if current_slice:
            chunk_text = " ".join(current_slice).strip()
            if chunk_text:
                c_id = f"{doc_id}_c{chunk_idx:04d}"
                meta = ChunkMetadata(
                    document_id=doc_id,
                    document_name=doc_name,
                    page_numbers=[page.page_number],
                    chunk_id=c_id,
                    chunk_index=chunk_idx,
                    section_heading=heading,
                    extraction_method=method_str,
                    source_citation=format_citation(doc_name, [page.page_number]),
                    char_count=len(chunk_text),
                    token_estimate=max(1, len(chunk_text) // 4),
                )
                chunks.append(DocumentChunk(chunk_id=c_id, chunk_text=chunk_text, metadata=meta))

        return chunks

    def _split_into_units(self, text: str) -> List[str]:
        """Split text into sentences and natural clause boundaries."""
        # Split on sentence boundaries: period, exclamation, question mark, or newlines
        parts = re.split(r"(?<=[.!?])\s+|\n+", text)
        units: List[str] = []
        for p in parts:
            p_clean = p.strip()
            if not p_clean:
                continue
            # If an individual sentence is larger than chunk_size, split by words
            if len(p_clean) > self.chunk_size:
                words = p_clean.split()
                sub = []
                sub_len = 0
                for w in words:
                    if sub_len + len(w) > self.chunk_size and sub:
                        units.append(" ".join(sub))
                        sub = [w]
                        sub_len = len(w)
                    else:
                        sub.append(w)
                        sub_len += len(w) + 1
                if sub:
                    units.append(" ".join(sub))
            else:
                units.append(p_clean)
        return units
