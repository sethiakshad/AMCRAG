"""main.py — FastAPI Application Factory, Lifespan Singleton Management, and Server Entrypoint.

Orchestrates the entire AMCRAG system:
  1. Person 1: Document Processing Pipeline & Duplicate Detector
  2. Person 2: Dense BGE Embeddings + BM25 Sparse Hybrid Retriever
  3. Person 3: ColPali Visual Retrieval Bridge
  4. Person 4: CRAG Evaluator, Gatekeeper & Query Reformulator
  5. Person 5: Context Builder, Answer Generator, and FastAPI Gateway
"""

from __future__ import annotations

import os

# Crucial Windows OpenMP & HuggingFace runtime guards
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.config import Settings, default_settings
from app.crag.controller import CRAGController
from app.services.duplicate_detector import DuplicateDetector
from app.services.generator import AnswerGenerator, GeneratorConfig
from app.services.orchestrator import OrchestratorConfig, RAGOrchestrator
from app.services.pipeline import DocumentProcessingPipeline
from app.services.retrieval_bridge import ColPaliVisualBridge

# Configure structured application logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Configure structured application logger for AMCRAG
logger = logging.getLogger("amcrag.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Asynchronous lifespan context manager for startup and graceful shutdown.

    Warms up singleton neural models, establishes vector store connections,
    and cleanly closes resource handles on server shutdown.
    """
    logger.info("Initializing AMCRAG backend services and singleton dependencies...")
    app.state.start_time = time.time()

    settings: Settings = getattr(app.state, "settings", None) or default_settings
    app.state.settings = settings

    # Ensure required runtime storage directories exist
    settings.get_uploads_path()
    settings.get_processed_path()
    settings.get_page_images_path()

    initialize_models: bool = getattr(app.state, "initialize_models", True)

    if initialize_models:
        # 1. Person 1: Ingestion & Deduplication Services
        app.state.duplicate_detector = DuplicateDetector(settings=settings)
        app.state.pipeline = DocumentProcessingPipeline(settings=settings)

        # 2. Person 2: Hybrid Text Retriever (BGE Dense + BM25 Sparse)
        retriever = None
        try:
            from app.retrieval.hybrid_retriever import HybridTextRetriever

            logger.info("Loading Person 2 HybridTextRetriever...")
            retriever = HybridTextRetriever(
                dense_model_name="BAAI/bge-base-en-v1.5",
                qdrant_path=str(settings.base_dir / "qdrant_storage"),
                bm25_index_path=str(settings.base_dir / "bm25_index.pkl"),
            )
            logger.info("HybridTextRetriever initialized successfully.")
        except Exception as exc:
            logger.warning(
                "Could not initialize HybridTextRetriever on startup: %s. "
                "Running in decoupled/fallback retrieval mode.",
                exc,
            )
        app.state.retriever = retriever

        # 3. Person 3: ColPali Visual Retrieval Bridge
        visual_bridge = None
        try:
            logger.info("Initializing Person 3 ColPaliVisualBridge (enabled=%s)...", settings.colpali_enabled)
            visual_bridge = ColPaliVisualBridge(
                qdrant_url=settings.qdrant_url,
                collection=settings.colpali_collection_name,
                top_k=settings.colpali_top_k,
                batch_size=settings.colpali_batch_size,
                device=settings.colpali_device,
                enabled=settings.colpali_enabled,
                max_pages=settings.colpali_max_pages_per_doc,
            )
            logger.info("ColPaliVisualBridge initialized (is_ready=%s).", visual_bridge.is_ready)
        except Exception as exc:
            logger.warning("ColPaliVisualBridge failed to initialize: %s. Visual search disabled.", exc)
        app.state.visual_bridge = visual_bridge

        # 4. Person 4: CRAG Controller (Evaluator + Decision Engine + Reformulator)
        try:
            logger.info("Initializing Person 4 CRAGController...")
            crag_controller = CRAGController()
            app.state.crag_controller = crag_controller
            logger.info("CRAGController initialized successfully.")
        except Exception as exc:
            logger.warning("CRAGController initialization warning: %s.", exc)
            app.state.crag_controller = None

        # 5. Person 5: Answer Generation Service
        try:
            logger.info("Initializing Person 5 AnswerGenerator...")
            if settings.llm_provider in ("ollama", "ollama_cloud"):
                provider_model = settings.ollama_model
                provider_key = settings.get_ollama_api_key()
                provider_base_url = settings.ollama_base_url
            elif settings.llm_provider == "openai":
                provider_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
                provider_key = os.environ.get("OPENAI_API_KEY")
                provider_base_url = None
            else:
                provider_model = settings.gemini_model
                provider_key = settings.get_gemini_api_key()
                provider_base_url = None

            gen_config = GeneratorConfig(
                provider=settings.llm_provider,
                model_name=provider_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                api_key=provider_key,
                base_url=provider_base_url,
                fallback_to_mock=True,
            )
            generator = AnswerGenerator(gen_config)
            app.state.generator = generator
            logger.info(
                "AnswerGenerator initialized with active_provider='%s' (configured='%s', model='%s').",
                generator.active_provider,
                gen_config.provider,
                gen_config.model_name,
            )
        except Exception as exc:
            logger.warning("AnswerGenerator initialization warning: %s; falling back to Mock.", exc)
            generator = AnswerGenerator(GeneratorConfig(provider="mock"))
            app.state.generator = generator

        # 6. Person 5: Central RAG Orchestrator
        app.state.orchestrator = RAGOrchestrator(
            config=OrchestratorConfig(),
            retriever=app.state.retriever,
            visual_bridge=app.state.visual_bridge,
            crag_controller=app.state.crag_controller,
            generator=app.state.generator,
        )
        logger.info("Central RAGOrchestrator online and ready.")

    yield

    # =========================================================================
    # Graceful Shutdown
    # =========================================================================
    logger.info("Executing AMCRAG graceful shutdown...")
    if hasattr(app.state, "retriever") and app.state.retriever is not None:
        try:
            dense_eng = getattr(app.state.retriever, "dense_engine", None)
            if dense_eng and hasattr(dense_eng, "client") and hasattr(dense_eng.client, "close"):
                dense_eng.client.close()
                logger.info("Closed Qdrant vector database client connection.")
        except Exception as exc:
            logger.warning("Error releasing vector database client: %s", exc)

    logger.info("AMCRAG shutdown sequence finished.")


def create_app(
    settings: Optional[Settings] = None,
    initialize_models: bool = True,
) -> FastAPI:
    """Create and configure the primary AMCRAG FastAPI application."""
    app_settings = settings or default_settings

    app = FastAPI(
        title="AMCRAG — Adaptive Multimodal Corrective RAG",
        description=(
            "Production-ready FastAPI orchestration backend integrating Document Ingestion, "
            "Hybrid Text Retrieval (Dense BGE + Sparse BM25), ColPali Multi-Vector Visual Retrieval, "
            "CRAG Quality Evaluation & Correction Loops, and Grounded Multi-Provider Answer Generation."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Set initial state
    app.state.settings = app_settings
    app.state.initialize_models = initialize_models

    # Configure CORS for local frontend development (Vite / React / Next.js)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5175",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------------
    # Global Exception Handlers for Clean, Standardized JSON Responses
    # -------------------------------------------------------------------------

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Standardize HTTP exception error envelopes."""
        detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": detail_msg,
                "detail": detail_msg,
                "status_code": exc.status_code,
            },
            headers=exc.headers,
        )


    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Format 422 schema validation errors with structured field diagnostics."""
        formatted_errors = []
        for err in exc.errors():
            loc = " -> ".join(str(p) for p in err.get("loc", []))
            formatted_errors.append({
                "field": loc,
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            })
        http_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        return JSONResponse(
            status_code=http_422,
            content={
                "error": "Request validation failed",
                "details": formatted_errors,
                "status_code": http_422,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Intercept unhandled internal errors and emit a structured HTTP 500 response."""
        logger.error(
            "Unhandled server exception on %s %s: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": str(exc),
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )

    # -------------------------------------------------------------------------
    # Mount Sub-Routers & Static Files
    # -------------------------------------------------------------------------

    app.include_router(api_router, prefix="/api/v1")

    # Serve rendered 150 DPI page PNG images for ColPali and frontend preview
    page_images_dir = app_settings.get_page_images_path()
    page_images_dir.mkdir(parents=True, exist_ok=True)
    try:
        from fastapi.staticfiles import StaticFiles
        app.mount("/static/page_images", StaticFiles(directory=str(page_images_dir)), name="page_images")
    except Exception as exc:
        logger.warning("Could not mount static page_images directory: %s", exc)


    # -------------------------------------------------------------------------
    # Root Diagnostic Endpoint
    # -------------------------------------------------------------------------

    @app.get("/", tags=["System Information"], summary="AMCRAG API Root")
    def root_diagnostic():
        """Root status probe providing service metadata and discovery URLs."""
        return {
            "service": "AMCRAG — Adaptive Multimodal Corrective RAG",
            "version": "1.0.0",
            "status": "online",
            "docs_url": "/docs",
            "health_url": "/api/v1/health",
            "query_url": "/api/v1/query",
            "documents_url": "/api/v1/documents",
        }

    return app


# Default ASGI application instance for production runners (uvicorn app.main:app)
app = create_app()


if __name__ == "__main__":
    import uvicorn

    server_port = int(os.environ.get("PORT", os.environ.get("AMCRAG_PORT", 8000)))
    uvicorn.run("app.main:app", host="0.0.0.0", port=server_port, reload=True)
