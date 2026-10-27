/**
 * src/types/comparison.ts
 * Type definitions for RAG comparative evaluation benchmarking dashboard.
 */

export type QuestionCategory = 'factual' | 'multihop' | 'visual_table' | 'unanswerable';

export interface EvaluationQuestion {
  id: string;
  question: string;
  category: QuestionCategory;
  reference_answer?: string | null;
  expected_pages?: number[] | null;
  expected_keywords?: string[] | null;
}

export interface EvidenceItem {
  label?: string;
  text: string;
  page?: number;
  source_filename?: string;
  score?: number;
  rank?: number;
}

export interface PipelineOutput {
  system: 'amcrag' | 'normal_rag';
  answer: string;
  retrieved_evidence: EvidenceItem[];
  source_pages: number[];
  retrieval_latency_ms: number;
  generation_latency_ms: number;
  total_latency_ms: number;
  token_usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  } | null;
  error?: string | null;
  was_corrected?: boolean;
  requires_multimodal?: boolean;
  stages_executed?: string[];
}

export interface MetricScores {
  answer_correctness?: number | null;
  faithfulness?: number | null;
  answer_relevancy?: number | null;
  context_precision?: number | null;
  context_recall?: number | null;
  recall_at_1?: number | null;
  recall_at_3?: number | null;
  recall_at_5?: number | null;
  mrr?: number | null;
  ndcg_at_5?: number | null;
}

export interface ComparedQuestionResult {
  question_id: string;
  question: string;
  category: QuestionCategory;
  reference_answer?: string | null;
  expected_pages?: number[] | null;
  amcrag_output: PipelineOutput;
  normal_rag_output: PipelineOutput;
  amcrag_metrics: MetricScores;
  normal_rag_metrics: MetricScores;
  is_correct_amcrag?: boolean;
  is_correct_normal?: boolean;
  has_identical_evidence?: boolean;
  amcrag_stages_executed?: string[];
  normal_stages_executed?: string[];
  failure_analysis?: string | null;
}

export interface AggregateQualityMetrics {
  mean_answer_correctness?: number | null;
  mean_faithfulness?: number | null;
  mean_answer_relevancy?: number | null;
  mean_context_precision?: number | null;
  mean_context_recall?: number | null;
  recall_at_1?: number | null;
  recall_at_3?: number | null;
  recall_at_5?: number | null;
  mrr?: number | null;
}

export interface PerformanceMetrics {
  mean_latency_ms: number;
  median_latency_ms: number;
  mean_retrieval_latency_ms: number;
  mean_generation_latency_ms: number;
  mean_tokens_per_question: number;
  estimated_cost_usd?: number | null;
}

export interface CategoryBreakdown {
  category: QuestionCategory;
  count: number;
  normal_rag_correctness?: number | null;
  amcrag_correctness?: number | null;
  normal_rag_faithfulness?: number | null;
  amcrag_faithfulness?: number | null;
  normal_rag_latency_ms: number;
  amcrag_latency_ms: number;
}

export interface ComparisonSummary {
  evaluated_questions_count: number;
  normal_rag_accuracy_pct?: number | null;
  amcrag_accuracy_pct?: number | null;
  accuracy_diff_pct?: number | null;
  normal_rag_mean_correctness?: number | null;
  amcrag_mean_correctness?: number | null;
  retrieval_mrr_diff?: number | null;
  latency_diff_ms: number;
  tokens_diff: number;
  successful_corrective_retrievals?: number;
  questions_requiring_multimodal?: number;
  initially_failed_recovered?: number;
  identical_evidence_count?: number;
}

export interface ComparisonRunRequest {
  document_id?: string | null;
  questions: EvaluationQuestion[];
  top_k?: number;
}

export interface ComparisonRunResponse {
  run_id: string;
  timestamp: string;
  document_id?: string | null;
  document_name?: string | null;
  summary: ComparisonSummary;
  amcrag_aggregate: AggregateQualityMetrics;
  normal_rag_aggregate: AggregateQualityMetrics;
  amcrag_performance: PerformanceMetrics;
  normal_rag_performance: PerformanceMetrics;
  category_breakdown: CategoryBreakdown[];
  questions: ComparedQuestionResult[];
}
