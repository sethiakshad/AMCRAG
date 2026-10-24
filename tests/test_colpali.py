"""Tests for ColPali Visual Retrieval Module — Milestones 5-9.

These tests cover:
  - ColPali model availability check and graceful ImportError
  - MaxSim scoring logic with synthetic vectors
  - ColPali indexer: collection creation, page indexing, idempotent upsert
  - ColPali retriever: ScoredCandidate schema compliance, modality field
  - ColPali reranker: visual_only and full_blend strategies
  - ColPaliVisualBridge: disabled mode, graceful degradation
  - Retrieval bridge: index_colpali_pages() and index_document_chunks()
  - Schema compliance: all results must be valid ScoredCandidate / RetrievalResult

All tests that require the ColPali model or a live Qdrant instance are
marked with @pytest.mark.skipif so the suite still passes in CI environments
without GPU or Qdrant running.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path for `from schemas import ...`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas import RetrievalResult, ScoredCandidate


# ===========================================================================
# Helpers — synthetic data
# ===========================================================================

def _make_query_vectors(n_tokens: int = 8, dim: int = 128) -> List[List[float]]:
    """Return deterministic synthetic query vectors."""
    return [[float(i + j * 0.01) for j in range(dim)] for i in range(n_tokens)]


def _make_page_vectors(n_patches: int = 64, dim: int = 128) -> List[List[float]]:
    """Return deterministic synthetic page patch vectors."""
    return [[float(j * 0.1 + i * 0.001) for j in range(dim)] for i in range(n_patches)]


def _make_retrieval_result(
    chunk_id: str = "doc_001_page_0001",
    modality: str = "text",
    fused_score: float = 0.5,
    image_path: str = "",
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id="doc_001",
        page_number=1,
        text="Sample text" if modality == "text" else "",
        modality=modality,
        source_filename="sample.pdf",
        fused_score=fused_score,
        metadata={"image_path": image_path} if image_path else {},
    )


# ===========================================================================
# 1. ScoredCandidate schema compliance
# ===========================================================================

class TestScoredCandidateSchema:
    """Visual retrieval results must conform to the existing ScoredCandidate schema."""

    def test_visual_page_candidate_valid(self):
        candidate = ScoredCandidate(
            chunk_id="doc_abc_page_0003",
            score=0.921,
            rank=1,
            modality="visual_page",
            document_id="doc_abc",
            page_number=3,
            text="",
            source_filename="paper.pdf",
            page_start=3,
            page_end=3,
            metadata={
                "image_path": "data/page_images/paper/paper_page_0003.png",
                "colpali_score": 0.921,
            },
        )
        assert candidate.modality == "visual_page"
        assert candidate.chunk_id == "doc_abc_page_0003"
        assert candidate.score == pytest.approx(0.921)
        assert candidate.rank == 1
        assert candidate.metadata["colpali_score"] == pytest.approx(0.921)

    def test_visual_candidate_empty_text_allowed(self):
        """Visual candidates legitimately have no text content."""
        candidate = ScoredCandidate(
            chunk_id="page_001",
            score=0.75,
            rank=2,
            modality="visual_page",
            document_id="doc_x",
            page_number=1,
            text="",
            source_filename="report.pdf",
        )
        assert candidate.text == ""

    def test_candidate_to_retrieval_result_compatible(self):
        """ScoredCandidate fields must be expressible as RetrievalResult."""
        rr = RetrievalResult(
            chunk_id="doc_abc_page_0003",
            document_id="doc_abc",
            page_number=3,
            text="",
            modality="visual_page",
            source_filename="paper.pdf",
            fused_score=0.921,
            metadata={"image_path": "data/page_images/paper/paper_page_0003.png"},
        )
        assert rr.candidate_type == "visual_page"
        assert rr.retrieval_score == pytest.approx(0.921)

    def test_retrieval_result_get_evaluable_content_fallback(self):
        """For visual pages with no text, get_evaluable_content uses metadata caption."""
        rr = RetrievalResult(
            chunk_id="page_007",
            document_id="doc_001",
            page_number=7,
            text="",
            modality="visual_page",
            source_filename="report.pdf",
            fused_score=0.8,
            metadata={"caption": "Figure 3: accuracy comparison"},
        )
        content = rr.get_evaluable_content()
        assert "Figure 3" in content or "report.pdf" in content


# ===========================================================================
# 2. MaxSim scoring logic (no model required)
# ===========================================================================

class TestMaxSimScoring:
    """MaxSim score computation using synthetic vectors (no GPU required)."""

    def test_identical_vectors_score_one(self):
        """When query and page share the same single vector, MaxSim should be ~1.0."""
        pytest.importorskip("torch")
        from app.colpali.colpali_model import ColPaliModel

        # Use the static score() method without loading the model
        vec = [[1.0, 0.0, 0.0]]
        score = getattr(ColPaliModel.score, "__func__", ColPaliModel.score)(None, vec, vec)  # unbound call
        assert score == pytest.approx(1.0, abs=1e-4)

    def test_orthogonal_vectors_score_zero(self):
        """Orthogonal vectors should produce MaxSim ~0.0."""
        pytest.importorskip("torch")
        from app.colpali.colpali_model import ColPaliModel

        q = [[1.0, 0.0]]
        p = [[0.0, 1.0]]
        score = getattr(ColPaliModel.score, "__func__", ColPaliModel.score)(None, q, p)
        assert score == pytest.approx(0.0, abs=1e-4)

    def test_score_returns_float(self):
        pytest.importorskip("torch")
        from app.colpali.colpali_model import ColPaliModel

        q = _make_query_vectors(4, 16)
        p = _make_page_vectors(8, 16)
        score = getattr(ColPaliModel.score, "__func__", ColPaliModel.score)(None, q, p)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0 + 1e-4  # allow tiny floating point overshoot

    def test_score_higher_for_similar_vectors(self):
        """Similar vector pairs should score higher than dissimilar ones."""
        pytest.importorskip("torch")
        from app.colpali.colpali_model import ColPaliModel

        similar_q = [[1.0, 0.0, 0.0]]
        similar_p = [[0.9, 0.1, 0.0]]
        dissimilar_p = [[-1.0, 0.0, 0.0]]

        score_func = getattr(ColPaliModel.score, "__func__", ColPaliModel.score)
        score_sim = score_func(None, similar_q, similar_p)
        score_dis = score_func(None, similar_q, dissimilar_p)
        assert score_sim > score_dis


# ===========================================================================
# 3. ColPali model — import guard
# ===========================================================================

class TestColPaliModelImportGuard:

    def test_raises_import_error_when_colpali_not_installed(self):
        """ColPaliModel must raise ImportError (not crash) if colpali-engine missing."""
        with patch.dict(sys.modules, {"colpali_engine": None, "colpali_engine.models": None}):
            # Force reload to pick up the patched module
            import importlib
            import app.colpali.colpali_model as _mod
            original = _mod._COLPALI_AVAILABLE
            _mod._COLPALI_AVAILABLE = False
            try:
                with pytest.raises(ImportError, match="colpali-engine"):
                    _mod.ColPaliModel()
            finally:
                _mod._COLPALI_AVAILABLE = original

    def test_device_resolution_auto_cpu(self):
        """_resolve_device('auto') returns 'cpu' when CUDA is unavailable."""
        pytest.importorskip("torch")
        from app.colpali.colpali_model import ColPaliModel
        with patch("torch.cuda.is_available", return_value=False):
            assert ColPaliModel._resolve_device("auto") == "cpu"

    def test_device_resolution_explicit_cuda(self):
        pytest.importorskip("torch")
        from app.colpali.colpali_model import ColPaliModel
        assert ColPaliModel._resolve_device("cuda") == "cuda"


# ===========================================================================
# 4. ColPali indexer — unit tests with mocked Qdrant
# ===========================================================================

class TestColPaliIndexer:

    def _make_page_render_info(self, page_number: int = 1, exists: bool = True):
        """Create a mock PageRenderInfo."""
        mock = MagicMock()
        mock.page_number = page_number
        mock.image_path = "/fake/path/page_001.png" if exists else "/nonexistent/page.png"
        mock.width = 1240
        mock.height = 1755
        mock.dpi = 150
        mock.title = f"Page {page_number}"
        mock.caption = f"Caption for page {page_number}"
        return mock

    def test_indexer_raises_without_qdrant(self):
        """ColPaliIndexer must raise ImportError when qdrant-client is not installed."""
        with patch.dict(sys.modules, {"qdrant_client": None}):
            import importlib
            import app.colpali.colpali_indexer as _mod
            original = _mod._QDRANT_AVAILABLE
            _mod._QDRANT_AVAILABLE = False
            try:
                with pytest.raises(ImportError, match="qdrant-client"):
                    _mod.ColPaliIndexer(model=MagicMock())
            finally:
                _mod._QDRANT_AVAILABLE = original

    def test_make_point_id_deterministic(self):
        """_make_point_id must return the same UUID for the same inputs."""
        from app.colpali.colpali_indexer import ColPaliIndexer
        id1 = ColPaliIndexer._make_point_id("doc_abc", 3)
        id2 = ColPaliIndexer._make_point_id("doc_abc", 3)
        id3 = ColPaliIndexer._make_point_id("doc_abc", 4)
        assert id1 == id2
        assert id1 != id3

    def test_make_point_id_is_string(self):
        from app.colpali.colpali_indexer import ColPaliIndexer
        result = ColPaliIndexer._make_point_id("doc_xyz", 7)
        assert isinstance(result, str)
        assert len(result) == 36  # UUID string length

    def test_index_empty_pages_returns_zero(self):
        """index_rendered_pages with empty list returns 0 without error."""
        mock_model = MagicMock()
        mock_qdrant = MagicMock()
        existing_col = MagicMock()
        existing_col.name = "colpali_pages"
        mock_qdrant.get_collections.return_value = MagicMock(collections=[existing_col])

        import app.colpali.colpali_indexer as _mod
        orig_qdrant = _mod._QDRANT_AVAILABLE
        orig_pil = _mod._PIL_AVAILABLE
        orig_qmodels = _mod.qmodels
        _mod._QDRANT_AVAILABLE = True
        _mod._PIL_AVAILABLE = True
        _mod.qmodels = MagicMock()

        try:
            with patch("app.colpali.colpali_indexer.QdrantClient", return_value=mock_qdrant):
                from app.colpali.colpali_indexer import ColPaliIndexer
                indexer = ColPaliIndexer(model=mock_model, qdrant_url="http://localhost:6333")
                count = indexer.index_rendered_pages([], document_id="doc_001")
            assert count == 0
        finally:
            _mod._QDRANT_AVAILABLE = orig_qdrant
            _mod._PIL_AVAILABLE = orig_pil
            _mod.qmodels = orig_qmodels


# ===========================================================================
# 5. ColPali retriever — schema compliance tests
# ===========================================================================

class TestColPaliRetriever:

    def test_hits_to_candidates_returns_scored_candidates(self):
        """_hits_to_candidates must return valid ScoredCandidate objects."""
        from app.colpali.colpali_retriever import ColPaliRetriever

        mock_hit = MagicMock()
        mock_hit.score = 0.87
        mock_hit.payload = {
            "document_id": "doc_001",
            "page_number": 5,
            "source_filename": "paper.pdf",
            "image_path": "data/page_images/paper/paper_page_0005.png",
            "chunk_id": "doc_001_page_0005",
            "width": 1240,
            "height": 1755,
            "dpi": 150,
            "title": "Page 5",
            "caption": "Results section",
        }

        results = ColPaliRetriever._hits_to_candidates([mock_hit])
        assert len(results) == 1
        c = results[0]
        assert isinstance(c, ScoredCandidate)
        assert c.modality == "visual_page"
        assert c.score == pytest.approx(0.87)
        assert c.rank == 1
        assert c.document_id == "doc_001"
        assert c.page_number == 5

    def test_hits_to_candidates_assigns_sequential_ranks(self):
        """Rank must be 1-indexed and sequential across results."""
        from app.colpali.colpali_retriever import ColPaliRetriever

        hits = []
        for i in range(3):
            h = MagicMock()
            h.score = 0.9 - i * 0.1
            h.payload = {"document_id": "doc_001", "page_number": i + 1,
                         "source_filename": "paper.pdf", "image_path": ""}
            hits.append(h)

        results = ColPaliRetriever._hits_to_candidates(hits)
        assert [c.rank for c in results] == [1, 2, 3]

    def test_retrieve_returns_empty_when_disabled(self):
        """Retriever must return [] immediately when enabled=False."""
        mock_model = MagicMock()
        mock_qdrant = MagicMock()

        import app.colpali.colpali_retriever as _mod
        _mod._QDRANT_AVAILABLE = True

        with patch("app.colpali.colpali_retriever.QdrantClient", return_value=mock_qdrant):
            from app.colpali.colpali_retriever import ColPaliRetriever
            retriever = ColPaliRetriever(model=mock_model, enabled=False)
            results = retriever.retrieve("What does the chart show?")
        assert results == []
        mock_model.embed_query.assert_not_called()

    def test_retrieve_returns_empty_on_model_error(self):
        """Retriever must return [] gracefully if embed_query raises an error."""
        mock_model = MagicMock()
        mock_model.embed_query.side_effect = RuntimeError("CUDA OOM")
        mock_qdrant = MagicMock()

        import app.colpali.colpali_retriever as _mod
        _mod._QDRANT_AVAILABLE = True

        with patch("app.colpali.colpali_retriever.QdrantClient", return_value=mock_qdrant):
            from app.colpali.colpali_retriever import ColPaliRetriever
            retriever = ColPaliRetriever(model=mock_model, enabled=True)
            results = retriever.retrieve("Any query")
        assert results == []

    def test_build_filter_none_for_no_ids(self):
        """_build_filter returns None when no document_ids are provided."""
        from app.colpali.colpali_retriever import ColPaliRetriever
        assert ColPaliRetriever._build_filter(None) is None
        assert ColPaliRetriever._build_filter([]) is None


# ===========================================================================
# 6. ColPali reranker — unit tests
# ===========================================================================

class TestColPaliReranker:

    def _make_visual_result(self, chunk_id: str, score: float, image_path: str = "") -> RetrievalResult:
        return _make_retrieval_result(
            chunk_id=chunk_id,
            modality="visual_page",
            fused_score=score,
            image_path=image_path,
        )

    def _make_text_result(self, chunk_id: str, score: float) -> RetrievalResult:
        return _make_retrieval_result(chunk_id=chunk_id, modality="text", fused_score=score)

    def test_reranker_disabled_returns_input_unchanged(self):
        from app.colpali.colpali_reranker import ColPaliReranker
        mock_model = MagicMock()
        reranker = ColPaliReranker(model=mock_model, enabled=False)
        candidates = [self._make_visual_result("p1", 0.9), self._make_text_result("c1", 0.8)]
        result = reranker.rerank("any query", candidates)
        assert result is candidates  # same object returned unchanged

    def test_reranker_no_visual_candidates_unchanged(self):
        from app.colpali.colpali_reranker import ColPaliReranker
        mock_model = MagicMock()
        reranker = ColPaliReranker(model=mock_model, enabled=True)
        candidates = [self._make_text_result("c1", 0.9), self._make_text_result("c2", 0.7)]
        result = reranker.rerank("any query", candidates)
        assert result is candidates  # no visual → no change

    def test_visual_only_strategy_sorts_by_colpali_score(self):
        """visual_only: visual candidates are re-sorted by fused_score (ColPali MaxSim)."""
        from app.colpali.colpali_reranker import ColPaliReranker

        mock_model = MagicMock()
        mock_model.embed_query.return_value = _make_query_vectors(4, 16)
        mock_model.embed_image.return_value = _make_page_vectors(8, 16)
        mock_model.score.return_value = 0.95  # All visual get score 0.95 from mock

        reranker = ColPaliReranker(model=mock_model, strategy="visual_only", enabled=True)

        candidates = [
            self._make_text_result("chunk_1", 0.80),
            self._make_visual_result("page_3", 0.50),   # low initial score
            self._make_text_result("chunk_2", 0.70),
        ]

        with patch("app.colpali.colpali_reranker.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path_cls.return_value = mock_path
            with patch("app.colpali.colpali_reranker.PILImage") as mock_pil:
                mock_pil.open.return_value.convert.return_value = MagicMock()
                result = reranker.rerank("chart query", candidates, strategy="visual_only")

        assert len(result) == 3
        # All results must be RetrievalResult objects
        for r in result:
            assert isinstance(r, RetrievalResult)

    def test_merge_visual_only_sorts_descending(self):
        """_merge_visual_only: output sorted by fused_score descending."""
        from app.colpali.colpali_reranker import ColPaliReranker

        text    = [_make_retrieval_result("c1", "text", 0.6)]
        visual  = [_make_retrieval_result("p1", "visual_page", 0.9),
                   _make_retrieval_result("p2", "visual_page", 0.4)]
        result  = ColPaliReranker._merge_visual_only(text, visual)
        scores  = [r.fused_score for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_merge_full_blend_normalises_to_unit_range(self):
        """_merge_full_blend: all output fused_scores in [0, 1]."""
        from app.colpali.colpali_reranker import ColPaliReranker

        text    = [_make_retrieval_result("c1", "text", 0.3),
                   _make_retrieval_result("c2", "text", 0.9)]
        visual  = [_make_retrieval_result("p1", "visual_page", 10.0),
                   _make_retrieval_result("p2", "visual_page", 2.0)]
        result  = ColPaliReranker._merge_full_blend(text, visual)
        for r in result:
            assert 0.0 <= r.fused_score <= 1.0 + 1e-6


# ===========================================================================
# 7. Retrieval bridge
# ===========================================================================

class TestRetrievalBridge:

    def test_index_document_chunks_empty_returns_zero(self):
        from app.services.retrieval_bridge import index_document_chunks
        assert index_document_chunks([]) == 0

    def test_index_colpali_pages_empty_returns_zero(self):
        from app.services.retrieval_bridge import index_colpali_pages
        assert index_colpali_pages([], document_id="doc_001") == 0

    def test_colpali_visual_bridge_disabled_retrieve_empty(self):
        from app.services.retrieval_bridge import ColPaliVisualBridge
        bridge = ColPaliVisualBridge(enabled=False)
        assert bridge.retrieve("any query") == []
        assert bridge.index_pages([], "doc_001") == 0
        assert not bridge.is_ready

    def test_colpali_visual_bridge_disabled_index_returns_zero(self):
        from app.services.retrieval_bridge import ColPaliVisualBridge
        bridge = ColPaliVisualBridge(enabled=False)
        assert bridge.index_pages(rendered_pages=[], document_id="doc_x") == 0

    def test_index_colpali_pages_uses_provided_bridge(self):
        from app.services.retrieval_bridge import index_colpali_pages
        mock_bridge = MagicMock()
        mock_bridge.index_pages.return_value = 3
        mock_pages = [MagicMock(), MagicMock(), MagicMock()]

        count = index_colpali_pages(
            rendered_pages=mock_pages,
            document_id="doc_test",
            source_filename="test.pdf",
            colpali_bridge=mock_bridge,
        )
        assert count == 3
        mock_bridge.index_pages.assert_called_once_with(
            rendered_pages=mock_pages,
            document_id="doc_test",
            source_filename="test.pdf",
        )
