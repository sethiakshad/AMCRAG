"""CRAG Correction Benchmark for AMCRAG.

Follows Sections 2.3, 6.1, 9 (Experiments), 11, and 17 of AMCRAG Central Project Documentation.
Measures:
1. Evaluator decision distribution (CORRECT, AMBIGUOUS, INCORRECT)
2. Correction recovery rate (fraction of poor initial retrievals recovered after query reformulation)
3. Stopping / Hallucination prevention rate (fraction of unrecoverable cases safely flagged)
4. Runtime latency overhead per evaluation
"""

import json
import os
import sys
import time
from typing import Any

# Ensure repository root is in python path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.crag.controller import CRAGController
from app.crag.decisions import DecisionConfig
from app.crag.evaluator import HeuristicCRAGEvaluator
from app.schemas.crag import AmbiguousPolicy
from app.schemas.retrieval import RetrievalCandidate


# Benchmark test dataset representing diverse retrieval scenarios
BENCHMARK_SCENARIOS = [
    {
        "id": "bench_01_prose_good",
        "query": "What was the company's operating profit margin in 2024?",
        "initial_candidates": [
            RetrievalCandidate(
                candidate_id="c_01_a",
                document_id="doc_fin_2024",
                source_filename="financials_2024.pdf",
                candidate_type="text_chunk",
                text="In 2024, the company recorded an operating profit margin of 18.4%, up 210 bps.",
                retrieval_method="dense",
                retrieval_score=0.92,
            )
        ],
        "expected_initial_label": "CORRECT",
        "can_recover": True,
        "recovered_candidates": [],
    },
    {
        "id": "bench_02_visual_good",
        "query": "Which figure compares the latency across models?",
        "initial_candidates": [
            RetrievalCandidate(
                candidate_id="c_02_a",
                document_id="doc_benchmark",
                source_filename="benchmark_report.pdf",
                page_start=6,
                page_end=6,
                candidate_type="visual_page",
                page_reference="artifacts/doc_benchmark_p6.png",
                retrieval_method="colpali",
                retrieval_score=0.85,
                metadata={"caption": "Figure 4: Latency comparison across models and batch sizes"},
            )
        ],
        "expected_initial_label": "CORRECT",
        "can_recover": True,
        "recovered_candidates": [],
    },
    {
        "id": "bench_03_poor_recoverable",
        "query": "Can you explain the tokenizer vocabulary size for model B?",
        "initial_candidates": [
            # Irrelevant introduction passage retrieved initially
            RetrievalCandidate(
                candidate_id="c_03_poor",
                document_id="doc_model",
                source_filename="model_spec.pdf",
                candidate_type="text_chunk",
                text="The authors would like to acknowledge the compute support from the research lab.",
                retrieval_method="bm25",
                retrieval_score=0.15,
            )
        ],
        "expected_initial_label": "INCORRECT",
        "can_recover": True,
        # Candidate discovered after query reformulation
        "recovered_candidates": [
            RetrievalCandidate(
                candidate_id="c_03_good",
                document_id="doc_model",
                source_filename="model_spec.pdf",
                candidate_type="text_chunk",
                text="Model B utilizes a BPE tokenizer with a vocabulary size of 32,000 tokens.",
                retrieval_method="dense",
                retrieval_score=0.89,
            )
        ],
    },
    {
        "id": "bench_04_unrecoverable",
        "query": "What is the warranty policy for discontinued hardware unit X99?",
        "initial_candidates": [
            RetrievalCandidate(
                candidate_id="c_04_poor1",
                document_id="doc_hw",
                source_filename="hardware_catalog.pdf",
                candidate_type="text_chunk",
                text="General safety guidelines for operating electrical machinery.",
                retrieval_method="dense",
                retrieval_score=0.10,
            )
        ],
        "expected_initial_label": "INCORRECT",
        "can_recover": False,
        # Even after reformulation, no relevant evidence exists in the corpus
        "recovered_candidates": [
            RetrievalCandidate(
                candidate_id="c_04_poor2",
                document_id="doc_hw",
                source_filename="hardware_catalog.pdf",
                candidate_type="text_chunk",
                text="Index of product codes starting with letter A.",
                retrieval_method="dense",
                retrieval_score=0.08,
            )
        ],
    },
    {
        "id": "bench_05_ambiguous_partial",
        "query": "What are the terms of the customer SLA agreement?",
        "initial_candidates": [
            RetrievalCandidate(
                candidate_id="c_05_ambig",
                document_id="doc_sla",
                source_filename="service_terms.pdf",
                candidate_type="text_chunk",
                text="Standard enterprise service levels are governed by the operational schedule.",
                retrieval_method="dense",
                retrieval_score=0.52,
            )
        ],
        "expected_initial_label": "AMBIGUOUS",
        "can_recover": True,
        "recovered_candidates": [
            RetrievalCandidate(
                candidate_id="c_05_good",
                document_id="doc_sla",
                source_filename="service_terms.pdf",
                candidate_type="text_chunk",
                text="Customer SLA agreement guarantees 99.9% uptime with 4-hour response time.",
                retrieval_method="dense",
                retrieval_score=0.88,
            )
        ],
    },
]


