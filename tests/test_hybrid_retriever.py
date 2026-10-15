"""
Unit and Integration tests for Unified HybridTextRetriever.
Owner: Om Khapekar (Person 2)
"""
import pytest
from schemas import DocumentChunk
from hybrid_retriever import HybridTextRetriever


@pytest.fixture(scope="module")
def hybrid_retriever():
    return HybridTextRetriever(
        dense_model_name="BAAI/bge-base-en-v1.5",
        qdrant_path=None,  # In-memory Qdrant
        bm25_index_path=None,  # In-memory BM25
        device="cpu"
    )


def test_end_to_end_ingestion_and_retrieval(hybrid_retriever):
    chunks = [
        DocumentChunk(
            chunk_id="chunk_docling",
            document_id="docling.pdf",
            page_number=2,
            text="Docling parses complicated tables, reading order, and layout structures.",
            source_filename="docling.pdf",
            page_start=2,
            page_end=2,
            metadata={"tool": "Docling"}
        ),
        DocumentChunk(
            chunk_id="chunk_crag",
            document_id="crag.pdf",
            page_number=4,
            text="Corrective RAG applies a fine-tuned evaluator for retrieval quality decisions.",
            source_filename="crag.pdf",
            page_start=4,
            page_end=4,
            metadata={"tool": "CRAG"}
        )
    ]

    # Ingestion Hook
    hybrid_retriever.index_knowledge_base(chunks)

    # Retrieval Hook conforming to Section 10.2
    results = hybrid_retriever.retrieve(
        query="table layout extraction parser",
        top_k=2
    )

    assert len(results) > 0
    assert results[0].chunk_id == "chunk_docling"
    assert results[0].fused_score > 0.0
    assert results[0].source_filename == "docling.pdf"


def test_hybrid_filtered_retrieval(hybrid_retriever):
    results = hybrid_retriever.retrieve(
        query="retrieval evaluation",
        top_k=5,
        filters={"document_id": "crag.pdf"}
    )
    assert len(results) > 0
    assert all(r.document_id == "crag.pdf" for r in results)
