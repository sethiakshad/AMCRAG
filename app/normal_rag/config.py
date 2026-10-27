"""config.py — Configuration parameters for the Normal RAG baseline."""

from __future__ import annotations

import os
from typing import Optional
from pydantic import BaseModel, Field


DEFAULT_NORMAL_RAG_PROMPT_TEMPLATE = (
    "You are a helpful and factual AI assistant. "
    "Answer the user's question based strictly on the provided context below.\n"
    "If the answer cannot be found or deduced from the context, clearly state that the provided "
    "documents do not contain enough information to answer the question.\n"
    "Do not extrapolate or speculate beyond the provided evidence.\n\n"
    "--- CONTEXT ---\n"
    "{context}\n"
    "--- END CONTEXT ---\n\n"
    "Question: {question}\n\n"
    "Answer:"
)


class NormalRAGConfig(BaseModel):
    """Configuration settings for conventional Normal RAG workflow."""

    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Default number of text chunks to retrieve for context",
    )
    dense_model_name: str = Field(
        default="BAAI/bge-base-en-v1.5",
        description="HuggingFace model identifier for text embeddings",
    )
    collection_name: str = Field(
        default="normal_rag_text_chunks",
        description="Qdrant vector collection name dedicated to Normal RAG",
    )
    qdrant_path: Optional[str] = Field(
        default="./qdrant_storage",
        description="Local directory path for persistent Qdrant vector database",
    )
    qdrant_url: Optional[str] = Field(
        default_factory=lambda: os.environ.get("QDRANT_URL"),
        description="Optional remote Qdrant URL if running over HTTP/gRPC",
    )
    qdrant_api_key: Optional[str] = Field(
        default_factory=lambda: os.environ.get("QDRANT_API_KEY"),
        description="Optional Qdrant API key",
    )
    device: Optional[str] = Field(
        default=None,
        description="Compute device ('cpu', 'cuda', etc.). Defaults to auto-detection.",
    )
    similarity_threshold: Optional[float] = Field(
        default=None,
        description="Minimum cosine similarity score required for candidate acceptance",
    )
    token_budget: int = Field(
        default=4096,
        ge=500,
        le=128000,
        description="Maximum character or token budget for context assembly",
    )
    system_prompt_template: str = Field(
        default=DEFAULT_NORMAL_RAG_PROMPT_TEMPLATE,
        description="Prompt template combining retrieved context and question",
    )

    model_config = {"extra": "allow"}
