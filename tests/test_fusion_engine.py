"""
Unit tests for Reciprocal Rank Fusion Engine.
Owner: Om Khapekar (Person 2)
"""
from schemas import ScoredCandidate, RetrievalResult
try:
    from app.retrieval.fusion_engine import ReciprocalRankFusion
except ImportError:
    from fusion_engine import ReciprocalRankFusion


def test_rrf_scoring_math():
    k = 60
    fusion = ReciprocalRankFusion(k=k, weight_dense=1.0, weight_sparse=1.0)

    dense_cand = [
        ScoredCandidate(chunk_id="c1", document_id="doc.pdf", page_number=1, text="Text 1", score=0.9, rank=1),
        ScoredCandidate(chunk_id="c2", document_id="doc.pdf", page_number=2, text="Text 2", score=0.8, rank=2)
    ]
    sparse_cand = [
        ScoredCandidate(chunk_id="c2", document_id="doc.pdf", page_number=2, text="Text 2", score=5.0, rank=1),
        ScoredCandidate(chunk_id="c3", document_id="doc.pdf", page_number=3, text="Text 3", score=3.0, rank=2)
    ]

    results = fusion.fuse(dense_candidates=dense_cand, sparse_candidates=sparse_cand, top_k=3)

    # c2 appears in both:
    # dense_rank=2 -> 1 / (60 + 2) = 1/62
    # sparse_rank=1 -> 1 / (60 + 1) = 1/61
    expected_c2_score = (1.0 / 62.0) + (1.0 / 61.0)

    # c2 must be ranked first because it matched both dense & sparse
    assert results[0].chunk_id == "c2"
    assert abs(results[0].fused_score - expected_c2_score) < 1e-6
    assert results[0].dense_rank == 2
    assert results[0].sparse_rank == 1


def test_rrf_with_visual_candidates():
    """Verify Person 3's ColPali candidates can be fused directly."""
    fusion = ReciprocalRankFusion(k=60, weight_dense=1.0, weight_sparse=1.0, weight_visual=1.2)

    dense_cand = [
        ScoredCandidate(chunk_id="c1", document_id="doc.pdf", page_number=1, text="Prose text", score=0.9, rank=1)
    ]
    visual_cand = [
        RetrievalResult(
            chunk_id="page_img_p1",
            document_id="doc.pdf",
            page_number=1,
            text="[Diagram of Architecture]",
            modality="visual_page",
            fused_score=0.95
        )
    ]

    fused = fusion.fuse(dense_candidates=dense_cand, visual_candidates=visual_cand, top_k=2)
    assert len(fused) == 2
    modalities = {f.modality for f in fused}
    assert "text" in modalities
    assert "visual_page" in modalities


def test_rrf_multi_channel():
    fusion = ReciprocalRankFusion(k=60)
    rankings = {
        "dense": [ScoredCandidate(chunk_id="c1", document_id="d.pdf", page_number=1, text="A", score=0.9, rank=1)],
        "sparse": [ScoredCandidate(chunk_id="c1", document_id="d.pdf", page_number=1, text="A", score=2.5, rank=1)],
        "colpali": [ScoredCandidate(chunk_id="c1", document_id="d.pdf", page_number=1, text="A", score=0.8, rank=1)]
    }
    weights = {"dense": 1.0, "sparse": 1.0, "colpali": 1.5}

    results = fusion.fuse_multi(rankings=rankings, weights=weights, top_k=5)
    assert len(results) == 1
    assert results[0].chunk_id == "c1"
    expected = (1.0 / 61.0) + (1.0 / 61.0) + (1.5 / 61.0)
    assert abs(results[0].fused_score - expected) < 1e-6
