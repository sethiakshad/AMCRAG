"""
Unit tests for AMC-RAG Data Contracts & Schemas.
Owner: Om Khapekar (Person 2)
"""
from schemas import DocumentChunk, ScoredCandidate, RetrievalResult, RetrievalCandidate


def test_document_chunk_contract():
    chunk = DocumentChunk(
        chunk_id="c_001",
        document_id="doc_test.pdf",
        page_number=1,
        text="Sample test content from Docling",
        source_filename="doc_test.pdf",
        page_start=1,
        page_end=1,
        metadata={"section": "abstract"}
    )
    assert chunk.chunk_id == "c_001"
    assert chunk.page_start == 1
    assert chunk.source_filename == "doc_test.pdf"


def test_scored_candidate_contract():
    cand = ScoredCandidate(
        chunk_id="c_001",
        document_id="doc_test.pdf",
        page_number=1,
        text="Sample test content",
        score=0.92,
        rank=1,
        candidate_type="text_chunk"
    )
    assert cand.score == 0.92
    assert cand.rank == 1
    assert cand.candidate_type == "text_chunk"


def test_retrieval_candidate_aliases():
    res = RetrievalResult(
        chunk_id="c_001",
        document_id="doc_test.pdf",
        page_number=1,
        text="Sample test content",
        modality="text",
        fused_score=0.032,
        dense_rank=1,
        sparse_rank=2
    )
    # Check Section 10.1 property aliases
    assert res.candidate_id == "c_001"
    assert res.candidate_type == "text_chunk"
    assert res.retrieval_score == 0.032

    # Check type alias identity
    assert RetrievalCandidate is RetrievalResult
