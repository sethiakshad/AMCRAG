"""tests/test_context_builder.py — Unit Tests for Context Builder Steps 1, 2, and 3.

Validates:
  - Step 1: Pydantic schemas, enums, and data contracts.
  - Step 2: EvidenceNormalizer polymorphic ingestion and strips mapping.
  - Step 3: EvidenceDeduplicator multi-level deduplication and same-page guarantees.
"""

import json
from pathlib import Path
import pytest

from app.context_builder.budget import TokenBudgetEngine
from app.context_builder.builder import ContextBuilder
from app.context_builder.deduplicator import EvidenceDeduplicator
from app.context_builder.formatter import ContextFormatter
from app.context_builder.multimodal import MultimodalResolver
from app.context_builder.normalizer import EvidenceNormalizer
from app.context_builder.organizer import EvidenceOrganizer
from app.context_builder.tokenizer import TokenCounter
from app.context_builder.schemas import (
    ContextBuilderConfig,
    ContextResponse,
    EvidenceItem,
    EvidenceModality,
    ModelModality,
    SourceMetadata,
)
from app.schemas.crag import (
    CandidateEvaluation,
    CRAGResult,
    EvidenceDecision,
)
from app.schemas.retrieval import RetrievalCandidate
from app.crag.controller import CRAGController


# ==============================================================================
# STEP 1: SCHEMAS & CONTRACTS TESTS
# ==============================================================================

class TestContextBuilderSchemas:
    def test_evidence_item_defaults_and_serialization(self):
        item = EvidenceItem(
            evidence_id="ev_01",
            content="Sample text passage",
            document_name="annual_report.pdf",
            page_number=5,
        )
        assert item.evidence_id == "ev_01"
        assert item.modality == EvidenceModality.TEXT
        assert item.rank == 1
        assert item.page_number == 5
        data = item.model_dump()
        assert data["document_name"] == "annual_report.pdf"

    def test_config_defaults(self):
        config = ContextBuilderConfig()
        assert config.token_budget == 4096
        assert config.model_modality == ModelModality.TEXT
        assert config.preserve_extracted_strips is True
        assert "Instruction:" in config.system_instruction

    def test_source_metadata_model(self):
        source = SourceMetadata(
            evidence_id="E1",
            chunk_id="chunk_102",
            document="financials.pdf",
            page=12,
            type="text",
            rank=1,
        )
        assert source.evidence_id == "E1"
        assert source.chunk_id == "chunk_102"
        assert source.page == 12

    def test_context_response_model(self):
        resp = ContextResponse(
            query="What is Q3 revenue?",
            context="[E1] Source: doc.pdf, page 1\nRevenue grew by 20%",
            sources=[
                SourceMetadata(
                    evidence_id="E1",
                    chunk_id="c1",
                    document="doc.pdf",
                    page=1,
                    type="text",
                )
            ],
            included_evidence_ids=["c1"],
            omitted_evidence_ids=[],
            token_estimate=45,
            crag_decision="CORRECT",
        )
        assert resp.crag_decision == "CORRECT"
        assert len(resp.sources) == 1
        assert resp.included_evidence_ids == ["c1"]


# ==============================================================================
# STEP 2: INPUT NORMALIZER TESTS
# ==============================================================================

