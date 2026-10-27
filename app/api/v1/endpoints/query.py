"""query.py — FastAPI endpoints for RAG query execution and SSE streaming."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_orchestrator
from app.schemas.api import QueryRequest, QueryResponse
from app.services.generator import LLMRateLimitError
from app.services.orchestrator import RAGOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()




@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Execute End-to-End RAG Query",
    description=(
        "Executes adaptive retrieval, CRAG evaluation, context building, and answer "
        "generation with 100% citation provenance and granular latency breakdown."
    ),
)
async def execute_query(
    payload: QueryRequest,
    orchestrator: RAGOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    """Execute standard non-streaming RAG question answering."""
    try:
        return await orchestrator.query(payload)
    except LLMRateLimitError as exc:
        logger.warning("LLM provider rate limit exceeded in query: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM provider rate limit exceeded: {str(exc)}",
            headers={"Retry-After": str(exc.retry_after)},
        )
    except Exception as exc:
        logger.error("Query execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution error: {str(exc)}",
        )


@router.post(
    "/query/stream",
    summary="Execute Streaming RAG Query (SSE)",
    description=(
        "Streams token-by-token answer generation using Server-Sent Events (SSE). "
        "Emits 'metadata' event with citations, 'token' events, and final 'done' event."
    ),
    responses={
        200: {
            "description": "Server-Sent Events text stream",
            "content": {"text/event-stream": {}},
        }
    },
)
async def execute_query_stream(
    payload: QueryRequest,
    request: Request,
    orchestrator: RAGOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    """Execute streaming RAG question answering with SSE output."""
    async def sse_event_generator() -> AsyncIterator[str]:
        try:
            async for item in orchestrator.query_stream(payload):
                if await request.is_disconnected():
                    logger.info("SSE client disconnected; terminating generator.")
                    break
                event_name = item.get("event", "message")
                data_val = item.get("data")
                if isinstance(data_val, (dict, list)):
                    payload_str = json.dumps(data_val, ensure_ascii=False)
                    yield f"event: {event_name}\ndata: {payload_str}\n\n"
                else:
                    lines = str(data_val).split("\n")
                    data_block = "\n".join(f"data: {line}" for line in lines)
                    yield f"event: {event_name}\n{data_block}\n\n"
        except LLMRateLimitError as exc:
            logger.warning("LLM provider rate limit during SSE: %s", exc)
            err_payload = json.dumps({"error": str(exc), "retry_after": exc.retry_after})
            yield f"event: error\ndata: {err_payload}\n\n"
        except asyncio.TimeoutError:
            logger.error("SSE stream overall timeout exceeded (120s).")
            err_payload = json.dumps({"error": "Request timed out. The query may be too complex or the backend is overloaded."})
            yield f"event: error\ndata: {err_payload}\n\n"
        except Exception as exc:
            logger.error("SSE stream encountered exception: %s", exc, exc_info=True)
            err_payload = json.dumps({"error": str(exc)})
            yield f"event: error\ndata: {err_payload}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
