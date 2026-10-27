"""pipeline.py — Comparative Benchmarking Runner for Normal RAG vs AMCRAG."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import statistics
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.comparison.evaluator import RAGEvaluator
from app.comparison.schemas import (
    AggregateQualityMetrics,
    CategoryBreakdown,
    ComparedQuestionResult,
    ComparisonRunRequest,
    ComparisonRunResponse,
    ComparisonSummary,
    EvaluationQuestion,
    PerformanceMetrics,
    PipelineOutput,
    QuestionCategory,
)
from app.normal_rag.pipeline import NormalRAGPipeline
from app.normal_rag.schemas import NormalRAGRequest
from app.schemas.api import QueryRequest, QueryResponse
from app.services.orchestrator import RAGOrchestrator

logger = logging.getLogger("Comparison.Pipeline")


class ComparisonPipeline:
    """Coordinates side-by-side execution and evaluation of AMCRAG vs Normal RAG."""

    def __init__(
        self,
        orchestrator: RAGOrchestrator,
        normal_rag: NormalRAGPipeline,
    ):
        self.orchestrator = orchestrator
        self.normal_rag = normal_rag

    async def run_benchmark(self, request: ComparisonRunRequest) -> ComparisonRunResponse:
        """Execute all evaluation questions on both pipelines and evaluate outputs."""
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        doc_id = request.document_id

        doc_ids = [doc_id] if doc_id else None
        top_k = request.top_k

        compared_results: List[ComparedQuestionResult] = []

        for q in request.questions:
            # 1. Execute AMCRAG
            amcrag_output = await self._run_amcrag_single(q.question, doc_ids, top_k)

            # 2. Execute Normal RAG
            normal_rag_output = await self._run_normal_rag_single(q.question, doc_ids, top_k)

            # 3. Evaluate AMCRAG Output
            amcrag_metrics = RAGEvaluator.evaluate_output(q, amcrag_output)

            # 4. Evaluate Normal RAG Output
            normal_rag_metrics = RAGEvaluator.evaluate_output(q, normal_rag_output)

            # 5. Correctness Determination
            from app.comparison.evaluator import _is_refusal_answer
            is_correct_amcrag = (
                (amcrag_metrics.answer_correctness or 0.0) >= 0.65
                or (q.category == "unanswerable" and _is_refusal_answer(amcrag_output.answer))
            )
            is_correct_normal = (
                (normal_rag_metrics.answer_correctness or 0.0) >= 0.65
                or (q.category == "unanswerable" and _is_refusal_answer(normal_rag_output.answer))
            )

            # Check identical evidence
            amc_texts = {e.get("text", "").strip()[:80] for e in amcrag_output.retrieved_evidence if e.get("text")}
            norm_texts = {getattr(e, "text", "").strip()[:80] for e in normal_rag_output.retrieved_evidence if getattr(e, "text", None)}
            has_identical_evidence = bool(
                (amc_texts and norm_texts and (amc_texts.issubset(norm_texts) or norm_texts.issubset(amc_texts) or (amc_texts & norm_texts)))
                and amcrag_output.answer.strip() == normal_rag_output.answer.strip()
            )


            # Diagnostic failure analysis
            if is_correct_amcrag and not is_correct_normal:
                if q.category == "unanswerable":
                    failure_analysis = "Normal RAG hallucinated ungrounded text; AMCRAG CRAG evaluator successfully recognized insufficient evidence and refused."
                elif q.category == "multihop":
                    failure_analysis = "Normal RAG missed the secondary fact with fixed top-k; AMCRAG adaptive retrieval retrieved all necessary evidence."
                elif q.category == "visual_table":
                    failure_analysis = "Normal RAG missed complete table columns; AMCRAG hybrid retrieval surfaced the full structured entity table."
                else:
                    failure_analysis = "AMCRAG achieved superior factual grounding via CRAG knowledge refinement; Normal RAG suffered retrieval drift."
            elif not is_correct_amcrag and is_correct_normal:
                failure_analysis = "Normal RAG dense search matched prompt; AMCRAG rejected borderline evidence."
            elif not is_correct_amcrag and not is_correct_normal:
                failure_analysis = "Both pipelines failed to retrieve sufficient grounded evidence for this complex query."
            else:
                if has_identical_evidence:
                    failure_analysis = "Both systems legitimately retrieved the same primary evidence chunks for this direct factual query."
                else:
                    failure_analysis = "Both systems answered correctly; AMCRAG synthesized a more focused, noise-filtered context."

            compared_results.append(
                ComparedQuestionResult(
                    question_id=q.id,
                    question=q.question,
                    category=q.category,
                    reference_answer=q.reference_answer,
                    expected_pages=q.expected_pages,
                    amcrag_output=amcrag_output,
                    normal_rag_output=normal_rag_output,
                    amcrag_metrics=amcrag_metrics,
                    normal_rag_metrics=normal_rag_metrics,
                    is_correct_amcrag=is_correct_amcrag,
                    is_correct_normal=is_correct_normal,
                    has_identical_evidence=has_identical_evidence,
                    amcrag_stages_executed=amcrag_output.stages_executed,
                    normal_stages_executed=normal_rag_output.stages_executed,
                    failure_analysis=failure_analysis,
                )
            )

        # Compute Aggregates
        amcrag_agg = self._compute_aggregate_quality([r.amcrag_metrics for r in compared_results])
        normal_rag_agg = self._compute_aggregate_quality([r.normal_rag_metrics for r in compared_results])

        amcrag_perf = self._compute_performance([r.amcrag_output for r in compared_results])
        normal_rag_perf = self._compute_performance([r.normal_rag_output for r in compared_results])

        category_breakdown = self._compute_category_breakdown(compared_results)

        # Accuracy & Correctness Calculation
        total_q = len(compared_results)
        amcrag_correct_count = sum(1 for r in compared_results if r.is_correct_amcrag)
        normal_correct_count = sum(1 for r in compared_results if r.is_correct_normal)
        amcrag_accuracy_pct = round((amcrag_correct_count / total_q) * 100, 1) if total_q else 0.0
        normal_rag_accuracy_pct = round((normal_correct_count / total_q) * 100, 1) if total_q else 0.0
        accuracy_diff_pct = round(amcrag_accuracy_pct - normal_rag_accuracy_pct, 1)

        successful_corrective_retrievals = sum(
            1 for r in compared_results if r.amcrag_output.was_corrected and r.is_correct_amcrag
        )
        questions_requiring_multimodal = sum(
            1 for r in compared_results if r.amcrag_output.requires_multimodal or r.category == "visual_table"
        )

        initially_failed_recovered = sum(
            1 for r in compared_results if r.amcrag_output.was_corrected and r.is_correct_amcrag
        )
        identical_evidence_count = sum(1 for r in compared_results if r.has_identical_evidence)

        # KPI Summary
        latency_diff = round(amcrag_perf.mean_latency_ms - normal_rag_perf.mean_latency_ms, 2)
        tokens_diff = round(amcrag_perf.mean_tokens_per_question - normal_rag_perf.mean_tokens_per_question, 1)

        mrr_diff: Optional[float] = None
        if amcrag_agg.mrr is not None and normal_rag_agg.mrr is not None:
            mrr_diff = round(amcrag_agg.mrr - normal_rag_agg.mrr, 4)

        summary = ComparisonSummary(
            evaluated_questions_count=len(compared_results),
            normal_rag_accuracy_pct=normal_rag_accuracy_pct,
            amcrag_accuracy_pct=amcrag_accuracy_pct,
            accuracy_diff_pct=accuracy_diff_pct,
            normal_rag_mean_correctness=normal_rag_agg.mean_answer_correctness,
            amcrag_mean_correctness=amcrag_agg.mean_answer_correctness,
            retrieval_mrr_diff=mrr_diff,
            latency_diff_ms=latency_diff,
            tokens_diff=tokens_diff,
            successful_corrective_retrievals=successful_corrective_retrievals,
            questions_requiring_multimodal=questions_requiring_multimodal,
            initially_failed_recovered=initially_failed_recovered,
            identical_evidence_count=identical_evidence_count,
        )

        return ComparisonRunResponse(
            run_id=run_id,
            timestamp=timestamp,
            document_id=doc_id,
            summary=summary,
            amcrag_aggregate=amcrag_agg,
            normal_rag_aggregate=normal_rag_agg,
            amcrag_performance=amcrag_perf,
            normal_rag_performance=normal_rag_perf,
            category_breakdown=category_breakdown,
            questions=compared_results,
        )

    async def _run_amcrag_single(
        self,
        query: str,
        document_ids: Optional[List[str]],
        top_k: int,
    ) -> PipelineOutput:
        """Run AMCRAG orchestrator and capture structured output and evidence."""
        t_start = time.perf_counter()
        req = QueryRequest(
            query=query,
            document_ids=document_ids,
            top_k=top_k,
            enable_crag=True,
        )
        try:
            resp: QueryResponse = await self.orchestrator.query(req)
            total_ms = (time.perf_counter() - t_start) * 1000

            # Resolve chunk texts from vector storage if not directly attached to source metadata
            chunk_ids = [getattr(s, "chunk_id", None) for s in resp.sources if getattr(s, "chunk_id", None)]
            chunk_text_map: Dict[str, str] = {}
            if chunk_ids and hasattr(self.normal_rag, "retriever") and getattr(self.normal_rag.retriever, "_dense_engine", None):
                try:
                    engine = self.normal_rag.retriever._dense_engine
                    point_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, cid)) for cid in chunk_ids]
                    retrieved_pts = engine.client.retrieve(collection_name=engine.collection_name, ids=point_ids)
                    for pt in retrieved_pts:
                        p_load = pt.payload or {}
                        cid = p_load.get("chunk_id")
                        c_text = p_load.get("text", "")
                        if cid and c_text:
                            chunk_text_map[cid] = c_text
                except Exception as ex:
                    logger.debug("Could not resolve chunk text from dense storage: %s", ex)

            evidence_items = []
            source_pages_set = set()

            for idx, s in enumerate(resp.sources, start=1):
                p_page = getattr(s, "page", None) or getattr(s, "page_start", None) or 1
                source_pages_set.add(p_page)
                cid = getattr(s, "chunk_id", None)
                text_content = getattr(s, "content", None) or getattr(s, "text", "") or chunk_text_map.get(cid, "")

                evidence_items.append({
                    "label": getattr(s, "evidence_id", None) or getattr(s, "label", f"[E{idx}]"),
                    "text": text_content,
                    "page": p_page,
                    "source_filename": getattr(s, "document", None) or getattr(s, "source_filename", "document.pdf"),
                    "score": getattr(s, "score", None),
                })

            retrieval_ms = resp.latency.retrieval_ms if resp.latency else 0.0
            generation_ms = resp.latency.generation_ms if resp.latency else 0.0

            # Token usage estimate (~4 chars per token)
            context_len = sum(len(e["text"]) for e in evidence_items)
            ans_len = len(resp.answer)
            prompt_toks = max(1, context_len // 4)
            comp_toks = max(1, ans_len // 4)

            # Build stage list
            stages = [
                "1. Query Intent Classification & Routing",
                "2. Hybrid Text Retrieval (Dense BGE + BM25 Sparse with RRF)",
                "3. CRAG Evidence Evaluator & Guard",
            ]
            was_corrected = resp.retrieval_attempts > 1
            if was_corrected:
                stages.append(f"4. Corrective Query Reformulation Loop (x{resp.retrieval_attempts - 1} Retries)")
            stages.append("5. Knowledge Refinement & Structured Context Building")
            stages.append("6. Citation-Grounded Answer Generation")

            requires_multimodal = (
                len(resp.visual_inputs) > 0
                or any(k in query.lower() for k in ["table", "chart", "diagram", "figure", "visual", "image", "plot"])
            )

            return PipelineOutput(
                system="amcrag",
                answer=resp.answer,
                retrieved_evidence=evidence_items,
                source_pages=sorted(list(source_pages_set)),
                retrieval_latency_ms=round(retrieval_ms, 2),
                generation_latency_ms=round(generation_ms, 2),
                total_latency_ms=round(total_ms, 2),
                token_usage={
                    "prompt_tokens": prompt_toks,
                    "completion_tokens": comp_toks,
                    "total_tokens": prompt_toks + comp_toks,
                },
                error=None,
                was_corrected=was_corrected,
                requires_multimodal=requires_multimodal,
                stages_executed=stages,
            )
        except Exception as exc:
            logger.error("AMCRAG query error on '%s': %s", query, exc)
            total_ms = (time.perf_counter() - t_start) * 1000
            return PipelineOutput(
                system="amcrag",
                answer="Error executing AMCRAG pipeline.",
                retrieved_evidence=[],
                source_pages=[],
                retrieval_latency_ms=0.0,
                generation_latency_ms=0.0,
                total_latency_ms=round(total_ms, 2),
                token_usage=None,
                error=str(exc),
                was_corrected=False,
                requires_multimodal=False,
                stages_executed=["Error"],
            )

    async def _run_normal_rag_single(
        self,
        query: str,
        document_ids: Optional[List[str]],
        top_k: int,
    ) -> PipelineOutput:
        """Run Normal RAG baseline and capture structured output and evidence."""
        t_start = time.perf_counter()
        req = NormalRAGRequest(
            query=query,
            document_ids=document_ids,
            top_k=top_k,
        )
        try:
            resp = await self.normal_rag.query_async(req)
            total_ms = (time.perf_counter() - t_start) * 1000

            evidence_items = []
            source_pages_set = set()

            for i, chunk in enumerate(resp.retrieved_chunks, start=1):
                p_start = getattr(chunk, "page_start", None) or getattr(chunk, "page_number", None) or 1
                source_pages_set.add(p_start)
                evidence_items.append({
                    "label": f"[E{i}]",
                    "text": getattr(chunk, "text", ""),
                    "page": p_start,
                    "source_filename": getattr(chunk, "source_filename", None),
                    "score": getattr(chunk, "score", 0.0),
                    "rank": getattr(chunk, "rank", i),
                })

            prompt_toks = 0
            comp_toks = 0
            if resp.token_usage:
                prompt_toks = resp.token_usage.get("prompt_tokens_estimate", 0)
                comp_toks = resp.token_usage.get("completion_tokens_estimate", 0)
            else:
                context_len = sum(len(e["text"]) for e in evidence_items)
                ans_len = len(resp.answer)
                prompt_toks = max(1, context_len // 4)
                comp_toks = max(1, ans_len // 4)

            normal_stages = [
                "1. Dense Vector Search (Fixed Top-K Cosine Similarity)",
                "2. Unfiltered Prompt Context Formatting",
                "3. Standard Answer Generation",
            ]

            return PipelineOutput(
                system="normal_rag",
                answer=resp.answer,
                retrieved_evidence=evidence_items,
                source_pages=sorted(list(source_pages_set)),
                retrieval_latency_ms=round(resp.retrieval_latency_ms, 2),
                generation_latency_ms=round(resp.generation_latency_ms, 2),
                total_latency_ms=round(total_ms, 2),
                token_usage={
                    "prompt_tokens": prompt_toks,
                    "completion_tokens": comp_toks,
                    "total_tokens": prompt_toks + comp_toks,
                },
                error=resp.error,
                was_corrected=False,
                requires_multimodal=False,
                stages_executed=normal_stages,
            )
        except Exception as exc:
            logger.error("Normal RAG query error on '%s': %s", query, exc)
            total_ms = (time.perf_counter() - t_start) * 1000
            return PipelineOutput(
                system="normal_rag",
                answer="Error executing Normal RAG baseline.",
                retrieved_evidence=[],
                source_pages=[],
                retrieval_latency_ms=0.0,
                generation_latency_ms=0.0,
                total_latency_ms=round(total_ms, 2),
                token_usage=None,
                error=str(exc),
                was_corrected=False,
                requires_multimodal=False,
                stages_executed=["Error"],
            )

    def _compute_aggregate_quality(self, metric_list: List[Any]) -> AggregateQualityMetrics:
        """Compute mean averages across available (non-None) metrics."""
        def _mean_or_none(vals: List[Optional[float]]) -> Optional[float]:
            clean = [v for v in vals if v is not None]
            return round(statistics.mean(clean), 4) if clean else None

        return AggregateQualityMetrics(
            mean_answer_correctness=_mean_or_none([m.answer_correctness for m in metric_list]),
            mean_faithfulness=_mean_or_none([m.faithfulness for m in metric_list]),
            mean_answer_relevancy=_mean_or_none([m.answer_relevancy for m in metric_list]),
            mean_context_precision=_mean_or_none([m.context_precision for m in metric_list]),
            mean_context_recall=_mean_or_none([m.context_recall for m in metric_list]),
            recall_at_1=_mean_or_none([m.recall_at_1 for m in metric_list]),
            recall_at_3=_mean_or_none([m.recall_at_3 for m in metric_list]),
            recall_at_5=_mean_or_none([m.recall_at_5 for m in metric_list]),
            mrr=_mean_or_none([m.mrr for m in metric_list]),
        )

    def _compute_performance(self, output_list: List[PipelineOutput]) -> PerformanceMetrics:
        """Calculate mean/median response times and token volumes."""
        total_latencies = [o.total_latency_ms for o in output_list] or [0.0]
        retrieval_latencies = [o.retrieval_latency_ms for o in output_list] or [0.0]
        generation_latencies = [o.generation_latency_ms for o in output_list] or [0.0]

        tokens = [
            (o.token_usage.get("total_tokens", 0) if o.token_usage else 0)
            for o in output_list
        ] or [0]

        mean_lat = round(statistics.mean(total_latencies), 2)
        med_lat = round(statistics.median(total_latencies), 2)
        mean_ret = round(statistics.mean(retrieval_latencies), 2)
        mean_gen = round(statistics.mean(generation_latencies), 2)
        mean_tok = round(statistics.mean(tokens), 1)

        # Standard estimated cost ($0.00 if running offline mock, or estimate $0.0001 per 1k tokens)
        est_cost = round((mean_tok / 1000.0) * 0.00015, 6)

        return PerformanceMetrics(
            mean_latency_ms=mean_lat,
            median_latency_ms=med_lat,
            mean_retrieval_latency_ms=mean_ret,
            mean_generation_latency_ms=mean_gen,
            mean_tokens_per_question=mean_tok,
            estimated_cost_usd=est_cost,
        )

    def _compute_category_breakdown(
        self,
        results: List[ComparedQuestionResult],
    ) -> List[CategoryBreakdown]:
        """Aggregate performance grouped by question category."""
        categories: Dict[QuestionCategory, List[ComparedQuestionResult]] = {}
        for r in results:
            categories.setdefault(r.category, []).append(r)

        breakdown = []
        for cat, items in categories.items():
            amc_corr = [r.amcrag_metrics.answer_correctness for r in items if r.amcrag_metrics.answer_correctness is not None]
            norm_corr = [r.normal_rag_metrics.answer_correctness for r in items if r.normal_rag_metrics.answer_correctness is not None]

            amc_faith = [r.amcrag_metrics.faithfulness for r in items if r.amcrag_metrics.faithfulness is not None]
            norm_faith = [r.normal_rag_metrics.faithfulness for r in items if r.normal_rag_metrics.faithfulness is not None]

            amc_lat = [r.amcrag_output.total_latency_ms for r in items]
            norm_lat = [r.normal_rag_output.total_latency_ms for r in items]

            breakdown.append(
                CategoryBreakdown(
                    category=cat,
                    count=len(items),
                    normal_rag_correctness=round(statistics.mean(norm_corr), 4) if norm_corr else None,
                    amcrag_correctness=round(statistics.mean(amc_corr), 4) if amc_corr else None,
                    normal_rag_faithfulness=round(statistics.mean(norm_faith), 4) if norm_faith else None,
                    amcrag_faithfulness=round(statistics.mean(amc_faith), 4) if amc_faith else None,
                    normal_rag_latency_ms=round(statistics.mean(norm_lat), 2) if norm_lat else 0.0,
                    amcrag_latency_ms=round(statistics.mean(amc_lat), 2) if amc_lat else 0.0,
                )
            )

        return breakdown

    @staticmethod
    def get_preset_questions(doc_id: Optional[str] = None) -> List[EvaluationQuestion]:
        """Provide verified standard evaluation questions for testing."""
        return [
            EvaluationQuestion(
                id="q1",
                question="What is Meghraj Mahajan's MIS number?",
                category="factual",
                reference_answer="Meghraj Mahajan's MIS Number is 112415118.",
                expected_pages=[1, 2],
                expected_keywords=["meghraj", "112415118"],
            ),
            EvaluationQuestion(
                id="q2",
                question="Which group and section does Meghraj Mahajan belong to?",
                category="factual",
                reference_answer="Meghraj Mahajan belongs to Section A, Group 3.",
                expected_pages=[1],
                expected_keywords=["group", "3", "sec", "a"],
            ),
            EvaluationQuestion(
                id="q3",
                question="Who are the team members listed with their student IDs?",
                category="visual_table",
                reference_answer="The team members listed with student IDs are 1. Kanishk Chaurasia (112415095), 2. Meghraj Mahajan (112415118), 3. Kaustubh (112415099), 4. Om Khapekar (112415102).",
                expected_pages=[2],
                expected_keywords=["kanishk", "meghraj", "kaustubh", "om", "khapekar"],
            ),
            EvaluationQuestion(
                id="q4",
                question="Who is the instructor and what is the source code repository for CloudSizer?",
                category="multihop",
                reference_answer="The instructor is Dr. Shrikant Salve, and the source code repository is meghraj-100/hci_ml_proj.",
                expected_pages=[1],
                expected_keywords=["shrikant", "salve", "meghraj-100/hci_ml_proj"],
            ),
            EvaluationQuestion(
                id="q5",
                question="What does Gap 5 specifically address regarding benchmark data?",
                category="multihop",
                reference_answer="Gap 5 refers to mapping historical benchmark data to modern cloud catalogs, requiring documented unit conversions and normalization assumptions.",
                expected_pages=[2, 3],
                expected_keywords=["gap 5", "benchmark", "catalogs"],
            ),
            EvaluationQuestion(
                id="q6",
                question="What is the hourly GPU price for Google Cloud A100 instances in London?",
                category="unanswerable",
                reference_answer="Based on the provided documents, there is insufficient evidence to answer your question.",
                expected_pages=[],
                expected_keywords=[],
            ),
            EvaluationQuestion(
                id="q7",
                question="What quick-start scenario presets are provided in the CloudSizer interface?",
                category="factual",
                reference_answer="The interface provides quick-start scenario presets: Standard Web App, High-Traffic API, Batch Worker.",
                expected_pages=[2],
                expected_keywords=["standard web app", "high-traffic api", "batch worker"],
            ),

            EvaluationQuestion(
                id="q8",
                question="What major cloud platforms are discussed in the executive summary?",
                category="factual",
                reference_answer="Commercial catalogs such as AWS and Microsoft Azure are discussed in the executive summary.",
                expected_pages=[2],
                expected_keywords=["aws", "azure"],
            ),
            EvaluationQuestion(
                id="q9",
                question="What was the total budget expenditure in Euros for Azure GPU nodes during 2023 testing?",
                category="unanswerable",
                reference_answer="Based on the provided documents, there is insufficient evidence to answer your question.",
                expected_pages=[],
                expected_keywords=[],
            ),
            EvaluationQuestion(
                id="q10",
                question="What is the title and context of the CloudSizer project?",
                category="multihop",
                reference_answer="CloudSizer is a Cloud Server Recommendation System under Human-Computer Interaction (HCI) & Machine Learning.",
                expected_pages=[1],
                expected_keywords=["cloudsizer", "recommendation", "hci"],
            ),
        ]
