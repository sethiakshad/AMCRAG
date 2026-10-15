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


def test_document_chunk_contract():
    """Verify Person 2 input contract strictly conforms to Section 5 of Person 2 report."""
    from schemas import DocumentChunk

    chunk = DocumentChunk(
        chunk_id="doc1_chunk_004",
        document_id="annual_financial_report_2025.pdf",
        page_number=12,
        text="Net profit increased by 14.2% year-over-year...",
        source_filename="annual_financial_report_2025.pdf",
        page_start=12,
        page_end=12,
        metadata={
            "section": "Financial Results",
            "headings": ["Executive Summary", "Financial Highlights"],
            "table": False,
            "bbox": [54.0, 120.5, 480.0, 310.2],
        },
    )

    assert chunk.chunk_id == "doc1_chunk_004"
    assert chunk.document_id == "annual_financial_report_2025.pdf"
    assert chunk.page_number == 12
    assert "Net profit increased" in chunk.text
    assert chunk.source_filename == "annual_financial_report_2025.pdf"
    assert chunk.page_start == 12
    assert chunk.page_end == 12
    assert chunk.metadata["section"] == "Financial Results"
    assert chunk.metadata["headings"] == ["Executive Summary", "Financial Highlights"]
    assert chunk.metadata["table"] is False
    assert chunk.metadata["bbox"] == [54.0, 120.5, 480.0, 310.2]
    # Check backward compatibility aliases
    assert chunk.chunk_text == chunk.text
    assert chunk.document_name == chunk.source_filename
    assert chunk.start_page == 12
    assert chunk.end_page == 12


def test_scored_candidate_contract():
    """Verify Person 2 ScoredCandidate data contract."""
    from schemas import ScoredCandidate

    candidate = ScoredCandidate(
        chunk_id="doc1_chunk_004",
        score=0.92,
        rank=1,
        modality="text",
        document_id="annual_financial_report_2025.pdf",
        page_number=12,
        text="Net profit increased...",
        source_filename="annual_financial_report_2025.pdf",
        page_start=12,
        page_end=12,
    )
    assert candidate.chunk_id == "doc1_chunk_004"
    assert candidate.score == 0.92
    assert candidate.rank == 1
    assert candidate.modality == "text"


def test_retrieval_candidate_aliases():
    """Verify RetrievalResult and RetrievalCandidate property aliases conform to Section 10.1 & Person 4."""
    from schemas import RetrievalCandidate, RetrievalResult

    result = RetrievalResult(
        chunk_id="doc1_chunk_004",
        document_id="annual_financial_report_2025.pdf",
        page_number=12,
        text="Net profit increased by 14.2% year-over-year...",
        modality="text",
        source_filename="annual_financial_report_2025.pdf",
        page_start=12,
        page_end=12,
        dense_score=0.884,
        sparse_score=11.45,
        dense_rank=1,
        sparse_rank=2,
        fused_score=0.0325,
        metadata={"section": "Financial Results"},
    )

    # Person 4 and Person 3 property compatibility aliases
    assert result.candidate_id == "doc1_chunk_004"
    assert result.candidate_type == "text_chunk"
    assert result.retrieval_score == 0.0325
    assert result.get_evaluable_content().startswith("Net profit")

    # Visual candidate evaluation fallback
    visual_result = RetrievalCandidate(
        chunk_id="page_img_001",
        document_id="annual_financial_report_2025.pdf",
        page_number=1,
        text="",
        modality="visual_page",
        source_filename="annual_financial_report_2025.pdf",
        page_start=1,
        page_end=1,
        fused_score=0.041,
        metadata={"caption": "Chart showing annual revenue breakdown"},
    )
    assert visual_result.candidate_type == "visual_page"
    assert visual_result.get_evaluable_content() == "Chart showing annual revenue breakdown"