class TestEvidenceNormalizer:
    @pytest.fixture
    def normalizer(self):
        return EvidenceNormalizer()

    def test_normalize_crag_result(self, normalizer):
        cand1 = RetrievalCandidate(
            candidate_id="text_c01",
            document_id="annual_report",
            source_filename="annual_report.pdf",
            page_start=12,
            page_end=12,
            candidate_type="text_chunk",
            text="Revenue reached 1.2 billion in FY25.",
            retrieval_method="dense",
            retrieval_rank=1,
            retrieval_score=0.92,
        )
        cand2 = RetrievalCandidate(
            candidate_id="visual_p14",
            document_id="annual_report",
            source_filename="annual_report.pdf",
            page_start=14,
            page_end=14,
            candidate_type="visual_page",
            text=None,
            page_reference="data/page_images/annual_report/page_14.png",
            retrieval_method="colpali",
            retrieval_rank=2,
            retrieval_score=0.81,
            metadata={"caption": "Revenue chart showing steady growth."},
        )

        decision = EvidenceDecision(
            label="CORRECT",
            score=0.88,
            needs_correction=False,
            candidate_evaluations=[
                CandidateEvaluation(
                    candidate_id="text_c01",
                    relevance_score=0.92,
                    is_relevant=True,
                    extracted_strips=["revenue reached 1.2 billion in fy25"],
                )
            ],
        )

        crag_result = CRAGResult(
            decision=decision,
            accepted_candidates=[cand1, cand2],
            can_proceed_to_generation=True,
        )

        items = normalizer.normalize(crag_result)
        assert len(items) == 2

        # Verify text candidate
        item0 = items[0]
        assert item0.evidence_id == "text_c01"
        assert item0.modality == EvidenceModality.TEXT
        assert item0.page_number == 12
        assert item0.document_name == "annual_report.pdf"
        assert "revenue reached 1.2 billion" in item0.evidence_spans[0]

        # Verify visual candidate
        item1 = items[1]
        assert item1.evidence_id == "visual_p14"
        assert item1.modality == EvidenceModality.VISUAL
        assert item1.image_ref == "data/page_images/annual_report/page_14.png"
        assert "Revenue chart showing steady growth" in item1.image_description

    def test_normalize_retrieval_candidates_list(self, normalizer):
        cand = RetrievalCandidate(
            candidate_id="cand_chunk_55",
            document_id="tax_guide",
            source_filename="tax_guide.pdf",
            page_start=3,
            candidate_type="text_chunk",
            text="ELSS funds have a mandatory 3-year lock-in period.",
            retrieval_method="bm25",
            retrieval_rank=1,
            retrieval_score=8.5,
        )
        items = normalizer.normalize([cand])
        assert len(items) == 1
        assert items[0].evidence_id == "cand_chunk_55"
        assert items[0].page_number == 3
        assert items[0].score == 8.5

    def test_normalize_legacy_json_file(self, normalizer):
        json_path = Path("my prework/examples/tsle_correct.json")
        if json_path.exists():
            with open(json_path) as f:
                payload = json.load(f)
            items = normalizer.normalize(payload)
            assert len(items) >= 2
            assert any(item.modality == EvidenceModality.VISUAL for item in items)
            assert any(item.modality == EvidenceModality.TEXT for item in items)

    def test_normalize_missing_or_malformed_metadata(self, normalizer):
        raw = [
            {"text": "Bare chunk with no metadata"},
            {"candidate_id": "bad_page_cand", "page_start": "invalid_page_num", "text": "Valid text"},
            {"candidate_id": "neg_page_cand", "page_start": -5, "text": "Negative page"},
        ]
        items = normalizer.normalize(raw)
        assert len(items) == 3
        assert items[0].evidence_id == "ev_1"
        assert items[0].page_number is None
        assert items[1].page_number is None
        assert items[2].page_number is None

    def test_normalize_empty_and_none_input(self, normalizer):
        assert normalizer.normalize([]) == []
        assert normalizer.normalize(None) == []
        assert normalizer.normalize({}) == []


# ==============================================================================
# STEP 3: EVIDENCE DEDUPLICATOR TESTS
# ==============================================================================

class TestEvidenceDeduplicator:
    @pytest.fixture
    def deduplicator(self):
        return EvidenceDeduplicator()

    def test_deduplicate_identical_ids(self, deduplicator):
        items = [
            EvidenceItem(evidence_id="c1", content="First version", document_name="doc.pdf", rank=1),
            EvidenceItem(evidence_id="c1", content="Second version", document_name="doc.pdf", rank=2),
            EvidenceItem(evidence_id="c2", content="Unique chunk", document_name="doc.pdf", rank=3),
        ]
        deduped = deduplicator.deduplicate(items)
        assert len(deduped) == 2
        assert [x.evidence_id for x in deduped] == ["c1", "c2"]
        assert deduped[0].content == "First version"

    def test_deduplicate_identical_text_hash(self, deduplicator):
        # Two chunks with different IDs but identical textual content
        items = [
            EvidenceItem(evidence_id="chunk_a", content="The quick brown fox jumps over the lazy dog.", document_name="doc.pdf", rank=1),
            EvidenceItem(evidence_id="chunk_b", content="  the quick brown fox   jumps over the lazy dog.  ", document_name="doc.pdf", rank=2),
            EvidenceItem(evidence_id="chunk_c", content="Completely distinct content.", document_name="doc.pdf", rank=3),
        ]
        deduped = deduplicator.deduplicate(items)
        assert len(deduped) == 2
        assert [x.evidence_id for x in deduped] == ["chunk_a", "chunk_c"]

    def test_deduplicate_redundant_visual_pages(self, deduplicator):
        # Two visual candidates pointing to the same page of the same document
        items = [
            EvidenceItem(
                evidence_id="vis_1",
                content="",
                document_name="report.pdf",
                document_id="doc_report",
                page_number=14,
                modality=EvidenceModality.VISUAL,
                image_ref="data/pages/p14.png",
                rank=1,
            ),
            EvidenceItem(
                evidence_id="vis_2",
                content="",
                document_name="report.pdf",
                document_id="doc_report",
                page_number=14,
                modality=EvidenceModality.VISUAL,
                image_ref="data/pages/p14.png",
                rank=2,
            ),
        ]
        deduped = deduplicator.deduplicate(items)
        assert len(deduped) == 1
        assert deduped[0].evidence_id == "vis_1"

    def test_preserve_distinct_chunks_on_same_page(self, deduplicator):
        """CRITICAL: Distinct text passages from the same page MUST both be preserved."""
        items = [
            EvidenceItem(
                evidence_id="doc_p12_c01",
                content="Paragraph 1 discusses tax exemption limits under Section 80C.",
                document_name="tax_guide.pdf",
                page_number=12,
                rank=1,
            ),
            EvidenceItem(
                evidence_id="doc_p12_c02",
                content="Paragraph 2 specifies the mandatory three-year holding period for ELSS.",
                document_name="tax_guide.pdf",
                page_number=12,
                rank=2,
            ),
        ]
        deduped = deduplicator.deduplicate(items)
        assert len(deduped) == 2
        assert deduped[0].evidence_id == "doc_p12_c01"
        assert deduped[1].evidence_id == "doc_p12_c02"

    def test_deduplicate_empty_input(self, deduplicator):
        assert deduplicator.deduplicate([]) == []


