"""app.comparison — Comparative Benchmarking Subsystem for AMCRAG vs Normal RAG."""

from app.comparison.evaluator import RAGEvaluator
from app.comparison.pipeline import ComparisonPipeline
from app.comparison.schemas import (
    AggregateQualityMetrics,
    CategoryBreakdown,
    ComparedQuestionResult,
    ComparisonRunRequest,
    ComparisonRunResponse,
    ComparisonSummary,
    EvaluationQuestion,
    MetricScores,
    PerformanceMetrics,
    PipelineOutput,
    QuestionCategory,
)

__all__ = [
    "RAGEvaluator",
    "ComparisonPipeline",
    "EvaluationQuestion",
    "MetricScores",
    "PipelineOutput",
    "ComparedQuestionResult",
    "AggregateQualityMetrics",
    "PerformanceMetrics",
    "CategoryBreakdown",
    "ComparisonSummary",
    "ComparisonRunRequest",
    "ComparisonRunResponse",
    "QuestionCategory",
]
