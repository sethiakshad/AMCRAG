# AMCRAG — Context Builder Robustness & Stress Testing Framework (`test.md`)

> **Module:** Person 5 — Context Builder & Grounding Subsystem  
> **Target Subsystem:** [`app/context_builder/`](file:///Users/kanishkchaurasia/Documents/AMCRAG/app/context_builder/)  
> **Purpose:** Comprehensive benchmark suite, adversarial stress tests, parameter grids, and robustness metrics to evaluate resilience against edge cases, extreme token budgets, malformed schemas, and high concurrency.

---

## 1. Executive Summary & Testing Objectives

In the AMCRAG architecture, the Context Builder sits immediately before the generative LLM. Any failure, silent truncation, hallucination of source provenance, or unhandled exception will directly compromise the user experience or crash the FastAPI backend.

This testing framework defines **8 Robustness Dimensions**, **25 Specific Stress Scenarios**, and **quantitative SLA thresholds** to prove the Context Builder's resilience.

```
[ Extreme Adversarial Inputs ]
  • Malformed / Corrupted Schemas
  • Massive / Micro Token Budgets
  • High-Collision Duplicate Floods
  • Mixed Multimodal Visual Stress
  • Concurrency & Scale Bursts
                │
                ▼
  ╔═══════════════════════════════════════╗
  ║       ROBUSTNESS BENCHMARK SUITE      ║
  ║  1. Zero-Crash Ingestion Guarantee    ║
  ║  2. 100% Provenance Traceability      ║
  ║  3. Zero Silent Truncation Guarantee  ║
  ║  4. Same-Page Preservation Guarantee  ║
  ║  5. Strict Anti-Hallucination Fallback║
  ╚═══════════════════════════════════════╝
                │
                ▼
   [ Pass / Fail SLA Certification ]
```

---

## 2. Robustness Parameters & Quantitative Metrics

### A. Parameter Configuration Matrix

| Parameter Key | Permissible Range | Stress Test Values | Target Behavior |
| :--- | :--- | :--- | :--- |
| `token_budget` | $[0, \infty)$ | `0`, `50` (micro), `500`, `4096`, `32768`, `128000` | Never crash; omit items cleanly when budget is tight. |
| `evidence_count` | $[0, 10000]$ | `0`, `1`, `5`, `50`, `500`, `2000`, `10000` | Sub-linear execution time; zero memory leak. |
| `distinct_documents` | $[0, 500]$ | `1`, `5`, `25`, `100` | Proper document grouping without scrambling page order. |
| `content_length` | $[0, 100000]$ chars | `0`, `1` char, `500` chars, `50000` chars | Handle large passages without regex/string buffer overflows. |
| `model_modality` | `TEXT`, `VISION` | `ModelModality.TEXT`, `ModelModality.VISION` | Strict separation of image paths vs textual descriptions. |
| `group_by_document` | `True`, `False` | Both modes tested across all permutations | Maintain ascending page order within grouped docs. |

### B. Core Reliability Metrics & SLAs

1. **Crash-Free Ingestion Rate ($CFR$):** Target = **$100\%$**.
   $$\text{CFR} = \frac{\text{Successful Executions}}{\text{Total Adversarial Payloads}} \times 100\%$$
2. **Provenance Preservation Rate ($PPR$):** Target = **$100\%$**.
   Every accepted passage in prompt must map to an exact entry in `sources` with correct document name and 1-indexed page.
3. **Omission Transparency Rate ($OTR$):** Target = **$100\%$**.
   $$\text{OTR} = \frac{\text{Tracked Omitted IDs in } omitted\_evidence\_ids}{\text{Total Unincluded Candidates}} \times 100\%$$
   *Zero silent truncation allowed.*
4. **Same-Page Preservation Rate ($SPPR$):** Target = **$100\%$**.
   Distinct passages sharing the exact same page number must never be discarded by deduplication.
5. **Latency SLA ($p99$):**
   * Standard batch ($N=10$ candidates, budget=4096): $< 5\text{ ms}$.
   * High-stress batch ($N=500$ candidates, budget=32768): $< 50\text{ ms}$.

---

## 3. Comprehensive Robustness Test Suites

### Suite 1: Malformed & Adversarial Schema Ingestion
*Tests the input normalizer’s ability to safely ingest corrupted, unexpected, or poisoned data structures.*

* **Test 1.1: Null & Empty Inputs**
  * Inputs: `None`, `""`, `[]`, `{}`, `[None, None]`.
  * Expected: Returns clean `ContextResponse` with empty sources, empty visual inputs, and zero crash.
* **Test 1.2: Corrupted Page Numbers**
  * Inputs: `page_start="page_twelve"`, `page_start=-99`, `page_start=0`, `page_start=float("inf")`, `page_start=None`.
  * Expected: Normalized safely to positive integers or `None` without `ValueError` or type crash.
* **Test 1.3: Unicode, Emojis & Exotic Characters**
  * Inputs: Passages containing right-to-left Hebrew/Arabic, Cyrillic, Chinese glyphs, multiline emojis (📈, 📊), and null bytes (`\x00`).
  * Expected: Accurately processed and preserved in prompt context without UTF-8 encoding failures.
* **Test 1.4: Nested & Polymorphic Payload Formats**
  * Inputs: Mixed list containing raw dicts, `RetrievalCandidate` Pydantic models, and legacy `selected_evidence` dictionaries in the same batch.
  * Expected: Unified normalization into `EvidenceItem` without type mismatches.

---

### Suite 2: Extreme Token Budget Boundaries
*Tests greedy accumulation, overhead calculation, and omission accounting under constrained and massive budgets.*

* **Test 2.1: Micro-Budget Overflow (`token_budget < fixed_overhead`)**
  * Inputs: `token_budget=20`, Query = 30 tokens, Instruction = 40 tokens.
  * Expected: Zero candidates fit; all candidates cleanly recorded in `omitted_evidence_ids`; prompt contains query and instruction without crashing.
* **Test 2.2: Massive Token Budget ($128\text{k}$ tokens)**
  * Inputs: `token_budget=131072`, $N=500$ candidates.
  * Expected: Fits all candidates; sub-20ms execution time; memory usage remains constant.
* **Test 2.3: Single Giant Passage Overflow**
  * Inputs: Budget allows 100 tokens. Candidate 1 requires 10 tokens (fits). Candidate 2 requires 500 tokens (overflows). Candidate 3 requires 15 tokens.
  * Expected: Candidate 1 is included. Candidate 2 is added to `omitted_evidence_ids`. Candidate 3 is evaluated against remaining budget.

---

### Suite 3: High-Collision Deduplication Stress
*Verifies multi-level deduplication under synthetic worst-case redundancy.*

* **Test 3.1: Identical ID Flood**
  * Inputs: 100 candidate items sharing the exact same `candidate_id="chunk_duplicate_01"`.
  * Expected: Exactly 1 item retained (the one with the highest retrieval score or lowest rank).
* **Test 3.2: Identical Text Hash with Different IDs**
  * Inputs: 50 chunks with unique IDs (`chunk_1` to `chunk_50`) but identical text: `"The net profit of the company was 5 million USD."` with varied whitespace and capitalization.
  * Expected: Exactly 1 item retained; 49 duplicate items filtered out.
* **Test 3.3: Same-Page Distinct Chunk Preservation Guarantee**
  * Inputs: 20 distinct text chunks all having `document="report.pdf"` and `page_number=12`, each containing distinct paragraphs.
  * Expected: All 20 chunks are strictly retained (0% false-positive deduplication).
* **Test 3.4: Redundant Visual Page Flood**
  * Inputs: 10 visual candidates pointing to `report.pdf` Page 5 with identical image paths.
  * Expected: Exactly 1 visual page retained.

---

### Suite 4: Structural Document Grouping & Ordering
*Tests context coherence and page continuity for LLM attention.*

* **Test 4.1: Multi-Document Disordered Page Interleaving**
  * Inputs:
    * Doc A: Page 15 (rank 2), Page 3 (rank 6)
    * Doc B: Page 22 (rank 1), Page 2 (rank 4), Page 5 (rank 8)
  * Expected (`group_by_document=True`):
    * Doc B comes first (owns rank 1): Page 2 $\rightarrow$ Page 5 $\rightarrow$ Page 22.
    * Doc A comes second (owns rank 2): Page 3 $\rightarrow$ Page 15.
* **Test 4.2: Missing Page Number Ordering**
  * Inputs: Chunks from same document where some have `page_number=None` and others have `page_number=5`.
  * Expected: Numerical pages appear first in ascending order; `None` pages append to the end of the document bucket without crashing.
* **Test 4.3: Hard Limit Capping (`max_evidence_items`)**
  * Inputs: 50 valid candidates, `max_evidence_items=4`.
  * Expected: Exactly top 4 candidates retained.

---

### Suite 5: Multimodal Modality Isolation & Fallbacks
*Ensures downstream text-only LLMs never receive raw images, and vision models receive valid inputs.*

* **Test 5.1: Text-Only Mode Image Suppression**
  * Inputs: 10 visual page candidates with local PNG references passed to `ModelModality.TEXT`.
  * Expected: `visual_inputs` is strictly empty (`[]`); `image_ref` is `None` in all items; text captions/titles are injected into the prompt body.
* **Test 5.2: Bare Visual Fallback (No Caption / No OCR)**
  * Inputs: Visual page with `content=""` and `metadata={}` under `ModelModality.TEXT`.
  * Expected: Injects fallback placeholder `[Visual content from {doc}, page {page}: no text transcript available]`; never hallucinates fake descriptions.
* **Test 5.3: Vision Mode Image Resolution**
  * Inputs: 5 visual candidates with file paths passed to `ModelModality.VISION`.
  * Expected: `visual_inputs` has all 5 paths in order; prompt text contains `Visual input: <Image from {doc}, Page {page}>`.

---

### Suite 6: Grounding Instruction & Prompt Label Alignment
*Tests anti-hallucination prompt formatting and 1-to-1 citation mapping.*

* **Test 6.1: 1-to-1 Citation Map Invariant**
  * Invariant: For every `[E{i}]` in `response.context`, `response.sources[i-1].evidence_id` must equal `"E{i}"`.
* **Test 6.2: System Grounding Constraints Presence**
  * Expected: Prompt always contains explicit directives to answer ONLY from evidence, cite source labels, and explicitly state when evidence is insufficient or contradictory.
* **Test 6.3: CRAG Strips Prioritization**
  * Inputs: Candidate with both full text and `extracted_strips=["key sentence 1", "key sentence 2"]`.
  * Expected: Extracted strips are prioritized and preserved in the structured evidence item.

---

### Suite 7: High Scale & Concurrency Stress
*Tests throughput and stability under production load.*

* **Test 7.1: 10,000 Candidates Stress Load**
  * Inputs: Stream of 10,000 candidates with varied scores, documents, and lengths.
  * Expected: Pipeline completes within $< 250\text{ ms}$; memory overhead $< 20\text{ MB}$.
* **Test 7.2: Multi-Threaded Concurrency**
  * Simulation: 50 concurrent threads calling `builder.build()` simultaneously.
  * Expected: Thread-safe execution; zero state leakage between requests.

---

## 4. Automated Robustness Test Runner Script

You can run the automated robustness benchmark suite directly from the terminal:

```bash
# Run complete unit and robustness test suite
/opt/anaconda3/bin/pytest tests/test_context_builder.py -v

# Run with coverage report
/opt/anaconda3/bin/pytest tests/test_context_builder.py --cov=app/context_builder
```

---

## 5. Certification Checklist for Production Deployment

Before promoting Context Builder to production in FastAPI:
- [x] All 40 unit and integration tests passing in `tests/test_context_builder.py`.
- [x] Zero regressions against CRAG tests (`tests/test_crag.py`) and schemas (`tests/test_schemas.py`).
- [x] 1-to-1 citation mapping invariant holds for all prompt generations.
- [x] Same-page preservation guarantee verified (no dropping distinct passages on same page).
- [x] Vision mode vs. Text-only mode cleanly isolated.
- [x] Omission tracking verified: zero silent truncation under token budget pressure.
- [x] Graceful degradation on corrupted or missing metadata fields.
