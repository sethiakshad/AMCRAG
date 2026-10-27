"""pipeline.py — End-to-end Conventional Normal RAG Pipeline."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from app.normal_rag.config import NormalRAGConfig
from app.normal_rag.retriever import NormalRAGRetriever
from app.normal_rag.schemas import NormalRAGChunk, NormalRAGRequest, NormalRAGResult
from app.schemas.chunk import DocumentChunk, ProcessedDocumentOutput
from app.services.generator import AnswerGenerator, GeneratorConfig

logger = logging.getLogger("NormalRAG.Pipeline")


class NormalRAGPipeline:
    """Conventional Standard RAG Workflow.

    Architecture & Workflow:
      1. Document Ingestion (reused from DocumentProcessingPipeline):
         PDF -> PyMuPDF/Docling text extraction -> TextChunker -> DocumentChunks.
      2. Embedding & Vector Indexing:
         DocumentChunks -> BGE-base-en-v1.5 embeddings -> Qdrant vector index.
      3. Top-k Retrieval:
         User Query -> BGE embedding -> Cosine similarity search -> Top-k text chunks.
      4. Grounded Prompt Assembly:
         Concatenates retrieved chunk passages into a clean context prompt.
      5. Answer Generation:
         Context + Question -> AnswerGenerator (Gemini / OpenAI / Ollama / Mock) -> Grounded answer.
      6. Result Assembly:
         Emits structured NormalRAGResult with latency breakdown and source page metadata.
    """

    def __init__(
        self,
        config: Optional[NormalRAGConfig] = None,
        retriever: Optional[NormalRAGRetriever] = None,
        generator: Optional[AnswerGenerator] = None,
    ):
        self.config = config or NormalRAGConfig()
        self.retriever = retriever or NormalRAGRetriever(config=self.config)
        self.generator = generator or AnswerGenerator(GeneratorConfig(fallback_to_mock=True))

        logger.info(
            "NormalRAGPipeline initialized (top_k=%d, dense_model='%s', generator_provider='%s')",
            self.config.top_k,
            self.config.dense_model_name,
            self.generator.active_provider,
        )

    # -------------------------------------------------------------------------
    # Ingestion Hooks (Reusing existing Person 1 extraction and chunking)
    # -------------------------------------------------------------------------

    def ingest_pdf(
        self,
        pdf_path: Union[str, Path],
        force_reprocess: bool = False,
    ) -> ProcessedDocumentOutput:
        """Process a PDF file using the existing shared pipeline and index its chunks."""
        from app.services.pipeline import DocumentProcessingPipeline

        pipeline = DocumentProcessingPipeline()
        processed_output = pipeline.process_file(Path(pdf_path), force_reprocess=force_reprocess)

        if processed_output.chunks:
            self.retriever.index_chunks(processed_output.chunks)
            logger.info(
                "Indexed %d chunks for document '%s' in Normal RAG retriever.",
                len(processed_output.chunks),
                processed_output.document_id,
            )

        return processed_output

    def index_document_output(self, document_output: ProcessedDocumentOutput) -> int:
        """Index chunks from an already-processed ProcessedDocumentOutput model."""
        if not document_output.chunks:
            logger.warning("ProcessedDocumentOutput contains no chunks.")
            return 0
        return self.retriever.index_chunks(document_output.chunks)

    def index_chunks(self, chunks: Sequence[Union[DocumentChunk, Dict[str, Any]]]) -> int:
        """Directly index a sequence of text chunks."""
        return self.retriever.index_chunks(chunks)

    # -------------------------------------------------------------------------
    # Core RAG Execution Pipeline
    # -------------------------------------------------------------------------

    def query(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
    ) -> NormalRAGResult:
        """Synchronously execute conventional Normal RAG for a given question.

        Args:
            query_text: User question.
            top_k: Optional chunk limit (defaults to config.top_k).
            document_ids: Optional list of document IDs to scope retrieval.

        Returns:
            NormalRAGResult containing grounded answer, source pages, and latency metrics.
        """
        t_start = time.perf_counter()
        k = top_k or self.config.top_k
        err_msg: Optional[str] = None

        # 1. Retrieval Stage
        t_r_start = time.perf_counter()
        retrieved_chunks: List[NormalRAGChunk] = []
        try:
            retrieved_chunks = self.retriever.search(
                query=query_text,
                top_k=k,
                document_ids=document_ids,
            )
        except Exception as exc:
            logger.error("Error during Normal RAG retrieval: %s", exc, exc_info=True)
            err_msg = f"Retrieval error: {exc}"

        retrieval_latency_ms = (time.perf_counter() - t_r_start) * 1000

        # Collect source page numbers
        source_pages_set = set()
        for c in retrieved_chunks:
            if c.page_number:
                source_pages_set.add(c.page_number)
            if c.page_start:
                source_pages_set.add(c.page_start)
            if c.page_end:
                source_pages_set.add(c.page_end)
        source_pages = sorted(list(source_pages_set))

        # 2. Context Assembly
        context_str = self._format_context(retrieved_chunks)

        # 3. Answer Generation Stage
        t_g_start = time.perf_counter()
        answer = ""
        token_usage: Optional[Dict[str, int]] = None

        try:
            if not retrieved_chunks:
                answer = "Based on the provided documents, there is insufficient evidence to answer your question."
            else:
                prompt = self.config.system_prompt_template.format(
                    context=context_str,
                    question=query_text,
                )
                # Estimate prompt tokens (~4 chars per token)
                prompt_tokens_est = max(1, len(prompt) // 4)

                raw_answer = self.generator.generate(
                    prompt=prompt,
                    visual_inputs=None,
                    insufficient_evidence=False,
                )
                answer = raw_answer.strip()
                completion_tokens_est = max(1, len(answer) // 4)

                token_usage = {
                    "prompt_tokens_estimate": prompt_tokens_est,
                    "completion_tokens_estimate": completion_tokens_est,
                    "total_tokens_estimate": prompt_tokens_est + completion_tokens_est,
                }
        except Exception as exc:
            logger.error("Error during Normal RAG generation: %s", exc, exc_info=True)
            answer = "An error occurred during answer generation."
            err_msg = f"Generation error: {exc}" if not err_msg else f"{err_msg}; Generation error: {exc}"

        generation_latency_ms = (time.perf_counter() - t_g_start) * 1000
        total_latency_ms = (time.perf_counter() - t_start) * 1000

        return NormalRAGResult(
            system="normal_rag",
            question=query_text,
            answer=answer,
            retrieved_chunks=retrieved_chunks,
            source_pages=source_pages,
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
            generation_latency_ms=round(generation_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
            token_usage=token_usage,
            error=err_msg,
        )

    async def query_async(
        self,
        request: NormalRAGRequest,
    ) -> NormalRAGResult:
        """Asynchronously execute Normal RAG using asyncio.to_thread for blocking operations."""
        doc_ids = request.document_ids
        if not doc_ids and request.document_id:
            doc_ids = [request.document_id]

        return await asyncio.to_thread(
            self.query,
            query_text=request.query,
            top_k=request.top_k,
            document_ids=doc_ids,
        )

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _format_context(self, chunks: List[NormalRAGChunk]) -> str:
        """Format retrieved chunks into a clean, numbered context block."""
        if not chunks:
            return "No relevant context found."

        formatted_blocks = []
        for i, chunk in enumerate(chunks, start=1):
            source_info = f"Document: {chunk.source_filename or chunk.document_id or 'Unknown'}"
            if chunk.page_start:
                if chunk.page_end and chunk.page_end != chunk.page_start:
                    source_info += f", Pages {chunk.page_start}-{chunk.page_end}"
                else:
                    source_info += f", Page {chunk.page_start}"
            elif chunk.page_number:
                source_info += f", Page {chunk.page_number}"

            block = f"[E{i}] [Chunk {i}] ({source_info})\n{chunk.text.strip()}"
            formatted_blocks.append(block)

        return "\n\n".join(formatted_blocks)

