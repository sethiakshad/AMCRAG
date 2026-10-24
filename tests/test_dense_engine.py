"""
Unit tests for Dense Vector Retrieval Engine (BGE + Qdrant).
Owner: Om Khapekar (Person 2)
"""
import pytest

pytest.importorskip("sentence_transformers")
pytest.importorskip("qdrant_client")

from schemas import DocumentChunk
from dense_engine import BGEDenseEngine


@pytest.fixture(scope="module")
def dense_engine():
    # Use in-memory Qdrant instance for fast, isolated test execution
    return BGEDenseEngine(
        model_name="BAAI/bge-base-en-v1.5",
        collection_name="test_dense_collection",
        qdrant_path=None,
        device="cpu"
    )


def test_dense_indexing_and_search(dense_engine):
    chunks = [
        DocumentChunk(
            chunk_id="dense_1",
            document_id="doc1.pdf",
            page_number=1,
            text="Reciprocal Rank Fusion merges ranked lists across multiple retrieval models.",
            metadata={"topic": "information_retrieval"}
        ),
        DocumentChunk(
            chunk_id="dense_2",
            document_id="doc2.pdf",
            page_number=5,
            text="Convolutional neural networks extract visual features from high resolution images.",
            metadata={"topic": "computer_vision"}
        )
    ]
    dense_engine.index_chunks(chunks)

    results = dense_engine.search(query="How does RRF combine different retrieval rankings?", top_k=2)
    assert len(results) > 0
    assert results[0].chunk_id == "dense_1"
    assert results[0].rank == 1


def test_dense_filtering(dense_engine):
    # Filter by document_id
    results = dense_engine.search(
        query="neural network features",
        top_k=5,
        filters={"document_id": "doc2.pdf"}
    )
    assert len(results) > 0
    assert all(c.document_id == "doc2.pdf" for c in results)


def test_dense_empty_query(dense_engine):
    assert dense_engine.search(query="", top_k=5) == []
    assert dense_engine.search(query="   ", top_k=5) == []
