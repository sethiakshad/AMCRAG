"""schemas.py — Data contracts and metrics definitions for Normal RAG vs AMCRAG Comparison."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

QuestionCategory = Literal["factual", "multihop", "visual_table", "unanswerable"]


class EvaluationQuestion(BaseModel):
    """A standardized evaluation question for comparative benchmarking."""

    id: str = Field(description="Unique question identifier (e.g. 'q1')")
    question: str = Field(description="The evaluation prompt / query text")
    category: QuestionCategory = Field(default="factual", description="Question difficulty / modality category")
    reference_answer: Optional[str] = Field(default=None, description="Ground truth answer (if available)")
    expected_pages: Optional[List[int]] = Field(default=None, description="Ground truth source page numbers")
    expected_keywords: Optional[List[str]] = Field(default=None, description="Required keywords in evidence")


class PipelineOutput(BaseModel):
    """Captured execution output from one RAG system."""

    system: Literal["amcrag", "normal_rag"]
    answer: str
    retrieved_evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of retrieved chunks with text, rank, score, page",
    )
    source_pages: List[int] = Field(default_factory=list)
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    token_usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None
    was_corrected: bool = False
    requires_multimodal: bool = False
    stages_executed: List[str] = Field(default_factory=list)


class MetricScores(BaseModel):
    """Fine-grained evaluated metrics for a single question response."""

    # Answer quality
    answer_correctness: Optional[float] = None
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None

    # Retrieval quality (requires ground truth relevance labels)
    recall_at_1: Optional[float] = None
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None
    ndcg_at_5: Optional[float] = None


class ComparedQuestionResult(BaseModel):
    """Side-by-side execution and evaluation result for a single question."""

    question_id: str
    question: str
    category: QuestionCategory
    reference_answer: Optional[str] = None
    expected_pages: Optional[List[int]] = None
    amcrag_output: PipelineOutput
    normal_rag_output: PipelineOutput
    amcrag_metrics: MetricScores
    normal_rag_metrics: MetricScores
    is_correct_amcrag: bool = False
    is_correct_normal: bool = False
    has_identical_evidence: bool = False
    amcrag_stages_executed: List[str] = Field(default_factory=list)
    normal_stages_executed: List[str] = Field(default_factory=list)
    failure_analysis: Optional[str] = None


class AggregateQualityMetrics(BaseModel):
    """Aggregated average quality scores across all evaluated questions."""

    mean_answer_correctness: Optional[float] = None
    mean_faithfulness: Optional[float] = None
    mean_answer_relevancy: Optional[float] = None
    mean_context_precision: Optional[float] = None
    mean_context_recall: Optional[float] = None
    recall_at_1: Optional[float] = None
    recall_at_3: Optional[float] = None
    recall_at_5: Optional[float] = None
    mrr: Optional[float] = None


class PerformanceMetrics(BaseModel):
    """Aggregated system operational and latency metrics."""

    mean_latency_ms: float
    median_latency_ms: float
    mean_retrieval_latency_ms: float
    mean_generation_latency_ms: float
    mean_tokens_per_question: float
    estimated_cost_usd: Optional[float] = None


class CategoryBreakdown(BaseModel):
    """Performance breakdown across individual question categories."""

    category: QuestionCategory
    count: int
    normal_rag_correctness: Optional[float] = None
    amcrag_correctness: Optional[float] = None
    normal_rag_faithfulness: Optional[float] = None
    amcrag_faithfulness: Optional[float] = None
    normal_rag_latency_ms: float
    amcrag_latency_ms: float


class ComparisonSummary(BaseModel):
    """High-level comparison KPIs."""

    evaluated_questions_count: int
    normal_rag_accuracy_pct: Optional[float] = None
    amcrag_accuracy_pct: Optional[float] = None
    accuracy_diff_pct: Optional[float] = None
    normal_rag_mean_correctness: Optional[float] = None
    amcrag_mean_correctness: Optional[float] = None
    retrieval_mrr_diff: Optional[float] = None
    latency_diff_ms: float = 0.0  # AMCRAG latency minus Normal RAG latency
    tokens_diff: float = 0.0
    successful_corrective_retrievals: int = 0
    questions_requiring_multimodal: int = 0
    initially_failed_recovered: int = 0
    identical_evidence_count: int = 0


class ComparisonRunRequest(BaseModel):
    """Request payload to initiate a side-by-side RAG benchmark."""

    document_id: Optional[str] = Field(default=None, description="Document ID to scope retrieval")
    questions: List[EvaluationQuestion] = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class ComparisonRunResponse(BaseModel):
    """Full benchmark response payload for dashboard rendering."""

    run_id: str
    timestamp: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    summary: ComparisonSummary
    amcrag_aggregate: AggregateQualityMetrics
    normal_rag_aggregate: AggregateQualityMetrics
    amcrag_performance: PerformanceMetrics
    normal_rag_performance: PerformanceMetrics
    category_breakdown: List[CategoryBreakdown]
    questions: List[ComparedQuestionResult]
