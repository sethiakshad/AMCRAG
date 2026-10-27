"""Scanned PDF Multimodal RAG Regression Test Suite.

Validates:
1. Observable visual indexing lifecycle (pending -> indexing -> indexed) and verified Qdrant point persistence.
2. Candidate modality and metadata (colpali_score, colpali_rank, image_path, ocr_text) preservation through fusion.
3. Tested visual-evidence CRAG evaluation strategy (calibrated MaxSim / Cosine scores vs fused RRF scores).
4. Safe gate rejection of irrelevant visual pages.
5. Auto-mode query routing based on document scanning / chunking status.
6. End-to-end scanned PDF query execution without zero-hallucination safe fallback.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.crag.controller import CRAGController
from app.crag.decisions import CRAGDecisionEngine, DecisionConfig
from app.crag.evaluator import HeuristicCRAGEvaluator, T5CRAGEvaluator
from app.schemas.api import ModelModality, QueryRequest
from app.schemas.retrieval import RetrievalCandidate
from app.services.orchestrator import INSUFFICIENT_EVIDENCE_ANSWER, OrchestratorConfig, RAGOrchestrator


class TestScannedPDFRegression:
    """Regression test cases verifying the repair of AMCRAG visual pipeline."""

    # -------------------------------------------------------------------------
    # Priority 2: Modality & Metadata Preservation
    # -------------------------------------------------------------------------

    def test_modality_preserved_in_retrieval_candidate_conversion(self):
        """Verify that fused RetrievalResult with modality='visual_page' retains candidate_type='visual_page'."""
        orchestrator = RAGOrchestrator()

        # Mock duck-typed RetrievalResult from Person 2's hybrid retriever
        class DuckRetrievalResult:
            candidate_id = "doc_scan_p1"
            document_id = "doc_scan"
            source_filename = "scan.pdf"
            page_start = 1
            page_end = 1
            modality = "visual_page"
            candidate_type = None
            text = ""
            content = ""
            page_reference = None
            retrieval_method = "rrf"
            retrieval_rank = 1
            retrieval_score = 0.01639
            metadata = {
                "image_path": "data/page_images/doc_scan/page_0001.png",
                "colpali_score": 14.2,
                "colpali_rank": 1,
                "ocr_text": "Support Vector Machine margin calculation w^T x + b = 0",
            }

        mock_item = DuckRetrievalResult()
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [mock_item]
        orchestrator.retriever = mock_retriever

        candidates = orchestrator._fetch_candidates(
            query="Explain SVM margin",
            top_k=3,
            modality=ModelModality.VISION,
            document_ids=["doc_scan"],
        )

        assert len(candidates) == 1
        cand = candidates[0]
        assert cand.candidate_type == "visual_page"
        assert cand.metadata.get("modality") == "visual_page"
        assert cand.metadata.get("colpali_score") == 14.2
        assert cand.metadata.get("colpali_rank") == 1
        assert cand.page_reference == "data/page_images/doc_scan/page_0001.png"
        assert "SVM" in cand.text or "Support Vector" in cand.text

    # -------------------------------------------------------------------------
    # Priority 3: CRAG Evaluator Visual Evidence Strategy
    # -------------------------------------------------------------------------

    def test_heuristic_crag_evaluator_strong_maxsim_score_passes_gate(self):
        """A strong unnormalized ColPali MaxSim score (>= 8.0) maps above 0.65 (CORRECT)."""
        evaluator = HeuristicCRAGEvaluator()
        cand = RetrievalCandidate(
            candidate_id="p1",
            document_id="doc_scan",
            source_filename="scan.pdf",
            page_start=1,
            page_end=1,
            candidate_type="visual_page",
            text=None,
            page_reference="page_0001.png",
            retrieval_method="colpali",
            retrieval_rank=1,
            retrieval_score=15.0,  # MaxSim score = 15.0
            metadata={"colpali_score": 15.0},
        )

        evaluation = evaluator.evaluate_candidate(
            query="What is the margin equation?", candidate=cand
        )
        assert evaluation.relevance_score >= 0.65
        assert evaluation.is_relevant is True
        assert "modality=visual_page" in evaluation.notes

    def test_heuristic_crag_evaluator_weak_maxsim_score_rejected(self):
        """An irrelevant visual page (MaxSim <= 3.5) maps below 0.30 (INCORRECT), safely rejected."""
        evaluator = HeuristicCRAGEvaluator()
        cand = RetrievalCandidate(
            candidate_id="p3",
            document_id="doc_scan",
            source_filename="scan.pdf",
            page_start=3,
            page_end=3,
            candidate_type="visual_page",
            text=None,
            page_reference="page_0003.png",
            retrieval_method="colpali",
            retrieval_rank=5,
            retrieval_score=2.1,  # Low irrelevant MaxSim score
            metadata={"colpali_score": 2.1},
        )

        evaluation = evaluator.evaluate_candidate(
            query="What is the margin equation?", candidate=cand
        )
        assert evaluation.relevance_score < 0.30
        assert evaluation.is_relevant is False

    def test_heuristic_crag_evaluator_fused_rrf_score_calibrated_via_metadata(self):
        """A fused candidate with RRF score=0.01639 uses metadata['colpali_score'] and passes gate."""
        evaluator = HeuristicCRAGEvaluator()
        cand = RetrievalCandidate(
            candidate_id="p1",
            document_id="doc_scan",
            source_filename="scan.pdf",
            page_start=1,
            page_end=1,
            candidate_type="visual_page",
            text="[Visual Page from scan.pdf, page 1]",  # Placeholder text
            page_reference="page_0001.png",
            retrieval_method="rrf",
            retrieval_rank=1,
            retrieval_score=0.01639,  # RRF score
            metadata={"colpali_score": 12.0, "colpali_rank": 1},
        )

        evaluation = evaluator.evaluate_candidate(
            query="Explain SVM margin", candidate=cand
        )
        # Should NOT evaluate to 0.0065 based on placeholder text overlap!
        assert evaluation.relevance_score >= 0.65
        assert evaluation.is_relevant is True

    def test_heuristic_crag_evaluator_ocr_blending(self):
        """OCR text overlap enhances confidence when terms match, without penalizing when absent."""
        evaluator = HeuristicCRAGEvaluator()

        # Visual page without OCR text
        cand_no_ocr = RetrievalCandidate(
            candidate_id="p1",
            document_id="doc_scan",
            source_filename="scan.pdf",
            page_start=1,
            page_end=1,
            candidate_type="visual_page",
            text="",
            page_reference="page_0001.png",
            retrieval_method="colpali",
            retrieval_rank=1,
            retrieval_score=10.0,
            metadata={"colpali_score": 10.0},
        )

        # Visual page with matching OCR text
        cand_with_ocr = RetrievalCandidate(
            candidate_id="p1",
            document_id="doc_scan",
            source_filename="scan.pdf",
            page_start=1,
            page_end=1,
            candidate_type="visual_page",
            text="The margin is defined as 2 / ||w|| where w is the weight vector.",
            page_reference="page_0001.png",
            retrieval_method="colpali",
            retrieval_rank=1,
            retrieval_score=10.0,
            metadata={
                "colpali_score": 10.0,
                "ocr_text": "The margin is defined as 2 / ||w|| where w is the weight vector.",
            },
        )

        eval_no_ocr = evaluator.evaluate_candidate("What is the margin formula?", cand_no_ocr)
        eval_with_ocr = evaluator.evaluate_candidate("What is the margin formula?", cand_with_ocr)

        assert eval_no_ocr.relevance_score >= 0.65
        assert eval_with_ocr.relevance_score >= eval_no_ocr.relevance_score

    def test_t5_evaluator_routes_pure_visual_candidates_without_tokenizing_placeholder(self):
        """T5CRAGEvaluator evaluates pure visual candidates via visual strategy instead of placeholder text."""
        evaluator = T5CRAGEvaluator(fallback_on_error=True)
        cand = RetrievalCandidate(
            candidate_id="p1",
            document_id="doc_scan",
            source_filename="scan.pdf",
            page_start=1,
            page_end=1,
            candidate_type="visual_page",
            text=None,
            page_reference="page_0001.png",
            retrieval_method="colpali",
            retrieval_rank=1,
            retrieval_score=12.0,
            metadata={"colpali_score": 12.0},
        )

        evals = evaluator.evaluate_batch(query="margin formula", candidates=[cand])
        assert len(evals) == 1
        assert evals[0].relevance_score >= 0.65
        assert evals[0].is_relevant is True

    # -------------------------------------------------------------------------
    # Priority 4: Auto-Mode Routing
    # -------------------------------------------------------------------------

    def test_auto_mode_routing_for_scanned_document(self, tmp_path, monkeypatch):
        """Auto mode selects ModelModality.VISION for scanned PDF even when query has no visual keywords."""
        orchestrator = RAGOrchestrator()

        # Mock processed_dir with a scanned document JSON
        doc_data = {
            "document_id": "doc_scanned_001",
            "document_name": "scanned_notes.pdf",
            "is_scanned": True,
            "ocr_needed": True,
            "total_chunks": 0,
            "chunks": [],
            "rendered_pages": ["p1.png", "p2.png"],
        }
        json_file = tmp_path / "doc_scanned_001.json"
        json_file.write_text(json.dumps(doc_data), encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.get_processed_path.return_value = tmp_path
        monkeypatch.setattr("app.config.default_settings", mock_settings)

        # Query has NO visual keywords: "Explain the margin calculation"
        intent = orchestrator.analyze_query_intent(
            query="Explain the margin calculation",
            document_ids=["doc_scanned_001"],
        )
        assert intent == ModelModality.VISION

    def test_auto_mode_routing_for_textual_document(self, tmp_path, monkeypatch):
        """Auto mode keeps ModelModality.TEXT for non-scanned document with text chunks."""
        orchestrator = RAGOrchestrator()

        doc_data = {
            "document_id": "doc_text_001",
            "document_name": "annual_report.pdf",
            "is_scanned": False,
            "ocr_needed": False,
            "total_chunks": 15,
            "chunks": [{"chunk_id": "c1", "text": "Content"}],
            "rendered_pages": ["p1.png"],
        }
        json_file = tmp_path / "doc_text_001.json"
        json_file.write_text(json.dumps(doc_data), encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.get_processed_path.return_value = tmp_path
        monkeypatch.setattr("app.config.default_settings", mock_settings)

        intent = orchestrator.analyze_query_intent(
            query="Explain the margin calculation",
            document_ids=["doc_text_001"],
        )
        assert intent == ModelModality.TEXT

    # -------------------------------------------------------------------------
    # Priority 1: Observable Lifecycle & Point Verification
    # -------------------------------------------------------------------------

    def test_observable_indexing_lifecycle_and_point_verification(self, tmp_path, monkeypatch):
        """index_colpali_pages records indexing state and verifies points persisted in Qdrant."""
        from app.services.retrieval_bridge import index_colpali_pages

        mock_settings = MagicMock()
        mock_settings.get_processed_path.return_value = tmp_path
        monkeypatch.setattr("app.config.default_settings", mock_settings)

        doc_id = "doc_test_lifecycle"
        doc_json = tmp_path / f"{doc_id}.json"
        doc_json.write_text(json.dumps({"document_id": doc_id, "rendered_pages": ["p1", "p2", "p3"]}))

        mock_bridge = MagicMock()
        mock_bridge.index_pages.return_value = 3
        mock_bridge.count_document_pages.return_value = 3
        mock_bridge.max_pages = 20

        count = index_colpali_pages(
            rendered_pages=["p1.png", "p2.png", "p3.png"],
            document_id=doc_id,
            source_filename="test.pdf",
            colpali_bridge=mock_bridge,
        )

        assert count == 3
        persisted_data = json.loads(doc_json.read_text(encoding="utf-8"))
        assert persisted_data["visual_indexed"] is True
        assert persisted_data["visual_indexing_status"] == "indexed"
        assert persisted_data["visual_pages_indexed"] == 3
        assert "visual_indexing_completed_at" in persisted_data

    # -------------------------------------------------------------------------
    # End-to-End Scanned PDF Execution without Safe Fallback
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_scanned_pdf_end_to_end_no_hallucination_safe_fallback(self):
        """End-to-end execution of a scanned PDF query: CRAG passes evidence, answering prompt without fallback."""
        mock_visual_bridge = MagicMock()
        mock_visual_bridge.enabled = True
        mock_visual_bridge.retrieve.return_value = [
            RetrievalCandidate(
                candidate_id="doc_svm_p1",
                document_id="doc_svm",
                source_filename="6-Support+Vector+Classifier.pdf",
                page_start=1,
                page_end=1,
                candidate_type="visual_page",
                text="",
                page_reference="data/page_images/doc_svm/page_0001.png",
                retrieval_method="colpali",
                retrieval_rank=1,
                retrieval_score=14.5,
                metadata={
                    "image_path": "data/page_images/doc_svm/page_0001.png",
                    "colpali_score": 14.5,
                    "colpali_rank": 1,
                },
            )
        ]

        # Mock text retriever returning empty (scanned PDF has 0 text chunks)
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []

        mock_generator = MagicMock()
        mock_generator.generate.return_value = "The margin in SVM is the perpendicular distance between the decision boundary and the closest data points (support vectors)."

        orchestrator = RAGOrchestrator(
            config=OrchestratorConfig(enable_crag=True),
            retriever=mock_retriever,
            visual_bridge=mock_visual_bridge,
            generator=mock_generator,
        )

        request = QueryRequest(
            query="Explain the margin calculation in SVM",
            document_ids=["doc_svm"],
            model_modality=ModelModality.VISION,
            enable_crag=True,
        )

        response = await orchestrator.query(request)

        # Must NOT trigger the zero-hallucination safe fallback!
        assert response.answer != INSUFFICIENT_EVIDENCE_ANSWER
        assert response.insufficient_evidence is False
        assert response.crag_decision == "CORRECT"
        assert len(response.sources) >= 1
        assert response.sources[0].type == "visual"
        assert len(response.visual_inputs) >= 1
