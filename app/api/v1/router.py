"""router.py — Aggregates all v1 API route controllers into a single APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import documents, health, query

api_router = APIRouter()

# 1. Query endpoints: /api/v1/query and /api/v1/query/stream
api_router.include_router(query.router, prefix="", tags=["Query Execution"])

# 2. Document management endpoints: /api/v1/documents
api_router.include_router(documents.router, prefix="/documents", tags=["Knowledge Base & Documents"])

# 3. Subsystem health check: /api/v1/health
api_router.include_router(health.router, prefix="/health", tags=["Health & Readiness"])
