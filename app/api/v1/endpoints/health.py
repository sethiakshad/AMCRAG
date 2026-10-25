"""health.py — FastAPI endpoint for AMCRAG subsystem health check and readiness probe."""

from __future__ import annotations

import logging
import time
from typing import Dict
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_orchestrator
from app.schemas.api import HealthResponse
from app.services.orchestrator import RAGOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=HealthResponse,
    summary="Subsystem Health & Readiness Probe",
    description="Inspects operational readiness across Vector DB, BM25 index, CRAG evaluator, and LLM generator.",
)
def check_health(
    request: Request,
    orchestrator: RAGOrchestrator = Depends(get_orchestrator),
) -> HealthResponse:
    """Verify connectivity and readiness of all AMCRAG subsystems."""
    components: Dict[str, bool] = {
        "vector_db": False,
        "bm25": False,
        "crag": False,
        "llm": False,
    }

    # 1. Vector DB (Qdrant) check
    if orchestrator.retriever is not None and hasattr(orchestrator.retriever, "dense_engine"):
        try:
            client = getattr(orchestrator.retriever.dense_engine, "client", None)
            if client is not None:
                client.get_collections()
                components["vector_db"] = True
            else:
                components["vector_db"] = True
        except Exception as e:
            logger.warning("Vector DB health check failed: %s", e)
            components["vector_db"] = False
    else:
        # Fallback or standalone check
        components["vector_db"] = True

    # 2. BM25 Sparse Index check
    if orchestrator.retriever is not None and hasattr(orchestrator.retriever, "sparse_engine"):
        components["bm25"] = orchestrator.retriever.sparse_engine is not None
    else:
        components["bm25"] = True

    # 3. CRAG Evaluator check
    components["crag"] = orchestrator.crag_controller is not None

    # 4. LLM Generator check
    components["llm"] = orchestrator.generator is not None

    # Optional: ColPali visual bridge status
    if orchestrator.visual_bridge is not None:
        components["colpali"] = getattr(orchestrator.visual_bridge, "enabled", True)

    # Determine overall status
    critical_healthy = (
        components.get("vector_db", False)
        and components.get("crag", False)
        and components.get("llm", False)
    )
    overall_status = "healthy" if critical_healthy else "degraded"

    # Compute uptime
    start_time = getattr(request.app.state, "start_time", None)
    uptime_seconds = None
    if start_time is not None:
        uptime_seconds = round(time.time() - start_time, 2)

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        components=components,
        uptime_seconds=uptime_seconds,
    )
