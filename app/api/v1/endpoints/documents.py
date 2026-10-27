"""documents.py — FastAPI endpoints for document ingestion, cataloging, and deletion."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import (
    get_duplicate_detector,
    get_pipeline,
    get_retriever,
    get_settings,
    get_visual_bridge,
)
from app.config import Settings
from app.schemas.api import (
    DeleteResponse,
    DocumentDetailResponse,
    DocumentSummary,
    DocumentUploadResponse,
)
from app.services.duplicate_detector import DuplicateDetector
from app.services.pipeline import DocumentProcessingPipeline
from app.services.retrieval_bridge import index_colpali_pages, index_document_chunks

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB bound
STREAM_CHUNK_SIZE_BYTES = 1024 * 1024       # 1 MB streaming chunks

router = APIRouter()


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Ingest PDF Document",
    description=(
        "Uploads a PDF, verifies header integrity, checks duplicate cache, extracts structured text "
        "and tables, renders 150 DPI page images, and performs dual dense/sparse and ColPali indexing."
    ),
)
async def upload_document(
    file: UploadFile = File(..., description="PDF document file to process"),
    force: bool = Form(False, description="Force re-extraction and re-indexing even if already cached"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    settings: Settings = Depends(get_settings),
    pipeline: DocumentProcessingPipeline = Depends(get_pipeline),
    duplicate_detector: DuplicateDetector = Depends(get_duplicate_detector),
    retriever: Optional[Any] = Depends(get_retriever),
    visual_bridge: Optional[Any] = Depends(get_visual_bridge),
) -> DocumentUploadResponse:
    """Ingest, extract, chunk, render, and index an uploaded PDF."""
    # 1. Filename validation & path traversal check (Fix 5)
    raw_filename = file.filename or ""
    if ".." in raw_filename or "/" in raw_filename or "\\" in raw_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename contains invalid directory traversal sequences ('..', '/', '\\').",
        )

    safe_filename = Path(raw_filename).name
    if not safe_filename or not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a PDF document (.pdf).",
        )

    # 2. Stream content and validate size & magic bytes in 1 MB chunks (Fix 4)
    uploads_dir = settings.get_uploads_path()
    temp_upload_path = uploads_dir / f"upload_{uuid.uuid4().hex}.tmp"
    hasher = hashlib.sha256()
    total_bytes = 0
    first_chunk = True

    try:
        with temp_upload_path.open("wb") as out_f:
            while True:
                chunk = await file.read(STREAM_CHUNK_SIZE_BYTES)
                if not chunk:
                    break

                if first_chunk:
                    first_chunk = False
                    if not chunk.startswith(b"%PDF-"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid PDF format: file lacks %PDF header bytes.",
                        )

                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE_BYTES:
                    http_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)
                    raise HTTPException(
                        status_code=http_413,
                        detail="Uploaded file exceeds maximum limit of 100 MB.",
                    )

                hasher.update(chunk)
                out_f.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )

        content_hash = hasher.hexdigest()
        doc_id = f"doc_{content_hash[:16]}"
        saved_pdf_path = uploads_dir / f"{doc_id}_{safe_filename}"

        # Collision-free atomic placement (Fix 5)
        if saved_pdf_path.exists():
            temp_upload_path.unlink(missing_ok=True)
        else:
            temp_upload_path.replace(saved_pdf_path)

    except HTTPException:
        temp_upload_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temp_upload_path.unlink(missing_ok=True)
        logger.error("Failed to read/save uploaded file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(exc)}",
        )

    # 3. Duplicate Check
    is_dup, doc_id, cached_json = duplicate_detector.check_duplicate(saved_pdf_path)
    if is_dup and not force:
        logger.info("Duplicate document detected: %s (ID: %s)", safe_filename, doc_id)
        page_count = 0
        chunk_count = 0
        image_count = 0

        if cached_json and cached_json.exists():
            try:
                cached_data = json.loads(cached_json.read_text(encoding="utf-8"))
                page_count = cached_data.get("metadata", {}).get("page_count", 0)
                chunk_count = cached_data.get("total_chunks", 0)
                image_count = len(cached_data.get("rendered_pages", []))
            except Exception as e:
                logger.warning("Could not parse cached JSON %s: %s", cached_json, e)

        return DocumentUploadResponse(
            document_id=doc_id,
            filename=safe_filename,
            status="cached",
            page_count=page_count,
            chunk_count=chunk_count,
            image_count=image_count,
            message="Document already indexed. Use force=true to re-process and re-index.",
        )

    # 4. Execute extraction, chunking, and rendering pipeline (Fix 8: 400 error mapping)
    try:
        output = pipeline.process_file(saved_pdf_path, force_reprocess=force)
    except (ValueError, RuntimeError) as exc:
        logger.warning("Document extraction failed with format error for %s: %s", safe_filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or corrupted PDF document: {str(exc)}",
        )
    except Exception as exc:
        logger.error("Pipeline process_file raised unexpected exception: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing failed: {str(exc)}",
        )

    if output.status == "failed":
        logger.warning("Document extraction failed for %s: %s", safe_filename, output.error_message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or corrupted PDF document: {output.error_message}",
        )

    # 5. Dual Downstream Indexing
    try:
        indexed_chunks = index_document_chunks(output.chunks, retriever=retriever)
    except Exception as exc:
        logger.warning("Downstream text chunk indexing encountered non-fatal error: %s", exc)
        indexed_chunks = len(output.chunks)

    # Dispatch ColPali visual indexing as background task so HTTP upload returns immediately
    if visual_bridge is not None and getattr(visual_bridge, "enabled", False) and output.rendered_pages:
        logger.info(
            "Scheduling background ColPali visual indexing for %d page(s) of document '%s'.",
            len(output.rendered_pages),
            output.document_id,
        )
        background_tasks.add_task(
            index_colpali_pages,
            rendered_pages=output.rendered_pages,
            document_id=output.document_id,
            source_filename=safe_filename,
            colpali_bridge=visual_bridge,
            qdrant_url=settings.qdrant_url,
        )
    else:
        logger.info("ColPali visual indexing skipped (bridge disabled or no pages rendered).")

    return DocumentUploadResponse(
        document_id=output.document_id,
        filename=safe_filename,
        status="indexed",
        page_count=output.metadata.page_count,
        chunk_count=output.total_chunks,
        image_count=len(output.rendered_pages),
        message=f"Successfully indexed {output.total_chunks} chunks and rendered {len(output.rendered_pages)} pages (ColPali visual indexing running in background).",
    )


@router.get(
    "",
    response_model=List[DocumentSummary],
    summary="List All Indexed Documents",
    description="Returns a catalog of all documents currently indexed in the knowledge base.",
)
def list_documents(
    settings: Settings = Depends(get_settings),
    duplicate_detector: DuplicateDetector = Depends(get_duplicate_detector),
) -> List[DocumentSummary]:
    """Retrieve catalog list of indexed documents."""
    manifest = duplicate_detector._load_manifest()
    processed_dir = settings.get_processed_path()
    summaries: List[DocumentSummary] = []
    seen_ids = set()

    # 1. From manifest
    for doc_id, item in manifest.items():
        seen_ids.add(doc_id)
        output_json = processed_dir / f"{doc_id}.json"
        is_scanned = False
        ocr_needed = False
        status_val = item.get("status")
        page_count = 0
        file_size = None
        timestamp = None

        if output_json.exists():
            try:
                data = json.loads(output_json.read_text(encoding="utf-8"))
                meta = data.get("metadata", {})
                page_count = meta.get("page_count", 0)
                file_size = meta.get("file_size_bytes")
                timestamp = meta.get("upload_timestamp")
                is_scanned = data.get("is_scanned", False)
                ocr_needed = data.get("ocr_needed", False)
                status_val = data.get("status", status_val)
            except Exception:
                pass

        summaries.append(
            DocumentSummary(
                document_id=doc_id,
                filename=item.get("document_name", "unknown.pdf"),
                page_count=page_count,
                chunk_count=item.get("total_chunks", 0),
                upload_timestamp=timestamp,
                file_size_bytes=file_size,
                is_scanned=is_scanned,
                ocr_needed=ocr_needed,
                status=status_val,
            )
        )

    # 2. From processed_dir files not in manifest
    if processed_dir.exists():
        for json_file in processed_dir.glob("*.json"):
            if json_file.name == "processed_manifest.json":
                continue
            doc_id = json_file.stem
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                meta = data.get("metadata", {})
                summaries.append(
                    DocumentSummary(
                        document_id=doc_id,
                        filename=meta.get("document_name", json_file.name),
                        page_count=meta.get("page_count", 0),
                        chunk_count=data.get("total_chunks", len(data.get("chunks", []))),
                        upload_timestamp=meta.get("upload_timestamp"),
                        file_size_bytes=meta.get("file_size_bytes"),
                        is_scanned=data.get("is_scanned", False),
                        ocr_needed=data.get("ocr_needed", False),
                        status=data.get("status"),
                    )
                )
            except Exception:
                continue

    return summaries


@router.get(
    "/{doc_id}",
    response_model=DocumentDetailResponse,
    summary="Get Document Details & Manifest",
    description="Returns detailed processing output, chunk count, and page image paths for a document.",
)
def get_document_detail(
    doc_id: str,
    settings: Settings = Depends(get_settings),
) -> DocumentDetailResponse:
    """Retrieve detailed manifest and metadata for a specific document ID."""
    doc_json = settings.get_processed_path() / f"{doc_id}.json"
    if not doc_json.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found.",
        )

    try:
        data = json.loads(doc_json.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read document JSON: {str(exc)}",
        )

    meta = data.get("metadata", {})
    filename = data.get("document_name", meta.get("document_name", f"{doc_id}.pdf"))
    page_count = meta.get("page_count", 0)
    chunk_count = data.get("total_chunks", len(data.get("chunks", [])))

    # Discover rendered page images
    page_images_dir = settings.get_page_images_path() / doc_id
    page_images: List[str] = []
    if page_images_dir.exists():
        page_images = sorted([str(p.resolve()) for p in page_images_dir.glob("*.png")])

    return DocumentDetailResponse(
        document_id=doc_id,
        filename=filename,
        page_count=page_count,
        chunk_count=chunk_count,
        image_count=len(page_images),
        status=data.get("status", "indexed"),
        metadata=meta,
        page_images=page_images,
    )


@router.delete(
    "/{doc_id}",
    response_model=DeleteResponse,
    summary="Delete Document From Knowledge Base",
    description="Deletes document metadata, processed chunks, page images, and removes entries from vector stores.",
)
def delete_document(
    doc_id: str,
    settings: Settings = Depends(get_settings),
    duplicate_detector: DuplicateDetector = Depends(get_duplicate_detector),
    retriever: Optional[Any] = Depends(get_retriever),
    visual_bridge: Optional[Any] = Depends(get_visual_bridge),
) -> DeleteResponse:
    """Delete a document and purge all associated artifacts."""
    doc_json = settings.get_processed_path() / f"{doc_id}.json"
    manifest = duplicate_detector._load_manifest()

    if not doc_json.exists() and doc_id not in manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found.",
        )

    # 1. Unlink processed json
    if doc_json.exists():
        try:
            doc_json.unlink()
        except Exception as exc:
            logger.warning("Could not delete %s: %s", doc_json, exc)

    # 2. Remove from manifest
    if doc_id in manifest:
        del manifest[doc_id]
        duplicate_detector._save_manifest(manifest)

    # 3. Remove rendered page images directory
    page_images_dir = settings.get_page_images_path() / doc_id
    if page_images_dir.exists():
        try:
            shutil.rmtree(page_images_dir, ignore_errors=True)
        except Exception as exc:
            logger.warning("Could not delete page images dir %s: %s", page_images_dir, exc)

    # 4. Remove uploaded PDF files matching doc_id
    uploads_dir = settings.get_uploads_path()
    for matching_pdf in uploads_dir.glob(f"{doc_id}_*"):
        try:
            matching_pdf.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Could not delete uploaded PDF %s: %s", matching_pdf, exc)

    # 5. Purge from text retrieval stores (Qdrant & BM25) (Fix 6)
    if retriever is not None:
        try:
            if hasattr(retriever, "delete_document"):
                retriever.delete_document(doc_id)
            elif hasattr(retriever, "dense_engine") and hasattr(retriever.dense_engine, "delete_document"):
                retriever.dense_engine.delete_document(doc_id)
        except Exception as exc:
            logger.warning("Retriever delete_document failed for %s: %s", doc_id, exc)

    # 6. Remove from ColPali visual bridge if wired
    if visual_bridge is not None and hasattr(visual_bridge, "delete_document"):
        try:
            visual_bridge.delete_document(doc_id)
        except Exception as exc:
            logger.warning("ColPali bridge delete_document failed for %s: %s", doc_id, exc)

    return DeleteResponse(
        document_id=doc_id,
        deleted=True,
        message=f"Document '{doc_id}' deleted successfully from knowledge base.",
    )


@router.post(
    "/{doc_id}/ocr",
    summary="Run Vision OCR and Index Scanned Document",
    description="Runs fast Apple Vision OCR on rendered page images, chunks extracted text, and indexes into Qdrant & BM25.",
)
def ocr_document(
    doc_id: str,
    start_page: int = 1,
    end_page: int = 60,
    settings: Settings = Depends(get_settings),
    retriever: Optional[Any] = Depends(get_retriever),
    duplicate_detector: DuplicateDetector = Depends(get_duplicate_detector),
) -> dict:
    page_images_dir = settings.get_page_images_path() / doc_id
    if not page_images_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rendered page images for document '{doc_id}' not found.",
        )

    ocr_bin = settings.base_dir / "scripts" / "fast_ocr_bin"
    if not ocr_bin.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="fast_ocr_bin utility not compiled or missing.",
        )

    cmd = [str(ocr_bin), str(page_images_dir), str(start_page), str(end_page)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        pages_data = json.loads(proc.stdout)
    except Exception as exc:
        logger.error("OCR execution failed for %s: %s", doc_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR execution failed: {str(exc)}",
        )

    from schemas import DocumentChunk

    watermark_terms = ["books4career.blogspot.com", "copyrighted material"]
    chunks: List[DocumentChunk] = []

    for item in pages_data:
        p_num = item["page"]
        raw_text = item.get("text", "")

        clean_lines = [
            ln.strip() for ln in raw_text.splitlines()
            if ln.strip() and not any(term in ln.lower() for term in watermark_terms)
        ]
        page_clean_text = "\n".join(clean_lines).strip()
        if len(page_clean_text) < 30:
            continue

        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap
        text_len = len(page_clean_text)

        start_idx = 0
        c_sub = 0
        while start_idx < text_len:
            end_idx = min(start_idx + chunk_size, text_len)
            chunk_content = page_clean_text[start_idx:end_idx].strip()
            if chunk_content:
                cid = f"{doc_id}_p{p_num:03d}_c{c_sub:02d}"
                chunk = DocumentChunk(
                    chunk_id=cid,
                    document_id=doc_id,
                    source_filename=f"{doc_id}.pdf",
                    page_number=p_num,
                    page_start=p_num,
                    page_end=p_num,
                    text=chunk_content,
                    candidate_type="text_chunk",
                    chunk_index=len(chunks),
                    section_heading=f"Page {p_num}",
                    char_count=len(chunk_content),
                    word_count=len(chunk_content.split()),
                )
                chunks.append(chunk)
                c_sub += 1
            if end_idx >= text_len:
                break
            start_idx += (chunk_size - overlap)

    indexed_count = 0
    if retriever is not None and chunks:
        if hasattr(retriever, "delete_document"):
            retriever.delete_document(doc_id)
        indexed_count = retriever.index_knowledge_base(chunks)
        if not isinstance(indexed_count, int):
            indexed_count = len(chunks)

    doc_json = settings.get_processed_path() / f"{doc_id}.json"
    if doc_json.exists():
        try:
            d = json.loads(doc_json.read_text(encoding="utf-8"))
            d["chunks"] = [c.model_dump() for c in chunks]
            d["total_chunks"] = len(chunks)
            d["is_scanned"] = True
            d["ocr_needed"] = False
            d["status"] = "indexed_with_ocr"
            d["warnings"] = [f"OCRed {len(pages_data)} pages using Apple Vision Engine."]
            doc_json.write_text(json.dumps(d, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not update processed JSON %s: %s", doc_json, exc)

    manifest = duplicate_detector._load_manifest()
    if doc_id in manifest:
        manifest[doc_id]["total_chunks"] = len(chunks)
        manifest[doc_id]["status"] = "indexed_with_ocr"
        duplicate_detector._save_manifest(manifest)

    return {
        "document_id": doc_id,
        "pages_ocred": len(pages_data),
        "chunks_indexed": indexed_count,
        "status": "success",
        "message": f"Successfully OCRed {len(pages_data)} pages and indexed {len(chunks)} chunks into Knowledge Base.",
    }
