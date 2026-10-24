# Context Builder Robustness Test Report — Revalidation

**Run date:** 2026-10-24  
**Scope:** `app/context_builder/test.md`, `app/context_builder/`, and the declared CRAG/schema regression tests.  
**Certification result:** **PASS — all documented, numbered robustness requirements are met.**

## Summary

| Validation layer | Result | Notes |
| --- | --- | --- |
| Context Builder suite | **45/45 passed** | 40 existing tests plus five robustness-audit tests. |
| CRAG and schema regressions | **22/22 passed** | `tests/test_crag.py` and `tests/test_schemas.py`. |
| Direct numbered scenarios | **22/22 passed** | Every currently numbered `test.md` case (1.1–7.2). |
| Supplemental parameter sweep | **25/25 passed** | All documented stress values and modality/grouping combinations. |

`test.md` claims 25 stress scenarios but defines 22 numbered cases. Every numbered case was run; the parameter sweep is recorded separately.

## Environment and measurement boundaries

| Item | Value |
| --- | --- |
| Runtime | macOS; `/opt/anaconda3/bin/python` 3.14.6; pytest 9.0.3 |
| Libraries | Pydantic 2.13.4; pydantic-settings 2.14.2 |
| Token counting | `heuristic` backend; neither `tiktoken` nor a usable Transformers tokenizer is installed |
| Latency method | Warm sequential executions; reported figure is maximum observed, not a statistical production p99 |
| Memory method | `tracemalloc` around `build()` after input creation; incremental Python allocations, not process RSS |

No production implementation file was changed during this test pass; this report reflects the current source state.

## Core reliability metrics

| Metric | Observed | Target | Result |
| --- | ---: | ---: | --- |
| Crash-Free Ingestion Rate | 22/22 direct scenarios (100%) | 100% | Pass |
| Provenance Preservation Rate | 2/2 rendered evidence labels exactly map to `E1`/`E2` sources | 100% | Pass |
| Omission Transparency Rate | 3/3 excluded candidates recorded under micro-budget pressure | 100% | Pass |
| Same-Page Preservation Rate | 20/20 distinct passages retained | 100% | Pass |
| Concurrency isolation | 50/50 shared-builder requests correct and isolated | 100% | Pass |

## Numbered robustness scenarios

| Scenario | Result | Observed evidence |
| --- | --- | --- |
| 1.1 Null and empty input | Pass | `None`, `""`, `[]`, `{}`, and `[None, None]` returned clean empty responses. |
| 1.2 Corrupted page numbers | Pass | Five malformed values, including `float("inf")`, normalized to `None`; no candidate was dropped. |
| 1.3 Unicode, emoji, null byte | Pass | Hebrew, Arabic, Cyrillic, Chinese, emoji, newline, and `\x00` were preserved verbatim. |
| 1.4 Polymorphic input | Pass | Model candidate, raw dict, and nested legacy `selected_evidence` normalized correctly. |
| 2.1 Micro-budget overflow | Pass | Zero items included; all three IDs were recorded as omitted; query and instruction remained. |
| 2.2 128k budget / 500 candidates | Pass | 500/500 included; maximum of seven warm runs: **3.290 ms**. |
| 2.3 Giant-item overflow | Pass | `e1` and later `e3` included; oversized `e2` omitted without stopping evaluation. |
| 3.1 Identical-ID flood | Pass | 100 duplicates collapsed to the lowest-rank item (rank 1). |
| 3.2 Equivalent-text flood | Pass | 50 case/whitespace variants collapsed to one item. |
| 3.3 Same-page distinct chunks | Pass | 20/20 distinct page-12 passages retained. |
| 3.4 Redundant visual-page flood | Pass | Ten duplicate visual references collapsed to one. |
| 4.1 Grouped document/page order | Pass | `B: 2 → 5 → 22`, then `A: 3 → 15`. |
| 4.2 Missing-page order | Pass | Numeric pages precede missing pages: `2, 5, None, None`. |
| 4.3 Evidence cap | Pass | `max_evidence_items=4` retained exactly the top four. |
| 5.1 Text-mode image suppression | Pass | Ten visual candidates yielded no `visual_inputs`; captions remained and `image_ref` was removed. |
| 5.2 Bare visual fallback | Pass | Exact non-hallucinatory fallback placeholder emitted. |
| 5.3 Vision input resolution | Pass | Five image paths retained in order and represented by `Visual input:` labels. |
| 6.1 Citation mapping | Pass | `[E1]` and `[E2]` map one-to-one to source IDs `E1` and `E2`. |
| 6.2 Grounding constraints | Pass | Only-evidence, citation, insufficiency/contradiction, and no-hallucination directives present. |
| 6.3 CRAG strips | Pass | Strips render first under `Key Extracted Strips:` before full context. |
| 7.1 10,000-candidate load | Pass | **53.565 ms** maximum across seven uninstrumented warm runs; **19.645 MiB** allocation peak; 967 items fit the 32,768-token budget. |
| 7.2 50-thread concurrency | Pass | Shared builder produced 50 correct request-specific responses; no state leakage observed. |