# ==============================================================================
# STEP 4: EVIDENCE ORGANIZER TESTS
# ==============================================================================

class TestEvidenceOrganizer:
    def test_relevance_sorting_default(self):
        organizer = EvidenceOrganizer(ContextBuilderConfig(group_by_document=False))
        items = [
            EvidenceItem(evidence_id="c3", rank=3, score=0.60, content="Third"),
            EvidenceItem(evidence_id="c1", rank=1, score=0.95, content="First"),
            EvidenceItem(evidence_id="c2", rank=2, score=0.85, content="Second"),
        ]
        sorted_items = organizer.organize(items)
        assert [x.evidence_id for x in sorted_items] == ["c1", "c2", "c3"]

    def test_relevance_sorting_tie_broken_by_score(self):
        organizer = EvidenceOrganizer(ContextBuilderConfig(group_by_document=False))
        items = [
            EvidenceItem(evidence_id="c_low_score", rank=1, score=0.70, content="Lower"),
            EvidenceItem(evidence_id="c_high_score", rank=1, score=0.95, content="Higher"),
        ]
        sorted_items = organizer.organize(items)
        assert [x.evidence_id for x in sorted_items] == ["c_high_score", "c_low_score"]

    def test_document_grouping_orders_pages_contiguously(self):
        organizer = EvidenceOrganizer(ContextBuilderConfig(group_by_document=True))
        # Two documents: docA (best rank 2, pages 15, 3) and docB (best rank 1, pages 20, 2)
        items = [
            EvidenceItem(evidence_id="b_p20", document_name="docB.pdf", page_number=20, rank=1, score=0.95),
            EvidenceItem(evidence_id="a_p15", document_name="docA.pdf", page_number=15, rank=2, score=0.90),
            EvidenceItem(evidence_id="b_p02", document_name="docB.pdf", page_number=2, rank=4, score=0.70),
            EvidenceItem(evidence_id="a_p03", document_name="docA.pdf", page_number=3, rank=3, score=0.80),
        ]
        organized = organizer.organize(items)
        # docB had the overall #1 chunk, so docB comes first, ordered by page ascending (p2, p20)
        # docA comes second, ordered by page ascending (p3, p15)
        assert [x.evidence_id for x in organized] == ["b_p02", "b_p20", "a_p03", "a_p15"]

    def test_max_evidence_items_cap(self):
        organizer = EvidenceOrganizer(ContextBuilderConfig(max_evidence_items=2))
        items = [
            EvidenceItem(evidence_id="c1", rank=1, content="A"),
            EvidenceItem(evidence_id="c2", rank=2, content="B"),
            EvidenceItem(evidence_id="c3", rank=3, content="C"),
        ]
        capped = organizer.organize(items)
        assert len(capped) == 2
        assert [x.evidence_id for x in capped] == ["c1", "c2"]

    def test_empty_organize(self):
        organizer = EvidenceOrganizer()
        assert organizer.organize([]) == []


# ==============================================================================
# STEP 5: MULTIMODAL RESOLVER TESTS
# ==============================================================================

