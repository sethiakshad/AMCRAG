"""
Unit tests for BM25 Lexical Retrieval Engine.
Owner: Om Khapekar (Person 2)
"""
import os
import tempfile
import pytest

pytest.importorskip("rank_bm25")

from schemas import DocumentChunk
try:
    from app.retrieval.sparse_engine import BM25SparseEngine
except ImportError:
    from sparse_engine import BM25SparseEngine


@pytest.fixture
def sample_chunks():
    return [
        DocumentChunk(
            chunk_id="chunk_1",
            document_id="paper_a.pdf",
            page_number=1,
            text="ColPali utilizes Vision-Language Models to index multi-vector PDF pages directly.",
            metadata={"domain": "vision"}
        ),
        DocumentChunk(
            chunk_id="chunk_2",
            document_id="paper_b.pdf",
            page_number=3,
            text="Corrective RAG (CRAG) evaluates evidence quality with a T5-large discriminator.",
            metadata={"domain": "eval"}
        ),
        DocumentChunk(
            chunk_id="chunk_3",
            document_id="paper_a.pdf",
            page_number=2,
            text="Error code E-502 denotes network timeout during ColPali image transfer.",
            metadata={"domain": "troubleshooting"}
        )
    ]


def test_bm25_tokenize():
    tokens = BM25SparseEngine.tokenize("ColPali v1.2-beta & Error-Code E_502!")
    assert "colpali" in tokens
    assert "v1.2-beta" in tokens or "v1" in tokens
    assert "e_502" in tokens


def test_bm25_search_and_ranking(sample_chunks):
    engine = BM25SparseEngine(index_file_path=None)
    engine.index_chunks(sample_chunks, save_to_disk=False)

    results = engine.search(query="ColPali image transfer", top_k=2)
    assert len(results) > 0
    # chunk_3 has both 'colpali' and 'image' and 'transfer'
    assert results[0].chunk_id == "chunk_3"
    assert results[0].rank == 1


def test_bm25_filtering(sample_chunks):
    engine = BM25SparseEngine(index_file_path=None)
    engine.index_chunks(sample_chunks, save_to_disk=False)

    # Filter by document_id
    filtered = engine.search(
        query="ColPali",
        top_k=5,
        filters={"document_id": "paper_a.pdf"}
    )
    assert len(filtered) > 0
    assert all(c.document_id == "paper_a.pdf" for c in filtered)


def test_bm25_empty_query_handling(sample_chunks):
    engine = BM25SparseEngine(index_file_path=None)
    engine.index_chunks(sample_chunks, save_to_disk=False)

    assert engine.search(query="", top_k=5) == []
    assert engine.search(query="   ", top_k=5) == []
    assert engine.search(query="!@#$%^&*", top_k=5) == []


def test_bm25_disk_persistence(sample_chunks):
    with tempfile.TemporaryDirectory() as tmpdir:
        pkl_path = os.path.join(tmpdir, "test_bm25.pkl")
        engine = BM25SparseEngine(index_file_path=pkl_path)
        engine.index_chunks(sample_chunks, save_to_disk=True)

        assert os.path.exists(pkl_path)

        # Reload in a new instance
        reloaded = BM25SparseEngine(index_file_path=pkl_path)
        res = reloaded.search(query="CRAG T5-large", top_k=1)
        assert len(res) == 1
        assert res[0].chunk_id == "chunk_2"
