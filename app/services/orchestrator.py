"""orchestrator.py — End-to-End RAG Pipeline Orchestrator.

Coordinates user query analysis, adaptive retrieval (Hybrid Text + ColPali Visual),
CRAG quality evaluation with bounded reformulation retry loops, prompt grounding
via ContextBuilder, and answer generation via AnswerGenerator.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Set, Tuple

from pydantic import BaseModel, Field

from app.context_builder import ContextBuilder, ContextBuilderConfig
from app.context_builder.schemas import ContextResponse, ModelModality, SourceMetadata
from app.crag import CRAGController
from app.schemas.api import LatencyBreakdown, QueryRequest, QueryResponse
from app.schemas.crag import CRAGResult, EvidenceDecision
from app.schemas.retrieval import RetrievalCandidate
from app.services.generator import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    AnswerGenerator,
    GeneratorConfig,
)

logger = logging.getLogger("AMCRAG.Orchestrator")


class OrchestratorConfig(BaseModel):
    """Configuration options for the RAG Orchestrator pipeline."""

    max_crag_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum query reformulation retries on poor evidence",
    )
    default_top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Default number of evidence passages to retrieve",
    )
    default_token_budget: int = Field(
        default=4096,
        ge=500,
        le=128000,
        description="Default token budget for prompt context",
    )
    enable_crag: bool = Field(
        default=True,
        description="Whether to run CRAG evaluation and correction by default",
    )
    crag_timeout_seconds: float = Field(
        default=5.0,
        ge=0.5,
        le=30.0,
        description="Timeout in seconds for CRAG evaluation before heuristic fallback",
    )
    visual_intent_keywords: List[str] = Field(
        default_factory=lambda: [
            "chart", "graph", "trend", "figure", "table", "diagram",
            "visual", "plot", "timeline", "image", "map", "illustration"
        ],
        description="Keywords indicating visual / multimodal retrieval intent",
    )

    model_config = {"extra": "allow"}


class RAGOrchestrator:
    """Central pipeline coordinator uniting Person 1–4 modules and Person 5 generator."""

    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        retriever: Optional[Any] = None,
        visual_bridge: Optional[Any] = None,
        crag_controller: Optional[CRAGController] = None,
        context_builder: Optional[ContextBuilder] = None,
        generator: Optional[AnswerGenerator] = None,
    ):
        self.config = config or OrchestratorConfig()
        self.retriever = retriever
        self.visual_bridge = visual_bridge
        self.crag_controller = crag_controller or CRAGController()
        self.context_builder = context_builder or ContextBuilder(
            ContextBuilderConfig(token_budget=self.config.default_token_budget)
        )
        self.generator = generator or AnswerGenerator(GeneratorConfig(fallback_to_mock=True))

        logger.info(
            "Initialized RAGOrchestrator (max_retries=%d, enable_crag=%s)",
            self.config.max_crag_retries,
            self.config.enable_crag,
        )

    # -------------------------------------------------------------------------
    # Intent Analysis & Routing
    # -------------------------------------------------------------------------

    def analyze_query_intent(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
    ) -> ModelModality:
        """Classify query to determine if vision-capable retrieval/model is needed.

        Args:
            query: Natural language query string.
            document_ids: Optional list of document IDs to inspect for document-driven modality.

        Returns:
            ModelModality.VISION if query requests charts, graphs, or visual artifacts,
            or if target documents are scanned / visual-only, otherwise ModelModality.TEXT.
        """
        lower_q = query.lower()
        for kw in self.config.visual_intent_keywords:
            if kw in lower_q:
                logger.debug("Visual keyword '%s' matched; routing to VISION modality.", kw)
                return ModelModality.VISION

        # Auto-mode: inspect document modality when target documents are selected
        if document_ids:
            try:
                import json
                from app.config import default_settings
                processed_dir = default_settings.get_processed_path()
                if processed_dir.exists():
                    for did in document_ids:
                        doc_path = processed_dir / f"{did}.json"
                        if doc_path.exists():
                            try:
                                d = json.loads(doc_path.read_text(encoding="utf-8"))
                                is_scanned = d.get("is_scanned", False)
                                ocr_needed = d.get("ocr_needed", False)
                                chunk_count = d.get("total_chunks", len(d.get("chunks", [])))
                                zero_text = (
                                    d.get("zero_text_fallback", False)
                                    or d.get("zero_text_chunks", False)
                                    or d.get("zero_embeddings", False)
                                    or d.get("pipeline_modality") == "visual_only"
                                )
                                rendered_pages = d.get("rendered_pages", [])
                                if is_scanned or ocr_needed or zero_text or (chunk_count == 0 and len(rendered_pages) > 0):
                                    logger.info(
                                        "Auto-mode routing: target document '%s' has 0 text chunks/embeddings or is visual-only (chunks=%d, pages=%d). Selecting VISION modality.",
                                        did,
                                        chunk_count,
                                        len(rendered_pages),
                                    )
                                    return ModelModality.VISION
                            except Exception as exc:
                                logger.debug("Could not inspect document '%s': %s", did, exc)
            except Exception as exc:
                logger.debug("Document-driven auto-mode check skipped: %s", exc)

        return ModelModality.TEXT

    # -------------------------------------------------------------------------
    # Core Synchronous / Async Execution Pipeline
    # -------------------------------------------------------------------------

    async def query(self, request: QueryRequest) -> QueryResponse:
        """Execute the end-to-end RAG workflow for an incoming user query.

        Workflow:
          1. Analyze query intent and resolve target model modality.
          2. Execute multi-store retrieval (Dense + Sparse Hybrid, optional ColPali).
          3. Evaluate evidence via CRAG with bounded reformulation loop.
          4. Build grounded prompt and structured citations via ContextBuilder.
          5. Generate answer using AnswerGenerator LLM.
          6. Assemble structured QueryResponse with granular latency breakdown.

        Args:
            request: Validated QueryRequest instance.

        Returns:
            QueryResponse contract instance.
        """
        t_start = time.perf_counter()

        # Step 1: Query Analysis & Routing
        t_stage_start = time.perf_counter()
        target_modality = request.model_modality or self.analyze_query_intent(
            request.query, request.document_ids
        )
        # If client explicitly specifies text but query is visual, respect client choice
        if request.model_modality is not None:
            target_modality = request.model_modality
        analysis_ms = (time.perf_counter() - t_stage_start) * 1000

        # Step 2: Retrieval & CRAG Evaluation Loop
        crag_result, attempts, t_retrieval_total, t_crag_total = await self._run_retrieval_and_crag(
            query=request.query,
            target_modality=target_modality,
            top_k=request.top_k or self.config.default_top_k,
            enable_crag=request.enable_crag and self.config.enable_crag,
            document_ids=request.document_ids,
        )

        # Step 3: Context Building & Prompt Grounding
        t_cb_start = time.perf_counter()
        has_visual_evidence = any(
            getattr(c, "modality", "") == "visual_page" or getattr(c, "candidate_type", "") == "visual_page"
            for c in (crag_result.accepted_candidates if crag_result else [])
        )
        effective_modality = ModelModality.VISION if has_visual_evidence else target_modality

        token_budget = request.token_budget or self.config.default_token_budget
        cb_config = ContextBuilderConfig(
            token_budget=token_budget,
            model_modality=effective_modality,
        )
        # Use dynamic context builder configured for request
        context_response: ContextResponse = ContextBuilder(cb_config).build(
            query=request.query,
            accepted_evidence=crag_result,
        )
        context_ms = (time.perf_counter() - t_cb_start) * 1000

        # Step 4: Answer Generation
        t_gen_start = time.perf_counter()
        if crag_result.insufficient_evidence or not context_response.sources:
            logger.info("Insufficient evidence confirmed; halting generation to prevent hallucination.")
            answer = INSUFFICIENT_EVIDENCE_ANSWER
        else:
            answer = self.generator.generate(
                prompt=context_response.context,
                visual_inputs=context_response.visual_inputs,
                insufficient_evidence=False,
            )
        generation_ms = (time.perf_counter() - t_gen_start) * 1000

        total_ms = (time.perf_counter() - t_start) * 1000

        latency = LatencyBreakdown(
            query_analysis_ms=round(analysis_ms, 2),
            retrieval_ms=round(t_retrieval_total, 2),
            crag_evaluation_ms=round(t_crag_total, 2),
            context_building_ms=round(context_ms, 2),
            generation_ms=round(generation_ms, 2),
            total_ms=round(total_ms, 2),
        )

        crag_label = None
        if crag_result and crag_result.decision:
            expl = (crag_result.decision.explanation or "").lower()
            if "fallback" not in expl and "bypass" not in expl:
                crag_label = crag_result.decision.label

        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=context_response.sources,
            visual_inputs=context_response.visual_inputs,
            crag_decision=crag_label,
            insufficient_evidence=crag_result.insufficient_evidence if crag_result else False,
            retrieval_attempts=attempts,
            latency=latency,
        )

    # -------------------------------------------------------------------------
    # CRAG Evaluation Guard & Retrieval Loop
    # -------------------------------------------------------------------------

    async def _evaluate_crag_with_timeout(
        self,
        query: str,
        candidates: List[RetrievalCandidate],
        attempt_number: int,
    ) -> CRAGResult:
        """Run CRAG candidate evaluation with a timeout guard and heuristic fallback."""
        timeout_sec = self.config.crag_timeout_seconds
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self.crag_controller.process_candidates,
                    query=query,
                    candidates=candidates,
                    attempt_number=attempt_number,
                ),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "CRAG evaluation timed out after %.1fs on attempt %d; falling back to heuristic candidate acceptance.",
                timeout_sec,
                attempt_number,
            )
        except Exception as e:
            logger.warning(
                "CRAG evaluation failed with exception on attempt %d: %s; falling back to heuristic candidate acceptance.",
                attempt_number,
                e,
            )

        # Fallback to heuristic acceptance of retrieved candidates
        fallback_decision = EvidenceDecision(
            label="CORRECT" if candidates else "INCORRECT",
            score=0.85 if candidates else 0.0,
            explanation="Heuristic fallback candidate acceptance",
            needs_correction=False,
            attempt_number=attempt_number,
        )
        return CRAGResult(
            decision=fallback_decision,
            reformulated_query=None,
            accepted_candidates=candidates,
            can_proceed_to_generation=bool(candidates),
            insufficient_evidence=not bool(candidates),
        )

    async def _run_retrieval_and_crag(
        self,
        query: str,
        target_modality: ModelModality,
        top_k: int,
        enable_crag: bool,
        document_ids: Optional[List[str]] = None,
    ) -> Tuple[CRAGResult, int, float, float]:
        """Execute bounded retrieval and CRAG evaluation with cycle detection.

        Returns:
            Tuple of (crag_result, total_attempts_executed, total_retrieval_ms, total_crag_ms)
        """
        t_retrieval_total = 0.0
        t_crag_total = 0.0

        active_query = query
        seen_queries: Set[str] = {active_query.lower().strip()}

        candidates: List[RetrievalCandidate] = []
        crag_result: Optional[CRAGResult] = None
        attempt = 0
        max_attempts = self.config.max_crag_retries if enable_crag else 0

        while attempt <= max_attempts:
            # Fetch retrieval candidates
            t_r_start = time.perf_counter()
            candidates = self._fetch_candidates(
                query=active_query,
                top_k=top_k,
                modality=target_modality,
                document_ids=document_ids,
            )
            t_retrieval_total += (time.perf_counter() - t_r_start) * 1000

            # Evaluate evidence with CRAG
            t_c_start = time.perf_counter()
            if enable_crag:
                crag_result = await self._evaluate_crag_with_timeout(
                    query=active_query,
                    candidates=candidates,
                    attempt_number=attempt,
                )
            else:
                bypass_decision = EvidenceDecision(
                    label="CORRECT" if candidates else "INCORRECT",
                    score=1.0 if candidates else 0.0,
                    explanation="CRAG bypassed by request",
                    needs_correction=False,
                    attempt_number=attempt,
                )
                crag_result = CRAGResult(
                    decision=bypass_decision,
                    reformulated_query=None,
                    accepted_candidates=candidates,
                    can_proceed_to_generation=bool(candidates),
                    insufficient_evidence=not bool(candidates),
                )
            t_crag_total += (time.perf_counter() - t_c_start) * 1000

            # Check outcome
            if crag_result.can_proceed_to_generation:
                logger.info(
                    "CRAG approved generation on attempt %d (accepted=%d, decision=%s)",
                    attempt,
                    len(crag_result.accepted_candidates),
                    crag_result.decision.label if crag_result.decision else "BYPASSED",
                )
                break

            # If CRAG requested query reformulation and retries remain
            if crag_result.decision and crag_result.decision.needs_correction and attempt < max_attempts:
                next_query = crag_result.reformulated_query
                # Cycle / loop detection
                if not next_query or next_query.lower().strip() in seen_queries:
                    logger.warning(
                        "Cycle detected in reformulation '%s' on attempt %d; terminating loop.",
                        next_query,
                        attempt,
                    )
                    crag_result.can_proceed_to_generation = False
                    crag_result.insufficient_evidence = True
                    break

                logger.info(
                    "CRAG reformulation triggered (attempt %d -> %d): '%s' -> '%s'",
                    attempt,
                    attempt + 1,
                    active_query,
                    next_query,
                )
                seen_queries.add(next_query.lower().strip())
                active_query = next_query
                attempt += 1
            else:
                break

        return crag_result, attempt + 1, t_retrieval_total, t_crag_total

    # -------------------------------------------------------------------------
    # Streaming Pipeline for SSE
    # -------------------------------------------------------------------------

    async def query_stream(self, request: QueryRequest) -> AsyncIterator[Dict[str, Any]]:
        """Stream response tokens as an asynchronous generator for SSE endpoints.

        Yields:
          - {"event": "metadata", "data": {...}}
          - {"event": "sources", "data": [...]}
          - {"event": "token", "data": "token_str"}
          - {"event": "done", "data": {...}}
        """
        t_start = time.perf_counter()

        target_modality = request.model_modality or self.analyze_query_intent(
            request.query, request.document_ids
        )
        if request.model_modality is not None:
            target_modality = request.model_modality

        # Shared bounded retrieval and CRAG loop (Fix 1 parity)
        crag_result, attempts, _, _ = await self._run_retrieval_and_crag(
            query=request.query,
            target_modality=target_modality,
            top_k=request.top_k or self.config.default_top_k,
            enable_crag=request.enable_crag and self.config.enable_crag,
            document_ids=request.document_ids,
        )

        has_visual_evidence = any(
            getattr(c, "modality", "") == "visual_page" or getattr(c, "candidate_type", "") == "visual_page"
            for c in (crag_result.accepted_candidates if crag_result else [])
        )
        effective_modality = ModelModality.VISION if has_visual_evidence else target_modality

        token_budget = request.token_budget or self.config.default_token_budget
        cb_config = ContextBuilderConfig(
            token_budget=token_budget,
            model_modality=effective_modality,
        )
        context_response = ContextBuilder(cb_config).build(
            query=request.query,
            accepted_evidence=crag_result,
        )

        # Emit metadata event first
        yield {
            "event": "metadata",
            "data": {
                "query": request.query,
                "sources": [s.model_dump() for s in context_response.sources],
                "visual_inputs": context_response.visual_inputs,
                "crag_decision": crag_result.decision.label if crag_result.decision else None,
                "insufficient_evidence": crag_result.insufficient_evidence,
                "retrieval_attempts": attempts,
            },
        }

        # Emit explicit sources event for dual consumer compatibility (Fix 7)
        yield {
            "event": "sources",
            "data": [s.model_dump() for s in context_response.sources],
        }

        # Stream tokens
        is_insufficient = crag_result.insufficient_evidence or not context_response.sources
        async for token in self.generator.generate_stream(
            prompt=context_response.context,
            visual_inputs=context_response.visual_inputs,
            insufficient_evidence=is_insufficient,
        ):
            yield {"event": "token", "data": token}

        total_ms = (time.perf_counter() - t_start) * 1000
        yield {
            "event": "done",
            "data": {
                "total_ms": round(total_ms, 2),
                "retrieval_attempts": attempts,
                "insufficient_evidence": crag_result.insufficient_evidence,
            },
        }

    # -------------------------------------------------------------------------
    # Internal Candidate Fetcher with Safe Fallbacks
    # -------------------------------------------------------------------------

    def _fetch_candidates(
        self,
        query: str,
        top_k: int,
        modality: ModelModality,
        document_ids: Optional[List[str]] = None,
    ) -> List[RetrievalCandidate]:
        """Fetch and combine candidates from Person 2 and Person 3 with error isolation."""
        candidates: List[RetrievalCandidate] = []

        # Check if target documents have 0 text chunks or embeddings (scanned or visual-only)
        is_zero_text_doc = False
        if document_ids:
            try:
                import json
                from app.config import default_settings
                processed_dir = default_settings.get_processed_path()
                for did in document_ids:
                    doc_path = processed_dir / f"{did}.json"
                    if doc_path.exists():
                        d = json.loads(doc_path.read_text(encoding="utf-8"))
                        if (
                            d.get("total_chunks", 0) == 0
                            or d.get("zero_text_chunks", False)
                            or d.get("zero_embeddings", False)
                            or d.get("zero_text_fallback", False)
                            or d.get("pipeline_modality") == "visual_only"
                        ):
                            is_zero_text_doc = True
                            break
            except Exception as exc:
                logger.debug("Error checking zero text document status: %s", exc)

        if is_zero_text_doc and modality != ModelModality.VISION:
            logger.info("Target document '%s' has 0 text chunks or embeddings. Moving directly to visual module.", document_ids)
            modality = ModelModality.VISION

        # 1. Fetch visual candidates from Person 3 (if modality is VISION and bridge is active)
        visual_candidates = []
        if modality == ModelModality.VISION and self.visual_bridge is not None:
            try:
                if getattr(self.visual_bridge, "enabled", False):
                    scored_visuals = self.visual_bridge.retrieve(
                        query=query,
                        top_k=top_k,
                        document_ids=document_ids,
                    )
                    # Convert ScoredCandidate to RetrievalCandidate if needed
                    for sc in scored_visuals:
                        if isinstance(sc, RetrievalCandidate):
                            visual_candidates.append(sc)
                        elif hasattr(sc, "to_candidate"):
                            visual_candidates.append(sc.to_candidate())
                        elif isinstance(sc, dict):
                            visual_candidates.append(RetrievalCandidate.model_validate(sc))
                        else:
                            meta = getattr(sc, "metadata", {}) or {}
                            img_path = meta.get("image_path") or getattr(sc, "image_path", None)
                            doc_id = getattr(sc, "document_id", "doc")
                            page_num = getattr(sc, "page_number", 1)
                            src_file = getattr(sc, "source_filename", "") or "document.pdf"
                            score = float(getattr(sc, "score", 0.8))
                            cand = RetrievalCandidate(
                                candidate_id=getattr(sc, "chunk_id", None) or f"{doc_id}_p{page_num}",
                                document_id=doc_id,
                                source_filename=src_file,
                                page_start=page_num,
                                page_end=page_num,
                                candidate_type="visual_page",
                                text=getattr(sc, "text", "") or f"Visual page {page_num} from {src_file}",
                                page_reference=img_path,
                                retrieval_method="colpali",
                                retrieval_rank=getattr(sc, "rank", 1),
                                retrieval_score=score,
                                metadata=meta,
                            )
                            visual_candidates.append(cand)
            except Exception as e:
                logger.warning("Visual retrieval via ColPali bridge failed: %s; falling back to text.", e)

        # 2. Fetch text candidates from Person 2
        filters = {"document_id": document_ids[0]} if (document_ids and len(document_ids) == 1) else None

        if self.retriever is not None:
            try:
                raw_results = self.retriever.retrieve(
                    query=query,
                    top_k=top_k,
                    filters=filters,
                    visual_candidates=visual_candidates if visual_candidates else None,
                )
                for item in raw_results:
                    if isinstance(item, RetrievalCandidate):
                        candidates.append(item)
                    elif hasattr(item, "to_candidate"):
                        candidates.append(item.to_candidate())
                    elif isinstance(item, dict):
                        candidates.append(RetrievalCandidate.model_validate(item))
                    elif hasattr(item, "candidate_id"):
                        # Duck-typed RetrievalResult from Person 2
                        item_modality = getattr(item, "modality", None)
                        candidate_type = getattr(item, "candidate_type", None)
                        if candidate_type is None:
                            candidate_type = (
                                "visual_page"
                                if item_modality == "visual_page"
                                else "text_chunk"
                            )
                        meta = dict(getattr(item, "metadata", {}) or {})
                        if item_modality:
                            meta["modality"] = item_modality
                        if hasattr(item, "colpali_score") and "colpali_score" not in meta:
                            meta["colpali_score"] = getattr(item, "colpali_score")
                        if hasattr(item, "colpali_rank") and "colpali_rank" not in meta:
                            meta["colpali_rank"] = getattr(item, "colpali_rank")

                        page_ref = getattr(item, "page_reference", None) or meta.get("image_path")
                        ret_method = getattr(item, "retrieval_method", None)
                        if not ret_method:
                            ret_method = "colpali" if candidate_type == "visual_page" else "hybrid"

                        score_val = getattr(item, "retrieval_score", None)
                        if score_val is None:
                            score_val = getattr(item, "fused_score", getattr(item, "score", 0.8))

                        item_text = getattr(item, "text", "") or getattr(item, "content", "")
                        if not item_text and candidate_type == "visual_page":
                            item_text = meta.get("ocr_text", "") or f"Visual page {getattr(item, 'page_start', 1)} from {getattr(item, 'source_filename', 'doc.pdf')}"

                        cand = RetrievalCandidate(
                            candidate_id=getattr(item, "candidate_id", "c"),
                            document_id=getattr(item, "document_id", "doc"),
                            source_filename=getattr(item, "source_filename", "doc.pdf"),
                            page_start=getattr(item, "page_start", 1),
                            page_end=getattr(item, "page_end", 1),
                            candidate_type=candidate_type,
                            text=item_text,
                            page_reference=page_ref,
                            retrieval_method=ret_method,
                            retrieval_rank=getattr(item, "retrieval_rank", len(candidates) + 1),
                            retrieval_score=score_val,
                            metadata=meta,
                        )
                        candidates.append(cand)
            except Exception as e:
                logger.error("Hybrid text retrieval failed: %s", e, exc_info=True)

        # 3. If retriever is not wired or returned empty and visual candidates exist, retain visual
        if not candidates and visual_candidates:
            candidates.extend(visual_candidates)

        # 4. Fallback: If text retrieval returned 0 candidates (e.g. scanned or handwritten PDF),
        # query visual retrieval bridge as an automatic fallback (without blocking auto-indexing)
        if not candidates and not visual_candidates and self.visual_bridge is not None:
            try:
                if getattr(self.visual_bridge, "enabled", False):
                    logger.info(
                        "Text retrieval returned 0 candidates. Querying visual retrieval fallback for '%s'...",
                        query[:50],
                    )
                    scored_visuals = self.visual_bridge.retrieve(
                        query=query,
                        top_k=top_k,
                        document_ids=document_ids,
                    )

                    if not scored_visuals and document_ids:
                        self._auto_index_missing_visual_pages(document_ids)
                        scored_visuals = self.visual_bridge.retrieve(
                            query=query,
                            top_k=top_k,
                            document_ids=document_ids,
                        )

                    for sc in scored_visuals:
                        if isinstance(sc, RetrievalCandidate):
                            candidates.append(sc)
                        elif hasattr(sc, "to_candidate"):
                            candidates.append(sc.to_candidate())
                        elif isinstance(sc, dict):
                            candidates.append(RetrievalCandidate.model_validate(sc))
                        else:
                            meta = getattr(sc, "metadata", {}) or {}
                            img_path = meta.get("image_path") or getattr(sc, "image_path", None)
                            doc_id = getattr(sc, "document_id", "doc")
                            page_num = getattr(sc, "page_number", 1)
                            src_file = getattr(sc, "source_filename", "") or "document.pdf"
                            score = float(getattr(sc, "score", 0.8))
                            cand = RetrievalCandidate(
                                candidate_id=getattr(sc, "chunk_id", None) or f"{doc_id}_p{page_num}",
                                document_id=doc_id,
                                source_filename=src_file,
                                page_start=page_num,
                                page_end=page_num,
                                candidate_type="visual_page",
                                text=getattr(sc, "text", "") or meta.get("ocr_text", "") or f"Visual page {page_num} from {src_file}",
                                page_reference=img_path,
                                retrieval_method="colpali",
                                retrieval_rank=getattr(sc, "rank", 1),
                                retrieval_score=score,
                                metadata=meta,
                            )
                            candidates.append(cand)
            except Exception as e:
                logger.warning("Visual fallback retrieval failed: %s", e)

        return candidates

    def _auto_index_missing_visual_pages(self, document_ids: Optional[List[str]] = None) -> bool:
        """Helper to index any un-indexed visual pages for target documents into Qdrant."""
        if self.visual_bridge is None or not getattr(self.visual_bridge, "enabled", False):
            return False

        try:
            import json
            from app.config import default_settings
            processed_dir = default_settings.get_processed_path()
            if not processed_dir.exists():
                return False

            target_files = []
            if document_ids:
                for did in document_ids:
                    json_path = processed_dir / f"{did}.json"
                    if json_path.exists():
                        target_files.append(json_path)
            else:
                target_files = list(processed_dir.glob("doc_*.json"))

            if not target_files:
                return False

            indexed_any = False
            for jf in target_files:
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                    doc_id = data.get("document_id")
                    pages = data.get("rendered_pages", [])
                    filename = data.get("document_name", "document.pdf")
                    if doc_id and pages:
                        if hasattr(self.visual_bridge, "count_document_pages"):
                            verified = self.visual_bridge.count_document_pages(doc_id)
                            if verified >= len(pages):
                                continue
                        logger.info("Indexing %d visual pages for '%s' into Qdrant...", len(pages), doc_id)
                        count = self.visual_bridge.index_pages(
                            rendered_pages=pages,
                            document_id=doc_id,
                            source_filename=filename,
                        )
                        if count > 0:
                            indexed_any = True
                except Exception as exc:
                    logger.warning("Auto-index error for %s: %s", jf, exc)
            return indexed_any
        except Exception as exc:
            logger.warning("Auto-index failed: %s", exc)
            return False

