"""Unit tests for AMC-RAG Data Contracts & Schemas.

Organized clearly by subsystem responsibility:
- PERSON 1: Document Processing, Extraction & Knowledge Base Schemas Tests
- PERSON 2: Dense & Sparse Text Retrieval, RRF Fusion & Candidate Schemas Tests (Om Khapekar)
"""

import json
from schemas import (
    ChunkMetadata,
    DocumentChunk,
    DocumentMetadata,
    PageRenderInfo,
    ProcessedDocumentOutput,
    RetrievalCandidate,
    RetrievalResult,
    ScoredCandidate,
)


# =============================================================================
# PERSON 1: Document Ingestion, PDF Processing & Chunking Schemas Tests
# Teammate: Person 1 (Document Processing & Knowledge Base)
# =============================================================================

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


# =============================================================================
# PERSON 2: Dense & Sparse Text Retrieval, RRF Fusion & Candidates Tests
# Teammate: Person 2 / Om Khapekar (Dense/Sparse Text Retrieval & Hybrid Fusion)
# =============================================================================

def test_document_chunk_contract():
    """Verify Person 2 input contract strictly conforms to Section 5 of Person 2 report."""
    # 1. Full layout metadata contract
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

    # 2. Minimal constructor contract from Om's initial test suite
    om_chunk = DocumentChunk(
        chunk_id="c_001",
        document_id="doc_test.pdf",
        page_number=1,
        text="Sample test content from Docling",
        source_filename="doc_test.pdf",
        page_start=1,
        page_end=1,
        metadata={"section": "abstract"},
    )
    assert om_chunk.chunk_id == "c_001"
    assert om_chunk.page_start == 1
    assert om_chunk.source_filename == "doc_test.pdf"


def test_scored_candidate_contract():
    """Verify Person 2 ScoredCandidate data contract with modality and candidate_type."""
    # Person 1 & unified format (modality='text')
    candidate1 = ScoredCandidate(
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
    assert candidate1.chunk_id == "doc1_chunk_004"
    assert candidate1.score == 0.92
    assert candidate1.rank == 1
    assert candidate1.modality == "text"
    assert candidate1.candidate_type == "text_chunk"

    # Om's test suite format (candidate_type='text_chunk')
    candidate2 = ScoredCandidate(
        chunk_id="c_001",
        document_id="doc_test.pdf",
        page_number=1,
        text="Sample test content",
        score=0.92,
        rank=1,
        candidate_type="text_chunk",
    )
    assert candidate2.score == 0.92
    assert candidate2.rank == 1
    assert candidate2.candidate_type == "text_chunk"
    assert candidate2.modality == "text"


def test_retrieval_candidate_aliases():
    """Verify RetrievalResult and RetrievalCandidate property aliases conform to Section 10.1 & Person 4."""
    # 1. Full fused hybrid result
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

    # 2. Visual candidate evaluation fallback
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

    # 3. Om's minimal constructor & type alias identity
    om_res = RetrievalResult(
        chunk_id="c_001",
        document_id="doc_test.pdf",
        page_number=1,
        text="Sample test content",
        modality="text",
        fused_score=0.032,
        dense_rank=1,
        sparse_rank=2,
    )
    assert om_res.candidate_id == "c_001"
    assert om_res.candidate_type == "text_chunk"
    assert om_res.retrieval_score == 0.032
    assert RetrievalCandidate is RetrievalResult