## Performance and capacity

| Workload | Observed | SLA | Result |
| --- | ---: | ---: | --- |
| 10 candidates, 4,096-token budget | 0.082 ms maximum across 30 warm runs | <5 ms p99 | Pass |
| 500 candidates, 131,072-token budget | 3.290 ms maximum across 7 warm runs | <20 ms | Pass |
| 10,000 candidates, 32,768-token budget | 53.565 ms maximum across 7 warm runs | <250 ms | Pass |
| 10,000 candidates, incremental allocation peak | 19.645 MiB | <20 MiB | Pass, 0.355 MiB headroom |

The traced scale invocation took 348.115 ms. It is not used for the latency SLA because allocation tracing changes runtime; it is used only for the memory figure.

## Parameter-matrix sweep

Each sweep case completed without exceptions and fully accounted for included plus omitted IDs.

| Dimension | Values exercised | Result |
| --- | --- | --- |
| `token_budget` | 0, 50, 500, 4,096, 32,768, 128,000 | 6/6 pass |
| `evidence_count` | 0, 1, 5, 50, 500, 2,000, 10,000 | 7/7 pass |
| `distinct_documents` | 1, 5, 25, 100 | 4/4 pass |
| `content_length` | 0, 1, 500, 50,000 characters | 4/4 pass |
| model modality × grouping | Text/Vision × grouped/ungrouped | 4/4 pass |

## Reproducibility

Executed from the repository root:

```bash
/opt/anaconda3/bin/pytest tests/test_context_builder.py -v -rA
/opt/anaconda3/bin/pytest tests/test_crag.py tests/test_schemas.py -v -rA
```

```text
tests/test_context_builder.py: 45 passed in 0.06s
tests/test_crag.py + tests/test_schemas.py: 22 passed in 0.03s
```

The requested coverage command was also attempted. It cannot run in this environment: pytest lacks the `pytest-cov` plugin and `/opt/anaconda3/bin/python -m coverage` reports no installed `coverage` module. No dependencies were changed.

## Current fix validation

1. Non-finite page values degrade to `None` instead of dropping evidence.
2. Nested `selected_evidence`, `accepted_candidates`, and `candidates` envelopes flatten during normalization.
3. Deduplication chooses the best-ranked candidate before restoring source order.
4. CRAG strips are budgeted and rendered before full source text.
5. Budget enforcement short-circuits only after recording every remaining ID as omitted.

## Guidance for follow-up agents

- Keep the direct 10,000-candidate benchmark in CI: 19.645 MiB passes but is close to the 20 MiB allocation limit.
- Add `pytest-cov` if coverage is a release gate.
- Pin `tiktoken` or the generator’s exact tokenizer before treating heuristic token estimates as model-exact.
- Use a larger repeated benchmark sample or dedicated runner before making a true p99 claim.