def run_crag_benchmark(
    controller: CRAGController | None = None,
) -> dict[str, Any]:
    """Executes the correction benchmark suite and measures decision metrics."""
    if controller is None:
        controller = CRAGController(
            evaluator=HeuristicCRAGEvaluator(),
            decision_config=DecisionConfig(
                upper_threshold=0.65,
                lower_threshold=0.30,
                ambiguous_policy=AmbiguousPolicy.RETRY_ONCE,
            ),
        )

    results: list[dict[str, Any]] = []
    total_latency_ms = 0.0

    initial_decisions = {"CORRECT": 0, "AMBIGUOUS": 0, "INCORRECT": 0}
    recovery_attempts = 0
    recovery_successes = 0
    correctly_flagged_unrecoverable = 0

    print("=" * 70)
    print("AMCRAG Person 4: CRAG Evaluator & Correction Benchmark")
    print("=" * 70)

    for item in BENCHMARK_SCENARIOS:
        query = item["query"]
        candidates = item["initial_candidates"]
        can_recover = item["can_recover"]

        t0 = time.perf_counter()
        # Step 1: Initial evaluation (Attempt 0)
        res_0 = controller.process_candidates(query=query, candidates=candidates, attempt_number=0)
        t_elapsed = (time.perf_counter() - t0) * 1000
        total_latency_ms += t_elapsed

        initial_label = res_0.decision.label
        initial_decisions[initial_label] += 1

        final_label = initial_label
        recovered = False
        insufficient_flagged = False
        reformulated_query = res_0.reformulated_query

        # Step 2: Simulate corrective retrieval loop if correction was requested
        if res_0.decision.needs_correction:
            recovery_attempts += 1
            print(f"[{item['id']}] Correction triggered on attempt 0:")
            print(f"  Initial Query     : '{query}'")
            print(f"  Reformulated Query: '{reformulated_query}'")

            # Feed new candidate set simulated after reformulation
            new_candidates = item["recovered_candidates"]
            t1 = time.perf_counter()
            res_1 = controller.process_candidates(
                query=reformulated_query or query,
                candidates=new_candidates,
                attempt_number=1,
            )
            total_latency_ms += (time.perf_counter() - t1) * 1000
            final_label = res_1.decision.label

            if res_1.can_proceed_to_generation:
                recovery_successes += 1
                recovered = True
                print(f"  -> Successfully recovered! Final decision: {final_label}")
            else:
                # If still needs correction, simulate final attempt (Attempt 2 = Max)
                t2 = time.perf_counter()
                res_2 = controller.process_candidates(
                    query=reformulated_query or query,
                    candidates=new_candidates,
                    attempt_number=2,
                )
                total_latency_ms += (time.perf_counter() - t2) * 1000
                if res_2.insufficient_evidence:
                    insufficient_flagged = True
                    correctly_flagged_unrecoverable += 1
                    print("  -> Max retries reached: Safely flagged insufficient_evidence.")
        else:
            print(f"[{item['id']}] Initial retrieval acceptable ({initial_label}). Proceeding directly.")

        results.append(
            {
                "id": item["id"],
                "initial_label": initial_label,
                "final_label": final_label,
                "correction_triggered": res_0.decision.needs_correction,
                "recovered": recovered,
                "insufficient_evidence_flagged": insufficient_flagged,
            }
        )

    # Compute aggregate metrics
    num_queries = len(BENCHMARK_SCENARIOS)
    avg_latency = total_latency_ms / num_queries
    recovery_rate = (recovery_successes / recovery_attempts * 100) if recovery_attempts > 0 else 100.0

    summary = {
        "total_test_scenarios": num_queries,
        "initial_decision_distribution": initial_decisions,
        "correction_triggers": recovery_attempts,
        "recovery_successes": recovery_successes,
        "recovery_rate_percent": round(recovery_rate, 2),
        "hallucination_prevention_successes": correctly_flagged_unrecoverable,
        "average_evaluation_latency_ms": round(avg_latency, 2),
        "scenario_results": results,
    }

    print("-" * 70)
    print(f"Initial Decisions           : {initial_decisions}")
    print(f"Corrections Triggered       : {recovery_attempts}")
    print(f"Recovery Success Rate       : {summary['recovery_rate_percent']}%")
    print(f"Unrecoverable Safely Flagged: {correctly_flagged_unrecoverable}")
    print(f"Avg Evaluation Latency      : {summary['average_evaluation_latency_ms']} ms")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    report = run_crag_benchmark()
    os.makedirs("evaluation/reports", exist_ok=True)
    report_path = "evaluation/reports/crag_benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Benchmark report saved to: {report_path}")
