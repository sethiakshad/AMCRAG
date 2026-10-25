# AMCRAG Final LLM and Backend Test Report

**Scope:** Ollama Cloud LLM integration, answer generation, FastAPI orchestration, SSE, and backend regression  
**Specification used:** `backend/llm-test.md`, `backend/test.md`, and `backend/integration-plan.md`  
**Date:** 2026-10-25  
**Verdict:** **Functionally ready for a controlled first release after immediate credential rotation.** The live LLM and controlled FastAPI final-output path work. A public rollout remains conditional on live ingestion/retrieval, production security, and load validation.

## Security finding — action required before release

**Critical:** API credentials were found hard-coded in `geminiapitest.py`, `testollamaapikey.py`, and the supplied LLM test document. The values are not reproduced here.

Treat those credentials as compromised: revoke/rotate them now, remove the literals from those files and documentation, and load new keys only from a secret manager or deployment environment. `.gitignore` excludes `.env` and the standalone scripts, which helps prevent a new commit, but does not undo the exposure.

## Test environment

- Python 3.14.6, pytest 9.0.3
- Configured provider: Ollama Cloud, model `gemma4:31b`
- `OLLAMA_API_KEY` was detected without printing its value.
- The sandbox cannot directly reach Ollama Cloud. Strict provider probes were repeated with approved unrestricted network access; they reached `https://ollama.com/api/chat` successfully.

## Executed automated tests

| Command / scope | Result |
| --- | --- |
| `pytest tests/test_ollama_integration.py tests/test_api_schemas_and_generator.py tests/test_api_orchestrator.py tests/test_api_v1_endpoints.py -v` | **65 passed** in 2.76 s |
| `pytest tests/test_ollama_integration.py tests/test_orchestrator.py tests/test_main_app.py tests/test_context_builder.py tests/test_crag.py tests/test_schemas.py tests/test_person2_integration.py -v` | **89 passed** in 1.16 s |
| `pytest tests/test_api_orchestrator.py -k 'query or stream or rate_limit or concurrency or failure' -v` | **16 passed**, 20 deselected, in 1.06 s |
| Full `pytest -ra -q` | **Incomplete** in this execution channel: it reached 57% before the 30-second command limit while initializing the dense BGE retrieval fixture. No failure was observed, but this is not recorded as a full-suite pass. |

The completed test runs emitted seven non-fatal SWIG deprecation warnings.

## Strict live LLM verification

The standard live tests permit mock fallback. To prove that a passing result was not a fallback response, additional probes used `fallback_to_mock=False` and printed only non-sensitive outcome flags.

| Scenario | Result |
| --- | --- |
| Synchronous Ollama generation | Live provider remained `ollama`; non-empty answer and `[E1]` citation verified; **703.24 ms** total latency. |
| Full asynchronous token stream | Live provider remained `ollama`; **8** chunks received; non-empty reassembled answer and `[E1]` citation verified; **1,572.99 ms** total latency. |
| Time to first stream chunk | First non-empty chunk reached in **610.48 ms**. |
| FastAPI final-output path | `POST /api/v1/query` using controlled retrieved evidence and live Ollama returned **HTTP 200**, a non-empty cited answer, **1** source, and CRAG decision `CORRECT`. The upstream Ollama request returned HTTP 200. |
| Zero-evidence and fallback contracts | Covered by automated tests: deterministic insufficient-evidence response and key-free mock fallback passed. |
| Rate-limit behavior | Covered by automated tests: bounded retry/backoff, HTTP 503, `Retry-After`, and SSE error behavior passed. |

### What the FastAPI live check proves

It proves the full final-answer boundary works: validated request → retrieval result contract → CRAG approval → ContextBuilder provenance → live Ollama generation → cited `QueryResponse`.

The retriever and CRAG controller in that probe were controlled test doubles. It does **not** prove a real uploaded PDF can be ingested, embedded in a live Qdrant instance, retrieved by BGE/ColPali, and answered by Ollama in one production deployment.

## Requirement assessment

| Area | Assessment | Evidence |
| --- | --- | --- |
| Ollama credential/config routing | Pass | Config resolves the active provider and model; strict live calls retained `active_provider=ollama`. |
| Grounded standard generation | Pass | Strict live answer contained `[E1]`; live FastAPI response contained `[E1]` and a matching source. |
| Streaming generation | Pass for full consumption | Eight strict live chunks and citation returned in 1.57 s; SSE contract tests pass. |
| Vision/text resilience | Pass at integration-test level | `test_live_ollama_multimodal_vision_resilience` passes, including text-only fallback behavior. |
| Hallucination prevention on no evidence | Pass | Deterministic safe-halt tests pass; generator bypasses provider call on insufficient evidence. |
| CRAG bounded retries and timeouts | Pass at controlled-test level | Query/stream parity, cycle control, rate-limit, and CRAG timeout tests pass. |
| Upload safety and deletion cleanup | Pass at controlled-test level | 100 MB limit, traversal rejection, corrupt-PDF error mapping, collisions, and store purge tests pass. |
| Real ingestion → live retrieval → live answer | Not yet proven | Tests use controlled upstream services at the final FastAPI boundary; BGE full-suite fixture did not finish in this channel. |
| Whole-suite regression | Not independently completed in this session | Full suite hit the runner's 30-second cap during dense BGE initialization. |

## Observations and remaining risks

1. **Rotate credentials before any release.** This is the release-blocking issue.
2. **Run a production-like E2E smoke test:** upload a real PDF, wait for dense/sparse/visual indexing, query it through live Qdrant/BGE and Ollama, and verify citation/page alignment.
3. **Complete the BGE/Qdrant regression** in an environment that allows model initialization (or has the model pre-cached). Record its exit result.
4. **Validate real concurrency and SLAs:** 50 simultaneous—not merely 50 queued—clients, 10 simultaneous uploads, 1,000-query memory soak, p95 latency, and streaming TTFT.
5. **Perform a browser/client-disconnect SSE test.** A deliberately interrupted one-chunk SDK probe emitted an async-generator close warning; full-stream consumption completed cleanly. Confirm that real cancellation does not leave a provider request or warning behind.
6. **Production controls remain necessary:** API authentication/authorization, rate/usage limits, secret manager integration, structured monitoring/alerts, backups, and rollback procedures.

## Release recommendation

After credential rotation, this backend is suitable for a **restricted first release** (internal users or an allow-listed beta) with monitoring and request limits. Do not make it publicly available until the live ingestion/retrieval E2E test, full BGE/Qdrant suite, production load measurements, and access-control controls are complete.
