/**
 * src/services/api.ts
 * Type-safe API client for AMCRAG backend endpoints.
 */

import {
  ApiRootInfo,
  DeleteResponse,
  DocumentDetailResponse,
  DocumentSummary,
  DocumentUploadResponse,
  HealthResponse,
  QueryRequest,
  QueryResponse,
} from '../types/amcrag';

const API_BASE = '/api/v1';

/**
 * Fetch root diagnostic information.
 */
export async function fetchRootInfo(): Promise<ApiRootInfo> {
  const response = await fetch('/');
  if (!response.ok) {
    throw new Error(`Root probe failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fetch system readiness and subsystem health status.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

/**
 * Execute standard synchronous (non-streaming) RAG query.
 */
export async function executeQuery(payload: QueryRequest): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || errorData.error || `Query failed (${response.status})`;
    const error = new Error(message) as any;
    error.status = response.status;
    error.details = errorData.details;
    if (response.status === 503) {
      const retryAfter = response.headers.get('Retry-After');
      if (retryAfter) error.retryAfter = parseInt(retryAfter, 10);
    }
    throw error;
  }

  return response.json();
}

/**
 * List all documents indexed in the knowledge base catalog.
 */
export async function listDocuments(): Promise<DocumentSummary[]> {
  const response = await fetch(`${API_BASE}/documents`);
  if (!response.ok) {
    throw new Error(`Failed to list documents: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get detailed manifest and page images for a specific document ID.
 */
export async function getDocumentDetail(docId: string): Promise<DocumentDetailResponse> {
  const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Document not found (${response.status})`);
  }
  return response.json();
}

/**
 * Upload a PDF document with optional force re-indexing flag.
 */
export async function uploadDocument(file: File, force: boolean = false): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('force', String(force));

  const response = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData.detail || errorData.error || `Upload failed (${response.status})`;
    const err = new Error(message) as any;
    err.status = response.status;
    throw err;
  }

  return response.json();
}

/**
 * Delete a document and purge entries from vector and lexical stores.
 */
export async function deleteDocument(docId: string): Promise<DeleteResponse> {
  const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Delete failed (${response.status})`);
  }

  return response.json();
}
