"""test_api_schemas_and_generator.py — Unit Tests for Milestone 1 & 2.

Tests:
  - Milestone 1: Pydantic API schemas (QueryRequest, QueryResponse, DocumentUploadResponse,
    HealthResponse, validation rules, non-empty query enforcement).
  - Milestone 2: AnswerGenerator service (Gemini/OpenAI routing, fallback to mock,
    insufficient evidence safe-halt, streaming token generator).
"""

import asyncio
import pytest

from app.context_builder.schemas import ModelModality, SourceMetadata
from app.schemas.api import (
    DeleteResponse,
    DocumentDetailResponse,
    DocumentSummary,
    DocumentUploadResponse,
    HealthResponse,
    LatencyBreakdown,
    QueryRequest,
    QueryResponse,
)
from app.services.generator import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    AnswerGenerator,
    GeneratorConfig,
)


# =============================================================================
# MILESTONE 1: API SCHEMAS & CONTRACT TESTS
# =============================================================================

class TestAPISchemas:
    """Validates Milestone 1 request/response Pydantic models and constraints."""

    def test_query_request_valid(self):
        req = QueryRequest(
            query="What is the ELSS lock-in period?",
            model_modality=ModelModality.TEXT,
            token_budget=4096,
            top_k=5,
            enable_crag=True,
            document_ids=["doc_123"],
        )
        assert req.query == "What is the ELSS lock-in period?"
        assert req.token_budget == 4096
        assert req.top_k == 5
        assert req.document_ids == ["doc_123"]

    def test_query_request_whitespace_rejection(self):
        with pytest.raises(ValueError, match="Query cannot be empty or contain only whitespace"):
            QueryRequest(query="    \n\t  ")

    def test_query_request_bounds(self):
        # Budget below 500
        with pytest.raises(ValueError):
            QueryRequest(query="valid query", token_budget=100)

        # top_k below 1
        with pytest.raises(ValueError):
            QueryRequest(query="valid query", top_k=0)

        # top_k above 50
        with pytest.raises(ValueError):
            QueryRequest(query="valid query", top_k=100)

    def test_query_response_serialization(self):
        latency = LatencyBreakdown(
            query_analysis_ms=10.5,
            retrieval_ms=120.0,
            crag_evaluation_ms=45.2,
            context_building_ms=5.1,
            generation_ms=300.0,
            total_ms=480.8,
        )
        sources = [
            SourceMetadata(
                evidence_id="E1",
                chunk_id="chunk_1",
                document="guide.pdf",
                page=12,
                type="text",
                rank=1,
            )
        ]
        resp = QueryResponse(
            query="What is the lock-in?",
            answer="The lock-in is 3 years [E1].",
            sources=sources,
            visual_inputs=[],
            crag_decision="CORRECT",
            insufficient_evidence=False,
            retrieval_attempts=1,
            latency=latency,
        )
        data = resp.model_dump()
        assert data["query"] == "What is the lock-in?"
        assert data["sources"][0]["evidence_id"] == "E1"
        assert data["latency"]["total_ms"] == 480.8

    def test_document_upload_response(self):
        resp = DocumentUploadResponse(
            document_id="doc_xyz",
            filename="report.pdf",
            status="indexed",
            page_count=10,
            chunk_count=25,
            image_count=10,
            message="Document successfully indexed",
        )
        assert resp.status == "indexed"
        assert resp.chunk_count == 25

    def test_health_response(self):
        health = HealthResponse(
            status="healthy",
            version="1.0.0",
            components={"vector_db": True, "bm25": True, "crag": True, "llm": True},
            uptime_seconds=120.5,
        )
        assert health.status == "healthy"
        assert health.components["vector_db"] is True


# =============================================================================
# MILESTONE 2: ANSWER GENERATION LLM SERVICE TESTS
# =============================================================================

class TestAnswerGenerator:
    """Validates Milestone 2 AnswerGenerator multi-provider routing and fallbacks."""

    def test_mock_generator_grounded_answer(self):
        gen = AnswerGenerator(GeneratorConfig(provider="mock"))
        assert gen.active_provider == "mock"

        prompt = (
            "Question: What is the lock-in period for ELSS mutual funds?\n\n"
            "[E1] Source: mf_guide.pdf, page 12 | Type: text\n"
            "ELSS funds have a mandatory 3-year lock-in period.\n\n"
            "[E2] Source: mf_guide.pdf, page 14 | Type: text\n"
            "Investors cannot withdraw before 36 months.\n\n"
            "Instruction: Answer using ONLY the numbered evidence above. Cite [E1], [E2]."
        )
        answer = gen.generate(prompt)
        assert "[E1]" in answer
        assert "What is the lock-in period for ELSS mutual funds?" in answer

    def test_insufficient_evidence_safe_halt(self):
        gen = AnswerGenerator(GeneratorConfig(provider="mock"))
        prompt = "Question: What is the meaning of quantum superposition?\n[No retrieved evidence available]"

        # Direct insufficient flag
        ans1 = gen.generate(prompt, insufficient_evidence=True)
        assert ans1 == INSUFFICIENT_EVIDENCE_ANSWER

        # Empty prompt or no evidence marker
        ans2 = gen.generate(prompt)
        assert ans2 == INSUFFICIENT_EVIDENCE_ANSWER

    def test_visual_input_mention_in_mock(self):
        gen = AnswerGenerator(GeneratorConfig(provider="mock"))
        prompt = (
            "Question: What is the trend in revenue?\n\n"
            "[E1] Source: financials.pdf, page 5 | Type: visual page\n"
            "Visual input: <Image from financials.pdf, Page 5>"
        )
        answer = gen.generate(prompt, visual_inputs=["data/page_images/doc/page_5.png"])
        assert "visual and textual evidence" in answer
        assert "[E1]" in answer

    @pytest.mark.anyio
    async def test_streaming_generator(self):
        gen = AnswerGenerator(GeneratorConfig(provider="mock"))
        prompt = (
            "Question: What is the tax deduction under Section 80C?\n\n"
            "[E1] Source: tax.pdf, page 1 | Type: text\n"
            "Section 80C allows deductions up to 1.5 lakh INR."
        )
        tokens = []
        async for token in gen.generate_stream(prompt):
            tokens.append(token)

        full_streamed = "".join(tokens)
        assert "[E1]" in full_streamed
        assert len(tokens) > 1

    def test_fallback_when_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Configured for gemini but no key provided -> falls back to mock
        gen = AnswerGenerator(GeneratorConfig(provider="gemini", fallback_to_mock=True))
        assert gen.active_provider == "mock"
        ans = gen.generate("Question: Test?\n[E1] Source: doc, p1\nData")
        assert "[E1]" in ans
