/**
 * src/services/comparisonApi.ts
 * API client methods for RAG comparison benchmarking endpoints.
 */

import {
  ComparisonRunRequest,
  ComparisonRunResponse,
  EvaluationQuestion,
} from '../types/comparison';

const API_BASE = '/api/v1/comparison';

/**
 * Execute side-by-side RAG benchmark across AMCRAG and Normal RAG baseline.
 */
export async function runComparisonBenchmark(
  payload: ComparisonRunRequest
): Promise<ComparisonRunResponse> {
  const response = await fetch(`${API_BASE}/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || errorData.error || `Comparison failed (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

/**
 * Fetch default verified evaluation questions for a document.
 */
export async function fetchDefaultQuestions(
  documentId?: string
): Promise<EvaluationQuestion[]> {
  const url = documentId
    ? `${API_BASE}/default-questions?document_id=${encodeURIComponent(documentId)}`
    : `${API_BASE}/default-questions`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load default questions (${response.status})`);
  }

  return response.json();
}
