"""test_comparison.py — Unit and integration tests for RAG comparison evaluation and metrics."""

import pytest
from app.comparison.evaluator import RAGEvaluator
from app.comparison.pipeline import ComparisonPipeline
from app.comparison.schemas import EvaluationQuestion, PipelineOutput


def test_answer_correctness_exact_and_f1():
    # 1. Exact match
    score = RAGEvaluator.evaluate_answer_correctness(
        candidate_answer="Meghraj Mahajan's MIS Number is 112415118.",
        reference_answer="Meghraj Mahajan's MIS Number is 112415118.",
    )
    assert score == 1.0

    # 2. Partial match
    score_partial = RAGEvaluator.evaluate_answer_correctness(
        candidate_answer="The MIS is 112415118.",
        reference_answer="Meghraj Mahajan's MIS Number is 112415118.",
    )
    assert score_partial is not None
    assert 0.4 < score_partial < 1.0

    # 3. Completely unrelated
    score_zero = RAGEvaluator.evaluate_answer_correctness(
        candidate_answer="The weather is sunny in Paris today.",
        reference_answer="Meghraj Mahajan's MIS Number is 112415118.",
    )
    assert score_zero == 0.0

    # 4. Missing reference answer (Rule 5: display N/A / None)
    assert RAGEvaluator.evaluate_answer_correctness("Some answer", None) is None
    assert RAGEvaluator.evaluate_answer_correctness("Some answer", "") is None


def test_unanswerable_refusal_handling():
    # Both agree on insufficient evidence -> 1.0
    ref_refusal = "Based on the provided documents, there is insufficient evidence to answer your question."
    cand_refusal = "There is insufficient evidence in the document to answer this query."
    score = RAGEvaluator.evaluate_answer_correctness(cand_refusal, ref_refusal)
    assert score == 1.0

    # Model hallucinated on unanswerable query -> 0.0
    cand_hallucination = "The cost is $45.50 per hour on Google Cloud."
    score_hallucinated = RAGEvaluator.evaluate_answer_correctness(cand_hallucination, ref_refusal)
    assert score_hallucinated == 0.0


def test_faithfulness_grounding():
    evidence = [
        {"text": "Meghraj Mahajan MIS is 112415118 Section A Group 3."},
    ]
    # Grounded answer
    grounded_ans = "Meghraj Mahajan MIS 112415118."
    f_score = RAGEvaluator.evaluate_faithfulness(grounded_ans, evidence)
    assert f_score == 1.0

    # Ungrounded fabricated entities
    invented_ans = "Meghraj Mahajan was born in Tokyo Japan in 1990."
    f_invented = RAGEvaluator.evaluate_faithfulness(invented_ans, evidence)
    assert f_invented < 0.5


def test_retrieval_metrics_with_and_without_ground_truth():
    evidence = [
        {"text": "Intro and cloud overview", "page": 1},
        {"text": "Team details and student IDs", "page": 2},
        {"text": "Gap analysis and benchmarks", "page": 3},
    ]

    # Case A: Ground truth page label provided (page 2 is relevant)
    rec1, rec3, rec5, mrr, ndcg = RAGEvaluator.evaluate_retrieval_metrics(
        expected_pages=[2],
        expected_keywords=None,
        retrieved_evidence=evidence,
    )
    assert rec1 == 0.0  # page 1 is at rank 1, so not at rank 1
    assert rec3 == 1.0  # page 2 is at rank 2, so in top 3
    assert rec5 == 1.0
    assert mrr == 0.5   # 1 / 2 = 0.5
    assert ndcg > 0.0

    # Case B: NO ground truth relevance labels provided (Rule 5: must return None / N/A)
    rec1_na, rec3_na, rec5_na, mrr_na, ndcg_na = RAGEvaluator.evaluate_retrieval_metrics(
        expected_pages=None,
        expected_keywords=None,
        retrieved_evidence=evidence,
    )
    assert rec1_na is None
    assert rec3_na is None
    assert rec5_na is None
    assert mrr_na is None
    assert ndcg_na is None


def test_context_precision_and_recall():
    evidence = [
        {"text": "Meghraj Mahajan MIS 112415118 Section A Group 3"},
        {"text": "Unrelated paragraph about cloud servers"},
    ]
    prec = RAGEvaluator.evaluate_context_precision(
        question="What is Meghraj MIS?",
        reference_answer="112415118",
        retrieved_evidence=evidence,
    )
    assert prec == 1.0  # First rank is relevant

    rec = RAGEvaluator.evaluate_context_recall(
        reference_answer="112415118",
        retrieved_evidence=evidence,
    )
    assert rec == 1.0

    assert RAGEvaluator.evaluate_context_recall(None, evidence) is None


def test_preset_benchmark_questions_coverage():
    questions = ComparisonPipeline.get_preset_questions()
    assert len(questions) >= 4

    categories = {q.category for q in questions}
    assert "factual" in categories
    assert "multihop" in categories
    assert "visual_table" in categories
    assert "unanswerable" in categories

    for q in questions:
        assert q.question
        assert q.id
