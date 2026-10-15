"""
Reciprocal Rank Fusion (RRF) Implementation.
Combines Dense Semantic, Sparse Lexical, and Optional Visual (ColPali) candidates
cleanly without score calibration issues.
Owner: Om Khapekar (Person 2 - Dense/Sparse Text Retrieval & Fusion)
Shared Interface for Person 3 (ColPali Visual Retrieval)
"""
from typing import List, Dict, Any, Optional
from schemas import ScoredCandidate, RetrievalResult


class ReciprocalRankFusion:
    def __init__(
        self,
        k: int = 60,
        weight_dense: float = 1.0,
        weight_sparse: float = 1.0,
        weight_visual: float = 1.0
    ):
        """
        k: Smoothing constant that prevents high ranks from dominating disproportionately.
           Empirical standard across IR literature (Cormack et al.) is k = 60.
        weight_dense: Modality weight multiplier for dense candidates.
        weight_sparse: Modality weight multiplier for BM25 candidates.
        weight_visual: Modality weight multiplier for ColPali visual candidates.
        """
        self.k = k
        self.weight_dense = weight_dense
        self.weight_sparse = weight_sparse
        self.weight_visual = weight_visual

    def fuse(
        self,
        dense_candidates: Optional[List[Any]] = None,
        sparse_candidates: Optional[List[Any]] = None,
        visual_candidates: Optional[List[Any]] = None,
        top_k: int = 15
    ) -> List[RetrievalResult]:
        """
        Merges ranked candidate lists using weighted Reciprocal Rank Fusion:
        RRF_Score(d) = sum_{r in R} (w_r / (k + rank_r(d)))

        Supports:
        - Dense text candidates (BGE + Qdrant)
        - Sparse text candidates (BM25)
        - Visual page candidates (Person 3's ColPali)
        """
        dense_candidates = dense_candidates or []
        sparse_candidates = sparse_candidates or []
        visual_candidates = visual_candidates or []

        fused_map: Dict[str, Dict[str, Any]] = {}

        def _get_val(cand: Any, attr: str, default: Any = None) -> Any:
            if hasattr(cand, attr):
                return getattr(cand, attr)
            if isinstance(cand, dict):
                return cand.get(attr, default)
            return default

        # 1. Process Dense Candidates
        for cand in dense_candidates:
            cid = _get_val(cand, "chunk_id", str(_get_val(cand, "candidate_id", "")))
            rank = _get_val(cand, "rank", 1)
            score = _get_val(cand, "score", 0.0)
            rrf_contrib = self.weight_dense / (self.k + rank)

            fused_map[cid] = {
                "chunk_id": cid,
                "document_id": _get_val(cand, "document_id", "unknown"),
                "page_number": _get_val(cand, "page_number", 0),
                "text": _get_val(cand, "text", ""),
                "modality": _get_val(cand, "modality", "text"),
                "source_filename": _get_val(cand, "source_filename", None),
                "page_start": _get_val(cand, "page_start", None),
                "page_end": _get_val(cand, "page_end", None),
                "dense_score": score,
                "sparse_score": None,
                "dense_rank": rank,
                "sparse_rank": None,
                "fused_score": rrf_contrib,
                "metadata": dict(_get_val(cand, "metadata", {}))
            }

        # 2. Process Sparse (BM25) Candidates
        for cand in sparse_candidates:
            cid = _get_val(cand, "chunk_id", str(_get_val(cand, "candidate_id", "")))
            rank = _get_val(cand, "rank", 1)
            score = _get_val(cand, "score", 0.0)
            rrf_contrib = self.weight_sparse / (self.k + rank)

            if cid in fused_map:
                fused_map[cid]["sparse_score"] = score
                fused_map[cid]["sparse_rank"] = rank
                fused_map[cid]["fused_score"] += rrf_contrib
            else:
                fused_map[cid] = {
                    "chunk_id": cid,
                    "document_id": _get_val(cand, "document_id", "unknown"),
                    "page_number": _get_val(cand, "page_number", 0),
                    "text": _get_val(cand, "text", ""),
                    "modality": _get_val(cand, "modality", "text"),
                    "source_filename": _get_val(cand, "source_filename", None),
                    "page_start": _get_val(cand, "page_start", None),
                    "page_end": _get_val(cand, "page_end", None),
                    "dense_score": None,
                    "sparse_score": score,
                    "dense_rank": None,
                    "sparse_rank": rank,
                    "fused_score": rrf_contrib,
                    "metadata": dict(_get_val(cand, "metadata", {}))
                }

        # 3. Process Visual (ColPali) Candidates (Person 3 Integration Extension Point)
        for cand in visual_candidates:
            cid = _get_val(cand, "chunk_id", str(_get_val(cand, "candidate_id", "")))
            rank = _get_val(cand, "rank", 1)
            score = _get_val(cand, "score", _get_val(cand, "fused_score", 0.0))
            rrf_contrib = self.weight_visual / (self.k + rank)

            if cid in fused_map:
                fused_map[cid]["fused_score"] += rrf_contrib
                fused_map[cid]["metadata"]["visual_rank"] = rank
                fused_map[cid]["metadata"]["visual_score"] = score
            else:
                fused_map[cid] = {
                    "chunk_id": cid,
                    "document_id": _get_val(cand, "document_id", "unknown"),
                    "page_number": _get_val(cand, "page_number", 0),
                    "text": _get_val(cand, "text", ""),
                    "modality": _get_val(cand, "modality", "visual_page"),
                    "source_filename": _get_val(cand, "source_filename", None),
                    "page_start": _get_val(cand, "page_start", None),
                    "page_end": _get_val(cand, "page_end", None),
                    "dense_score": None,
                    "sparse_score": None,
                    "dense_rank": None,
                    "sparse_rank": None,
                    "fused_score": rrf_contrib,
                    "metadata": {
                        **dict(_get_val(cand, "metadata", {})),
                        "visual_rank": rank,
                        "visual_score": score
                    }
                }

        # 4. Sort descending by fused_score
        sorted_results = sorted(
            fused_map.values(),
            key=lambda item: item["fused_score"],
            reverse=True
        )[:top_k]

        return [RetrievalResult(**res) for res in sorted_results]

    def fuse_multi(
        self,
        rankings: Dict[str, List[Any]],
        weights: Optional[Dict[str, float]] = None,
        top_k: int = 15
    ) -> List[RetrievalResult]:
        """
        Generic multi-list RRF merger accepting arbitrary named retrieval channels:
        rankings: e.g. {"dense": [...], "sparse": [...], "colpali": [...]}
        """
        weights = weights or {}
        fused_map: Dict[str, Dict[str, Any]] = {}

        def _get_val(cand: Any, attr: str, default: Any = None) -> Any:
            if hasattr(cand, attr):
                return getattr(cand, attr)
            if isinstance(cand, dict):
                return cand.get(attr, default)
            return default

        for channel_name, cand_list in rankings.items():
            ch_weight = weights.get(channel_name, 1.0)
            for idx, cand in enumerate(cand_list, start=1):
                cid = _get_val(cand, "chunk_id", str(_get_val(cand, "candidate_id", "")))
                rank = _get_val(cand, "rank", idx)
                score = _get_val(cand, "score", None)
                rrf_contrib = ch_weight / (self.k + rank)

                if cid not in fused_map:
                    fused_map[cid] = {
                        "chunk_id": cid,
                        "document_id": _get_val(cand, "document_id", "unknown"),
                        "page_number": _get_val(cand, "page_number", 0),
                        "text": _get_val(cand, "text", ""),
                        "modality": _get_val(cand, "modality", "text"),
                        "source_filename": _get_val(cand, "source_filename", None),
                        "page_start": _get_val(cand, "page_start", None),
                        "page_end": _get_val(cand, "page_end", None),
                        "dense_score": None,
                        "sparse_score": None,
                        "dense_rank": None,
                        "sparse_rank": None,
                        "fused_score": 0.0,
                        "metadata": dict(_get_val(cand, "metadata", {}))
                    }

                fused_map[cid]["fused_score"] += rrf_contrib
                fused_map[cid]["metadata"][f"{channel_name}_rank"] = rank
                if score is not None:
                    fused_map[cid]["metadata"][f"{channel_name}_score"] = score

                if channel_name == "dense":
                    fused_map[cid]["dense_score"] = score
                    fused_map[cid]["dense_rank"] = rank
                elif channel_name == "sparse":
                    fused_map[cid]["sparse_score"] = score
                    fused_map[cid]["sparse_rank"] = rank

        sorted_results = sorted(
            fused_map.values(),
            key=lambda item: item["fused_score"],
            reverse=True
        )[:top_k]

        return [RetrievalResult(**res) for res in sorted_results]
