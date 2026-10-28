"""
Comprehensive end-to-end test script for sample/6-Support+Vector+Classifier.pdf.
Indexes the visual pages into Qdrant using ColPali and executes query tests
through RAGOrchestrator, checking CRAG evaluation and answer generation.
"""

import sys
import os
import json
import time
import asyncio
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

# Ensure environment loaded
load_dotenv()
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from app.config import default_settings
from app.services.retrieval_bridge import ColPaliVisualBridge
from app.services.orchestrator import RAGOrchestrator, OrchestratorConfig
from app.retrieval.hybrid_retriever import HybridTextRetriever
from app.crag.controller import CRAGController
from app.services.generator import AnswerGenerator, GeneratorConfig
from app.schemas.api import QueryRequest, ModelModality
from qdrant_client import QdrantClient

async def run_svm_evaluation():
    pdf_path = Path("sample/6-Support+Vector+Classifier.pdf")
    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} not found!")
        return

    print("=" * 75)
    print("STEP 1: INSPECTING PDF AND PROCESSED METADATA")
    print("=" * 75)
    print(f"PDF Path      : {pdf_path.resolve()}")
    print(f"File Size     : {pdf_path.stat().st_size:,} bytes")

    doc_id = "doc_03cf1724ad9d8b00"
    processed_json = default_settings.get_processed_path() / f"{doc_id}.json"
    if not processed_json.exists():
        print(f"Processed JSON not found at {processed_json}, creating from pipeline...")
        from app.services.pipeline import DocumentProcessingPipeline
        pipeline = DocumentProcessingPipeline(settings=default_settings)
        res = pipeline.process_file(pdf_path)
        doc_id = res.document_id
        processed_json = default_settings.get_processed_path() / f"{doc_id}.json"

    meta_data = json.loads(processed_json.read_text(encoding="utf-8"))
    rendered_pages = meta_data.get("rendered_pages", [])
    print(f"Document ID   : {doc_id}")
    print(f"Pages Found   : {len(rendered_pages)}")
    for p in rendered_pages:
        img_p = Path(p["image_path"])
        print(f"  - Page {p['page_number']}: exists={img_p.exists()}, size={img_p.stat().st_size if img_p.exists() else 0:,} bytes")

    print("\n" + "=" * 75)
    print("STEP 2: INITIALIZING COLPALI VISUAL BRIDGE & QDRANT")
    print("=" * 75)
    bridge = ColPaliVisualBridge(
        qdrant_url=default_settings.qdrant_url,
        collection=default_settings.colpali_collection_name,
        top_k=default_settings.colpali_top_k,
        batch_size=default_settings.colpali_batch_size,
        device=default_settings.colpali_device,
        enabled=True,
        max_pages=default_settings.colpali_max_pages_per_doc,
    )

    client = bridge._indexer._client
    print(f"Connected to Qdrant. Existing points for {doc_id}: {bridge.count_document_pages(doc_id)}")

    # Index pages if not already indexed
    if bridge.count_document_pages(doc_id) < len(rendered_pages):
        print(f"\nEmbedding and indexing {len(rendered_pages)} pages with ColPali...")
        t0 = time.time()
        indexed_count = bridge.index_pages(
            rendered_pages=rendered_pages,
            document_id=doc_id,
            source_filename=meta_data.get("document_name", pdf_path.name),
        )
        elapsed = time.time() - t0
        print(f"Indexing completed in {elapsed:.1f}s. Pages indexed: {indexed_count}")
    else:
        print(f"Pages already indexed ({bridge.count_document_pages(doc_id)} points in Qdrant).")

    # Update processed json status
    meta_data["visual_indexed"] = True
    meta_data["visual_indexing_status"] = "indexed"
    meta_data["visual_pages_indexed"] = bridge.count_document_pages(doc_id)
    processed_json.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 75)
    print("STEP 3: INITIALIZING RAG ORCHESTRATOR")
    print("=" * 75)
    retriever = HybridTextRetriever(
        dense_model_name="BAAI/bge-base-en-v1.5",
        qdrant_path=str(default_settings.base_dir / "qdrant_storage"),
        bm25_index_path=str(default_settings.base_dir / "bm25_index.pkl"),
    )
    crag_controller = CRAGController()
    generator = AnswerGenerator(
        GeneratorConfig(
            provider=default_settings.llm_provider,
            model_name=default_settings.ollama_model if default_settings.llm_provider == "ollama" else default_settings.gemini_model,
            base_url=default_settings.ollama_base_url,
            temperature=default_settings.llm_temperature,
            max_tokens=default_settings.llm_max_tokens,
            fallback_to_mock=True,
        )
    )

    orchestrator = RAGOrchestrator(
        config=OrchestratorConfig(enable_crag=True),
        retriever=retriever,
        visual_bridge=bridge,
        crag_controller=crag_controller,
        generator=generator,
    )
    print("Orchestrator ready. Active generator provider:", generator.active_provider)

    print("\n" + "=" * 75)
    print("STEP 4: RUNNING COMPREHENSIVE TEST QUERIES")
    print("=" * 75)

    test_queries = [
        ("Summarize Support Vector Classifier from the slides", "High-level summary of the entire document"),
        ("What is the margin in Support Vector Classifier?", "Specific concept on Page 1 & 2"),
        ("What are support vectors and how do they relate to the hyperplane?", "Core mechanism on Page 1 & 2"),
        ("What is the recipe for chocolate cake?", "Negative out-of-domain query (Anti-hallucination test)"),
    ]

    for q_idx, (q_text, description) in enumerate(test_queries, 1):
        print(f"\n[{q_idx}/4] QUERY: \"{q_text}\"")
        print(f"Goal: {description}")
        print("-" * 75)

        req = QueryRequest(
            query=q_text,
            document_ids=[doc_id],
            top_k=5,
            enable_crag=True,
            model_modality=None,
        )

        t_query_start = time.time()
        resp = await orchestrator.query(req)
        q_elapsed = time.time() - t_query_start

        print(f"CRAG Decision          : {resp.crag_decision}", flush=True)
        print(f"Confidence Score       : {resp.confidence_score:.3f}", flush=True)
        print(f"Insufficient Evidence  : {resp.insufficient_evidence}", flush=True)
        print(f"Retrieval Attempts     : {resp.retrieval_attempts}", flush=True)
        print(f"Total Latency          : {q_elapsed:.2f}s (Breakdown: ret={resp.latency.retrieval_ms:.0f}ms, crag={resp.latency.crag_ms:.0f}ms, gen={resp.latency.generation_ms:.0f}ms)", flush=True)
        print(f"Citations / Sources    : {len(resp.sources)}", flush=True)
        for src in resp.sources:
            print(f"   [{src.evidence_id}] Page {src.page} ({src.type}): {src.document} (score={src.score:.3f})", flush=True)
        print(f"Visual Inputs Sent     : {resp.visual_inputs}", flush=True)
        print("\nGENERATED ANSWER:", flush=True)
        print(resp.answer, flush=True)
        print("=" * 75, flush=True)

if __name__ == "__main__":
    asyncio.run(run_svm_evaluation())