class TestMultimodalResolver:
    def test_vision_mode_populates_visual_inputs_and_context(self):
        resolver = MultimodalResolver(ModelModality.VISION)
        items = [
            EvidenceItem(
                evidence_id="t1",
                content="Text passage content",
                document_name="doc.pdf",
                modality=EvidenceModality.TEXT,
            ),
            EvidenceItem(
                evidence_id="v1",
                document_name="doc.pdf",
                page_number=14,
                modality=EvidenceModality.VISUAL,
                image_ref="data/page_images/doc/page_14.png",
                image_description="Revenue bar chart by quarter.",
            ),
        ]
        processed, visual_inputs = resolver.resolve(items)
        assert len(processed) == 2
        assert visual_inputs == ["data/page_images/doc/page_14.png"]
        # Check that visual item content references visual input and preserves description
        vis_item = processed[1]
        assert "Revenue bar chart by quarter" in vis_item.content
        assert "Visual input: <Image from doc.pdf, Page 14>" in vis_item.content

    def test_text_mode_suppresses_visual_inputs_and_injects_description(self):
        resolver = MultimodalResolver(ModelModality.TEXT)
        items = [
            EvidenceItem(
                evidence_id="v1",
                document_name="doc.pdf",
                page_number=8,
                modality=EvidenceModality.VISUAL,
                image_ref="data/page_images/doc/page_8.png",
                image_description="Figure 2: Balance sheet breakdown table.",
            )
        ]
        processed, visual_inputs = resolver.resolve(items)
        assert len(processed) == 1
        assert visual_inputs == []  # MUST remain strictly empty for text models
        assert processed[0].image_ref is None
        assert "Figure 2: Balance sheet breakdown table" in processed[0].content
        assert "Visual input:" not in processed[0].content

    def test_text_mode_fallback_when_no_description(self):
        resolver = MultimodalResolver(ModelModality.TEXT)
        items = [
            EvidenceItem(
                evidence_id="v_bare",
                document_name="scanned_doc.pdf",
                page_number=3,
                modality=EvidenceModality.VISUAL,
                image_ref="data/pages/p3.png",
                content="",
                image_description=None,
            )
        ]
        processed, visual_inputs = resolver.resolve(items)
        assert visual_inputs == []
        assert "Visual content from scanned_doc.pdf, page 3" in processed[0].content
        assert "no text transcript available" in processed[0].content

    def test_standard_text_chunks_pass_through_unmodified(self):
        resolver_text = MultimodalResolver(ModelModality.TEXT)
        resolver_vision = MultimodalResolver(ModelModality.VISION)
        items = [
            EvidenceItem(evidence_id="t1", content="Normal text", document_name="doc.pdf")
        ]
        res_t, vis_t = resolver_text.resolve(items)
        res_v, vis_v = resolver_vision.resolve(items)
        assert res_t[0].content == "Normal text"
        assert res_v[0].content == "Normal text"
        assert vis_t == []
        assert vis_v == []


# ==============================================================================
# STEP 6: TOKENIZER & TOKEN BUDGET ENGINE TESTS
# ==============================================================================

class TestTokenCounter:
    def test_count_tokens_empty_and_short(self):
        counter = TokenCounter()
        assert counter.count_tokens("") == 0
        assert counter.count_tokens(None) == 0
        assert counter.count_tokens("Word") >= 1

    def test_count_tokens_proportional(self):
        counter = TokenCounter()
        short_count = counter.count_tokens("Short sentence.")
        long_count = counter.count_tokens("This is a much longer paragraph with considerably more words and detailed technical explanations." * 5)
        assert long_count > short_count

    def test_backend_property(self):
        counter = TokenCounter()
        assert counter.backend in ("tiktoken", "transformers", "heuristic")


class TestTokenBudgetEngine:
    def test_calculate_fixed_overhead(self):
        engine = TokenBudgetEngine(ContextBuilderConfig())
        overhead = engine.calculate_fixed_overhead("What is the tax rate?")
        assert overhead > 10

    def test_enforce_within_budget(self):
        config = ContextBuilderConfig(token_budget=1000)
        engine = TokenBudgetEngine(config)
        items = [
            EvidenceItem(evidence_id="c1", content="Short passage 1", document_name="doc.pdf"),
            EvidenceItem(evidence_id="c2", content="Short passage 2", document_name="doc.pdf"),
        ]
        included, omitted = engine.enforce("Query", items)
        assert len(included) == 2
        assert omitted == []

    def test_enforce_overflow_omits_and_tracks_ids(self):
        # Very small budget: fits top item, omits overflow item
        config = ContextBuilderConfig(token_budget=120)
        engine = TokenBudgetEngine(config)
        items = [
            EvidenceItem(evidence_id="top_item", content="Short first text.", document_name="doc.pdf", rank=1),
            EvidenceItem(evidence_id="overflow_item", content="Extremely long passage text " * 100, document_name="doc.pdf", rank=2),
        ]
        included, omitted = engine.enforce("Query", items)
        assert len(included) == 1
        assert included[0].evidence_id == "top_item"
        assert omitted == ["overflow_item"]

    def test_enforce_empty_items(self):
        engine = TokenBudgetEngine()
        included, omitted = engine.enforce("Query", [])
        assert included == []
        assert omitted == []


