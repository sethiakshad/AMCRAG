"""comparison.py — FastAPI endpoints for running and managing RAG comparative evaluations."""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_comparison_pipeline
from app.comparison.pipeline import ComparisonPipeline
from app.comparison.schemas import (
    ComparisonRunRequest,
    ComparisonRunResponse,
    EvaluationQuestion,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/run",
    response_model=ComparisonRunResponse,
    summary="Execute Normal RAG vs AMCRAG Benchmark",
    description=(
        "Executes identical evaluation questions sequentially on both AMCRAG and the Normal RAG baseline, "
        "calculating ground-truth answer correctness, faithfulness, relevancy, context precision/recall, "
        "retrieval recall@k/MRR, latency, and token metrics."
    ),
)
async def run_comparison_benchmark(
    payload: ComparisonRunRequest,
    pipeline: ComparisonPipeline = Depends(get_comparison_pipeline),
) -> ComparisonRunResponse:
    """Run side-by-side comparative evaluation of AMCRAG vs Normal RAG."""
    try:
        return await pipeline.run_benchmark(payload)
    except Exception as exc:
        logger.error("Error executing comparison benchmark: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison evaluation failed: {str(exc)}",
        )


@router.get(
    "/default-questions",
    response_model=List[EvaluationQuestion],
    summary="Get Default Evaluation Benchmark Questions",
    description="Returns pre-configured evaluation questions covering factual, multihop, visual/table, and unanswerable categories.",
)
async def get_default_questions(
    document_id: Optional[str] = Query(default=None, description="Optional document ID to contextualize questions"),
    pipeline: ComparisonPipeline = Depends(get_comparison_pipeline),
) -> List[EvaluationQuestion]:
    """Retrieve verified evaluation questions for benchmarking."""
    return pipeline.get_preset_questions(doc_id=document_id)
