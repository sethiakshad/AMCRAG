"""
Test script to ingest and evaluate sample/6-Support+Vector+Classifier.pdf
end-to-end through AMCRAG's visual pipeline.
"""

import sys
import time
import json
from pathlib import Path
import requests

BASE_URL = "http://localhost:8000/api/v1"
PDF_PATH = Path("sample/6-Support+Vector+Classifier.pdf")

def main():
    if not PDF_PATH.exists():
        print(f"ERROR: {PDF_PATH} does not exist!", flush=True)
        sys.exit(1)

    print(f"=== 1. UPLOADING {PDF_PATH.name} ({PDF_PATH.stat().st_size:,} bytes) ===", flush=True)
    with open(PDF_PATH, "rb") as f:
        files = {"file": (PDF_PATH.name, f, "application/pdf")}
        resp = requests.post(f"{BASE_URL}/documents", files=files, timeout=60)

    if resp.status_code not in (200, 201):
        print(f"Upload failed: {resp.status_code} - {resp.text}", flush=True)
        sys.exit(1)

    upload_data = resp.json()
    doc_id = upload_data["document_id"]
    page_count = upload_data["page_count"]
    chunk_count = upload_data["chunk_count"]
    print(f"Uploaded successfully!", flush=True)
    print(f"  Document ID : {doc_id}", flush=True)
    print(f"  Pages       : {page_count}", flush=True)
    print(f"  Text Chunks : {chunk_count}", flush=True)
    print(f"  Message     : {upload_data.get('message')}", flush=True)

    print("\n=== 2. CHECKING COLPALI VISUAL INDEXING STATUS ===", flush=True)
    status_resp = requests.get(f"{BASE_URL}/documents/{doc_id}/visual-status", timeout=10)
    st = status_resp.json() if status_resp.status_code == 200 else {}
    v_indexed = st.get("visual_indexed", False)
    v_pages = st.get("visual_pages_indexed", 0)
    img_count = st.get("image_count", 0)

    print(f"Initial status: visual_indexed={v_indexed}, pages_indexed={v_pages}/{img_count}", flush=True)

    if not v_indexed or v_pages < img_count:
        print(f"\nTriggering ColPali visual indexing for {img_count} pages...", flush=True)
        t0 = time.time()
        idx_resp = requests.post(f"{BASE_URL}/documents/{doc_id}/index-visual", timeout=600)
        elapsed = time.time() - t0
        print(f"Visual indexing finished in {elapsed:.1f}s:", idx_resp.status_code, idx_resp.text, flush=True)

    # Re-verify final status
    status_resp = requests.get(f"{BASE_URL}/documents/{doc_id}/visual-status", timeout=10)
    st = status_resp.json()
    print(f"Final status: visual_indexed={st.get('visual_indexed')}, pages_indexed={st.get('visual_pages_indexed')}/{st.get('image_count')}", flush=True)

    print("\n=== 3. RUNNING TEST QUERIES ===", flush=True)
    queries = [
        "Summarize Support Vector Classifier from the slides",
        "What is the margin in Support Vector Classifier?",
        "What are support vectors and how do they relate to the hyperplane?",
        "What is the recipe for chocolate cake?",  # Negative out-of-domain check
    ]

    for q in queries:
        print(f"\n" + "="*70, flush=True)
        print(f"QUERY: {q}", flush=True)
        print("="*70, flush=True)
        t_start = time.time()
        q_payload = {"query": q, "document_ids": [doc_id]}
        q_resp = requests.post(f"{BASE_URL}/query", json=q_payload, timeout=120)
        q_elapsed = time.time() - t_start

        if q_resp.status_code != 200:
            print(f"Query error: {q_resp.status_code} - {q_resp.text}", flush=True)
            continue

        res = q_resp.json()
        print(f"CRAG Decision        : {res.get('crag_decision')}", flush=True)
        print(f"Insufficient Evidence: {res.get('insufficient_evidence')}", flush=True)
        print(f"Retrieval Attempts   : {res.get('retrieval_attempts')}", flush=True)
        print(f"Latency              : {q_elapsed:.2f}s (server: {res.get('latency', {}).get('total_ms', 0):.0f}ms)", flush=True)
        print(f"Sources ({len(res.get('sources', []))}):", flush=True)
        for s in res.get("sources", []):
            print(f"  - [{s.get('evidence_id')}] Page {s.get('page')}: {s.get('document')} ({s.get('type')})", flush=True)
        print(f"Visual Inputs        : {res.get('visual_inputs', [])}", flush=True)
        print("\nANSWER:", flush=True)
        print(res.get("answer"), flush=True)

if __name__ == "__main__":
    main()