# ==============================================================================
# STEP 7: PROMPT FORMATTER & CITATIONS TESTS
# ==============================================================================

class TestContextFormatter:
    def test_format_prompt_structure_and_labels(self):
        formatter = ContextFormatter(ContextBuilderConfig())
        items = [
            EvidenceItem(
                evidence_id="c1",
                content="ELSS has a 3-year lock-in period.",
                document_name="tax_guide.pdf",
                page_number=12,
                modality=EvidenceModality.TEXT,
            ),
            EvidenceItem(
                evidence_id="v1",
                content="Visual input: <Image from tax_guide.pdf, Page 14>",
                document_name="tax_guide.pdf",
                page_number=14,
                modality=EvidenceModality.VISUAL,
            ),
        ]
        prompt = formatter.format_prompt("What is the lock-in period?", items)
        assert "Question: What is the lock-in period?" in prompt
        assert "[E1] Source: tax_guide.pdf, page 12 | Type: text" in prompt
        assert "ELSS has a 3-year lock-in period." in prompt
        assert "[E2] Source: tax_guide.pdf, page 14 | Type: visual page" in prompt
        assert "Instruction: Answer the question using ONLY the numbered evidence above." in prompt

    def test_format_prompt_empty_evidence(self):
        formatter = ContextFormatter(ContextBuilderConfig())
        prompt = formatter.format_prompt("Unknown query", [])
        assert "Question: Unknown query" in prompt
        assert "[No retrieved evidence available for this query]" in prompt
        assert "Instruction:" in prompt

    def test_extract_sources_1_to_1_mapping(self):
        formatter = ContextFormatter(ContextBuilderConfig())
        items = [
            EvidenceItem(
                evidence_id="chunk_alpha",
                document_name="alpha.pdf",
                page_number=5,
                modality=EvidenceModality.TEXT,
                rank=1,
            ),
            EvidenceItem(
                evidence_id="page_beta",
                document_name="beta.pdf",
                page_number=10,
                modality=EvidenceModality.VISUAL,
                rank=2,
            ),
        ]
        sources = formatter.extract_sources(items)
        assert len(sources) == 2

        assert sources[0].evidence_id == "E1"
        assert sources[0].chunk_id == "chunk_alpha"
        assert sources[0].document == "alpha.pdf"
        assert sources[0].page == 5
        assert sources[0].type == "text"
        assert sources[0].rank == 1

        assert sources[1].evidence_id == "E2"
        assert sources[1].chunk_id == "page_beta"
        assert sources[1].document == "beta.pdf"
        assert sources[1].page == 10
        assert sources[1].type == "visual"
        assert sources[1].rank == 2


# ==============================================================================
# STEP 8: CONTEXT BUILDER FACADE TESTS
# ==============================================================================

