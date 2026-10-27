"""normal_rag.py — FastAPI endpoint for the conventional Normal RAG baseline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_normal_rag_pipeline, get_settings
from app.config import Settings
from app.normal_rag.pipeline import NormalRAGPipeline
from app.normal_rag.schemas import NormalRAGRequest, NormalRAGResponse
from app.schemas.chunk import ProcessedDocumentOutput

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/query",
    response_model=NormalRAGResponse,
    summary="Execute Normal RAG Baseline Query",
    description=(
        "Executes conventional text-based RAG question answering: dense vector top-k retrieval "
        "and direct LLM generation without ColPali visual search or CRAG correction."
    ),
)
async def query_normal_rag(
    payload: NormalRAGRequest,
    pipeline: NormalRAGPipeline = Depends(get_normal_rag_pipeline),
) -> NormalRAGResponse:
    """Execute standard question answering using the Normal RAG baseline."""
    try:
        return await pipeline.query_async(payload)
    except Exception as exc:
        logger.error("Normal RAG query execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Normal RAG execution error: {str(exc)}",
        )


@router.post(
    "/index",
    summary="Index Processed Document into Normal RAG",
    description="Loads a previously processed document from data/processed/{doc_id}.json and indexes its text chunks into the Normal RAG vector store.",
)
async def index_document_for_normal_rag(
    document_id: str = Query(..., description="Document identifier (e.g. 'doc_a160afd4300a0538')"),
    settings: Settings = Depends(get_settings),
    pipeline: NormalRAGPipeline = Depends(get_normal_rag_pipeline),
):
    """Index an already ingested document into the Normal RAG vector database."""
    proc_path = settings.get_processed_path() / f"{document_id}.json"
    if not proc_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processed document file not found: {proc_path.name}",
        )

    try:
        data = json.loads(proc_path.read_text(encoding="utf-8"))
        doc_output = ProcessedDocumentOutput.model_validate(data)
        indexed_count = pipeline.index_document_output(doc_output)
        return {
            "status": "success",
            "document_id": document_id,
            "document_name": doc_output.document_name,
            "indexed_chunks": indexed_count,
            "message": f"Successfully indexed {indexed_count} chunks into Normal RAG vector store.",
        }
    except Exception as exc:
        logger.error("Failed to index document %s for Normal RAG: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index document: {str(exc)}",
        )
