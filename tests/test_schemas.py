"""Unit tests for schema contracts and Pydantic serialization."""

import json
from app.schemas.chunk import ChunkMetadata, DocumentChunk, ProcessedDocumentOutput
from app.schemas.document import DocumentMetadata, PageRenderInfo


def test_chunk_metadata_schema():
    """Verify that ChunkMetadata contains all required metadata fields."""
    meta = ChunkMetadata(
        document_id="doc_abc123",
        document_name="test_doc.pdf",
        page_numbers=[1, 2],
        chunk_id="doc_abc123_c0001",
        chunk_index=0,
        section_heading="Introduction",
        extraction_method="pymupdf",
        source_citation="test_doc.pdf, Pages 1-2",
        char_count=120,
        token_estimate=30,
    )
    assert meta.document_id == "doc_abc123"
    assert meta.page_numbers == [1, 2]
    assert meta.source_citation == "test_doc.pdf, Pages 1-2"
    assert meta.extraction_method == "pymupdf"


def test_document_chunk_json_serialization():
    """Verify DocumentChunk serializes to JSON with all metadata preserved."""
    meta = ChunkMetadata(
        document_id="doc_xyz987",
        document_name="paper.pdf",
        page_numbers=[3],
        chunk_id="doc_xyz987_c0005",
        chunk_index=5,
        section_heading="Methods",
        extraction_method="docling",
        source_citation="paper.pdf, Page 3",
        char_count=80,
        token_estimate=20,
    )
    chunk = DocumentChunk(
        chunk_id="doc_xyz987_c0005",
        chunk_text="This is an experimental procedure description.",
        metadata=meta,
    )

    json_str = chunk.model_dump_json()
    data = json.loads(json_str)

    assert data["chunk_id"] == "doc_xyz987_c0005"
    assert data["chunk_text"] == "This is an experimental procedure description."
    assert data["metadata"]["section_heading"] == "Methods"
    assert data["metadata"]["page_numbers"] == [3]


def test_processed_document_output_contract():
    """Verify ProcessedDocumentOutput contract matches team requirements."""
    doc_meta = DocumentMetadata(
        document_id="doc_test123",
        document_name="contract.pdf",
        file_path="/data/uploads/contract.pdf",
        file_size_bytes=1024,
        page_count=2,
        upload_timestamp="2026-10-12T00:00:00Z",
        content_hash="hash123",
    )
    render_info = [
        PageRenderInfo(
            page_number=1,
            image_path="/data/page_images/doc_test123/page_001.png",
            width=800,
            height=1000,
            dpi=150,
        )
    ]
    output = ProcessedDocumentOutput(
        document_id="doc_test123",
        document_name="contract.pdf",
        metadata=doc_meta,
        status="success",
        is_scanned=False,
        ocr_needed=False,
        extraction_method="pymupdf",
        rendered_pages=render_info,
        chunks=[],
        total_chunks=0,
        tables=[],
    )

    dumped = json.loads(output.model_dump_json())
    assert dumped["document_id"] == "doc_test123"
    assert dumped["status"] == "success"
    assert len(dumped["rendered_pages"]) == 1
    assert dumped["rendered_pages"][0]["dpi"] == 150