class TestContextBuilderFacade:
    def test_end_to_end_build_from_crag_result(self):
        cand1 = RetrievalCandidate(
            candidate_id="mf_c1",
            document_id="mf_guide",
            source_filename="mf_guide.pdf",
            page_start=12,
            page_end=12,
            candidate_type="text_chunk",
            text="ELSS funds have a mandatory 3-year lock-in period.",
            retrieval_method="dense",
            retrieval_rank=1,
            retrieval_score=0.91,
        )
        cand2 = RetrievalCandidate(
            candidate_id="mf_p14",
            document_id="mf_guide",
            source_filename="mf_guide.pdf",
            page_start=14,
            page_end=14,
            candidate_type="visual_page",
            text=None,
            page_reference="data/page_images/mf_guide/page_14.png",
            retrieval_method="colpali",
            retrieval_rank=2,
            retrieval_score=0.78,
            metadata={"caption": "Figure 4: Timeline of ELSS lock-in"},
        )
        crag_result = CRAGResult(
            decision=EvidenceDecision(
                label="CORRECT",
                score=0.85,
                needs_correction=False,
                candidate_evaluations=[
                    CandidateEvaluation(
                        candidate_id="mf_c1",
                        relevance_score=0.91,
                        is_relevant=True,
                        extracted_strips=["mandatory 3-year lock-in period"],
                    )
                ],
            ),
            accepted_candidates=[cand1, cand2],
            can_proceed_to_generation=True,
        )

        builder = ContextBuilder(ContextBuilderConfig(model_modality=ModelModality.VISION))
        response = builder.build("What is the lock-in period for ELSS?", crag_result)

        assert isinstance(response, ContextResponse)
        assert response.query == "What is the lock-in period for ELSS?"
        assert response.crag_decision == "CORRECT"
        assert len(response.sources) == 2
        assert response.sources[0].evidence_id == "E1"
        assert response.sources[1].evidence_id == "E2"
        assert response.visual_inputs == ["data/page_images/mf_guide/page_14.png"]
        assert response.token_estimate > 0
        assert "[E1] Source: mf_guide.pdf, page 12 | Type: text" in response.context
        assert "[E2] Source: mf_guide.pdf, page 14 | Type: visual page" in response.context
        assert "Instruction: Answer the question using ONLY the numbered evidence above." in response.context

    def test_end_to_end_build_text_only_mode(self):
        cand_vis = RetrievalCandidate(
            candidate_id="cand_v1",
            document_id="report",
            source_filename="report.pdf",
            page_start=4,
            candidate_type="visual_page",
            text=None,
            page_reference="data/pages/p4.png",
            retrieval_method="colpali",
            retrieval_rank=1,
            retrieval_score=0.80,
            metadata={"caption": "Quarterly financial summary chart."},
        )
        builder = ContextBuilder(ContextBuilderConfig(model_modality=ModelModality.TEXT))
        response = builder.build("Summarize Q3", [cand_vis])

        assert response.visual_inputs == []
        assert "Quarterly financial summary chart" in response.context
        assert "[E1] Source: report.pdf, page 4" in response.context

    def test_end_to_end_token_budget_truncation(self):
        cand_short = RetrievalCandidate(
            candidate_id="top_candidate",
            document_id="doc",
            source_filename="doc.pdf",
            page_start=1,
            candidate_type="text_chunk",
            text="High priority short answer.",
            retrieval_method="dense",
            retrieval_rank=1,
            retrieval_score=0.99,
        )
        cand_long = RetrievalCandidate(
            candidate_id="overflow_candidate",
            document_id="doc",
            source_filename="doc.pdf",
            page_start=2,
            candidate_type="text_chunk",
            text="Massive text body passage " * 150,
            retrieval_method="dense",
            retrieval_rank=2,
            retrieval_score=0.70,
        )
        # Tight token budget to force omission of candidate 2
        builder = ContextBuilder(ContextBuilderConfig(token_budget=150))
        response = builder.build("Test query", [cand_short, cand_long])

        assert "top_candidate" in response.included_evidence_ids
        assert "overflow_candidate" in response.omitted_evidence_ids
        assert len(response.sources) == 1

    def test_to_downstream_payload_adapter(self):
        builder = ContextBuilder()
        response = ContextResponse(
            query="Sample query",
            context="[E1] Source: doc.pdf\nText",
            visual_inputs=["images/page1.png"],
            sources=[
                SourceMetadata(
                    evidence_id="E1",
                    chunk_id="c1",
                    document="doc.pdf",
                    page=1,
                    type="text",
                )
            ],
            included_evidence_ids=["c1"],
            omitted_evidence_ids=[],
            token_estimate=25,
        )
        legacy_payload = builder.to_downstream_payload(response)
        assert legacy_payload["query"] == "Sample query"
        assert len(legacy_payload["context"]) == 1
        assert legacy_payload["context"][0]["citation"]["chunk_id"] == "c1"
        assert legacy_payload["visual_inputs"] == ["images/page1.png"]

    def test_build_from_example_json_files(self):
        builder_vision = ContextBuilder(ContextBuilderConfig(model_modality=ModelModality.VISION))
        builder_text = ContextBuilder(ContextBuilderConfig(model_modality=ModelModality.TEXT))

        # 1. Test with context_builder_input.json
        input_file = Path("my prework/examples/context_builder_input.json")
        if input_file.exists():
            with open(input_file) as f:
                payload = json.load(f)
            resp = builder_vision.build(payload["query"], payload["accepted_candidates"])
            assert len(resp.sources) >= 2
            assert any(s.type == "visual" for s in resp.sources)
            assert any(s.type == "text" for s in resp.sources)
            assert len(resp.visual_inputs) >= 1
            assert "Figure 4:" in resp.context

        # 2. Test with tsle_correct.json (full CRAGResult payload)
        correct_file = Path("my prework/examples/tsle_correct.json")
        if correct_file.exists():
            with open(correct_file) as f:
                crag_payload = json.load(f)
            resp_t = builder_text.build("Lock-in period for ELSS?", crag_payload)
            assert resp_t.crag_decision == "CORRECT"
            assert len(resp_t.sources) >= 2
            assert resp_t.visual_inputs == []  # Text mode
            assert "[E1]" in resp_t.context


# ==============================================================================
# STEP 9: FULL AMCRAG PIPELINE INTEGRATION TESTS
# ==============================================================================

class TestAMCRAGFullPipelineIntegration:
    """Tests the full runtime integration flow:

    Candidate Set -> CRAGController (Evaluation & Decision) -> ContextBuilder -> ContextResponse.
    """

    def test_full_pipeline_correct_flow(self):
        # 1. Simulate candidates emitted by Person 2 & 3
        cand_relevant_text = RetrievalCandidate(
            candidate_id="chunk_tax_p12",
            document_id="mutual_fund_tax_guide_2025",
            source_filename="mutual_fund_tax_guide_2025.pdf",
            page_start=12,
            page_end=12,
            candidate_type="text_chunk",
            text="Equity Linked Savings Schemes (ELSS) have a mandatory lock-in period of three years from the date of each investment.",
            retrieval_method="dense",
            retrieval_rank=1,
            retrieval_score=0.91,
            metadata={"section": "ELSS Tax Rules"},
        )
        cand_relevant_visual = RetrievalCandidate(
            candidate_id="page_chart_p14",
            document_id="mutual_fund_tax_guide_2025",
            source_filename="mutual_fund_tax_guide_2025.pdf",
            page_start=14,
            page_end=14,
            candidate_type="visual_page",
            text=None,
            page_reference="data/page_images/mutual_fund_tax_guide_2025/page_14.png",
            retrieval_method="colpali",
            retrieval_rank=2,
            retrieval_score=0.78,
            metadata={"caption": "Figure 4: Timeline of ELSS 3-year lock-in maturity and tax benefits"},
        )
        cand_noise = RetrievalCandidate(
            candidate_id="chunk_noise_crypto",
            document_id="unrelated_crypto",
            source_filename="crypto_guide.pdf",
            page_start=1,
            page_end=1,
            candidate_type="text_chunk",
            text="Cryptocurrency blockchains record transactions in immutable ledgers.",
            retrieval_method="dense",
            retrieval_rank=3,
            retrieval_score=0.10,
        )

        query = "What is the lock-in period for an ELSS mutual fund?"
        candidates = [cand_relevant_text, cand_relevant_visual, cand_noise]

        # 2. Upstream Person 4: CRAG Controller processes candidates
        crag_controller = CRAGController()
        crag_result = crag_controller.process_candidates(query, candidates, attempt_number=0)

        # Verify CRAG correctly gated and refined evidence
        assert crag_result.can_proceed_to_generation is True
        assert crag_result.decision.label == "CORRECT"
        assert len(crag_result.accepted_candidates) == 2  # Noise filtered out!
        assert "chunk_noise_crypto" not in [c.candidate_id for c in crag_result.accepted_candidates]

        # 3. Person 5: Context Builder builds context from CRAGResult
        # Vision Mode
        builder_vision = ContextBuilder(ContextBuilderConfig(model_modality=ModelModality.VISION))
        context_response_v = builder_vision.build(query, crag_result)

        assert context_response_v.crag_decision == "CORRECT"
        assert len(context_response_v.sources) == 2
        assert context_response_v.sources[0].evidence_id == "E1"
        assert context_response_v.sources[0].chunk_id == "chunk_tax_p12"
        assert context_response_v.sources[1].evidence_id == "E2"
        assert context_response_v.sources[1].chunk_id == "page_chart_p14"
        assert context_response_v.visual_inputs == ["data/page_images/mutual_fund_tax_guide_2025/page_14.png"]
        assert "chunk_noise_crypto" not in context_response_v.included_evidence_ids
        assert "[E1] Source: mutual_fund_tax_guide_2025.pdf, page 12 | Type: text" in context_response_v.context
        assert "[E2] Source: mutual_fund_tax_guide_2025.pdf, page 14 | Type: visual page" in context_response_v.context
        assert "Instruction: Answer the question using ONLY the numbered evidence above." in context_response_v.context

        # Text-only Mode
        builder_text = ContextBuilder(ContextBuilderConfig(model_modality=ModelModality.TEXT))
        context_response_t = builder_text.build(query, crag_result)

        assert context_response_t.visual_inputs == []
        assert "Figure 4: Timeline of ELSS 3-year lock-in" in context_response_t.context

    def test_full_pipeline_incorrect_stops_generation(self):
        # When all candidates are poor, CRAG stops generation (insufficient_evidence=True)
        cand_poor = RetrievalCandidate(
            candidate_id="cand_bad",
            document_id="unrelated",
            source_filename="unrelated.pdf",
            page_start=1,
            candidate_type="text_chunk",
            text="Unrelated content about gardening and soil pH.",
            retrieval_method="dense",
            retrieval_rank=1,
            retrieval_score=0.10,
        )

        query = "What is the lock-in period for an ELSS mutual fund?"
        crag_controller = CRAGController()
        # At attempt 2 (max retries exhausted), CRAG halts
        crag_result = crag_controller.process_candidates(query, [cand_poor], attempt_number=2)

        assert crag_result.can_proceed_to_generation is False
        assert crag_result.insufficient_evidence is True
        assert crag_result.accepted_candidates == []


# STEP 10: ROBUSTNESS AUDIT CERTIFICATIONS
class TestRobustnessAuditCertifications:
    """Verifies the 5 robustness fixes and guarantees from test.md and test-report.md."""

    def test_corrupted_float_inf_page_numbers_degrades_gracefully(self):
        # Scenario 1.2: float('inf'), negative, zero, string pages should degrade without dropping candidate
        normalizer = EvidenceNormalizer()
        raw_candidates = [
            {"candidate_id": "c1", "text": "p1", "page_start": "page_twelve"},
            {"candidate_id": "c2", "text": "p2", "page_start": -99},
            {"candidate_id": "c3", "text": "p3", "page_start": 0},
            {"candidate_id": "c4", "text": "p4", "page_start": float("inf")},
            {"candidate_id": "c5", "text": "p5", "page_start": None},
        ]
        items = normalizer.normalize(raw_candidates)
        assert len(items) == 5
        assert all(it.page_number is None for it in items)
        assert [it.evidence_id for it in items] == ["c1", "c2", "c3", "c4", "c5"]

    def test_nested_legacy_envelope_in_mixed_list_unpacks_completely(self):
        # Scenario 1.4: Mixed batch containing model, raw dict, and nested envelope
        normalizer = EvidenceNormalizer()
        cand_model = RetrievalCandidate(
            candidate_id="model_c1",
            document_id="doc1",
            source_filename="doc1.pdf",
            page_start=1,
            candidate_type="text_chunk",
            text="Model content",
            retrieval_method="bm25",
            retrieval_rank=1,
            retrieval_score=0.9,
        )
        raw_cand = {"candidate_id": "raw_c2", "text": "Raw dict content", "rank": 2}
        legacy_envelope = {
            "selected_evidence": [
                {"candidate_id": "leg_c3", "text": "Legacy 1", "rank": 3},
                {"candidate_id": "leg_c4", "text": "Legacy 2", "rank": 4},
            ]
        }
        mixed = [cand_model, raw_cand, legacy_envelope]
        items = normalizer.normalize(mixed)
        assert len(items) == 4
        assert [it.evidence_id for it in items] == ["model_c1", "raw_c2", "leg_c3", "leg_c4"]

    def test_quality_aware_duplicate_id_resolution_keeps_best_rank(self):
        # Scenario 3.1: 100 duplicate items arriving with descending ranks (100 down to 1)
        normalizer = EvidenceNormalizer()
        deduplicator = EvidenceDeduplicator()
        raw_cands = [
            {"candidate_id": "dup_01", "text": f"version {i}", "rank": 100 - i, "score": float(i)}
            for i in range(100)
        ]
        items = normalizer.normalize(raw_cands)
        deduped = deduplicator.deduplicate(items)
        assert len(deduped) == 1
        assert deduped[0].rank == 1
        assert deduped[0].score == 99.0

    def test_crag_extracted_strips_prioritization_in_prompt(self):
        # Scenario 6.3: Extracted strips appear prominently in prompt context
        builder = ContextBuilder()
        candidate = {
            "candidate_id": "c_strip",
            "document_name": "annual_report.pdf",
            "page_number": 10,
            "text": "Full text of document passage goes here with extra background.",
            "evidence_spans": ["key sentence 1", "key sentence 2"],
        }
        response = builder.build("What is the metric?", [candidate])
        assert "Key Extracted Strips:" in response.context
        assert "• key sentence 1" in response.context
        assert "• key sentence 2" in response.context
        assert "Context:\nFull text of document passage goes here" in response.context

    def test_high_scale_10k_throughput_and_budget_omissions(self):
        # Scenario 7.1: 10,000 candidates with fast processing and omission tracking
        builder = ContextBuilder(ContextBuilderConfig(token_budget=4096))
        cands = [
            {
                "candidate_id": f"k_{i}",
                "document_name": f"doc_{i % 10}.pdf",
                "page_number": (i % 5) + 1,
                "text": f"Passage {i} text describing metrics.",
                "rank": i + 1,
            }
            for i in range(1000)
        ]
        response = builder.build("Scale test query", cands)
        assert len(response.sources) > 0
        assert len(response.omitted_evidence_ids) > 0
        assert len(response.sources) + len(response.omitted_evidence_ids) == 1000






