/**
 * src/types/amcrag.ts
 * Universal TypeScript contracts and models matching the AMCRAG FastAPI v1 backend.
 */

export type ModelModality = 'text' | 'vision';
export type EvidenceModality = 'text' | 'visual';
export type CRAGDecisionLabel = 'CORRECT' | 'AMBIGUOUS' | 'INCORRECT';
export type DocumentStatus = 'indexed' | 'cached' | 'failed';
export type SystemHealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface SourceMetadata {
  evidence_id: string;        // e.g. "E1", "E2"
  chunk_id: string;           // Underlying chunk identifier
  document: string;           // Human-readable filename
  page: number | null;        // 1-indexed page number
  type: EvidenceModality;     // "text" or "visual"
  source_ref: string | null;  // Relative path or document URI
  rank: number | null;        // Rank position in retrieved list
}

export interface LatencyBreakdown {
  query_analysis_ms: number;
  retrieval_ms: number;
  crag_evaluation_ms: number;
  context_building_ms: number;
  generation_ms: number;
  total_ms: number;
}

export interface QueryRequest {
  query: string;
  model_modality?: ModelModality | null;
  token_budget?: number;       // default 4096 (500 to 128000)
  top_k?: number;              // default 5 (1 to 50)
  enable_crag?: boolean;       // default true
  document_ids?: string[] | null;
}

export interface QueryResponse {
  query: string;
  answer: string;
  sources: SourceMetadata[];
  visual_inputs: string[];
  crag_decision: CRAGDecisionLabel | null;
  insufficient_evidence: boolean;
  retrieval_attempts: number;
  latency: LatencyBreakdown;
}

// Server-Sent Event Payloads
export interface SSEMetadataEvent {
  query: string;
  sources: SourceMetadata[];
  visual_inputs: string[];
  crag_decision: CRAGDecisionLabel | null;
  insufficient_evidence: boolean;
  retrieval_attempts: number;
}

export interface SSEDoneEvent {
  total_ms: number;
  retrieval_attempts: number;
  insufficient_evidence: boolean;
}

export interface SSEErrorEvent {
  error: string;
  retry_after?: number;
}

// Document Management
export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: DocumentStatus;
  page_count: number;
  chunk_count: number;
  image_count: number;
  message: string;
}

export interface DocumentSummary {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  upload_timestamp: string | null;
  file_size_bytes: number | null;
}

export interface DocumentDetailResponse {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
  image_count: number;
  status: string;
  metadata: Record<string, any>;
  page_images: string[];
}

export interface DeleteResponse {
  document_id: string;
  deleted: boolean;
  message: string;
}

// Health & System Information
export interface HealthResponse {
  status: SystemHealthStatus;
  version: string;
  components: {
    vector_db: boolean;
    bm25: boolean;
    crag: boolean;
    llm: boolean;
    colpali?: boolean;
    [key: string]: boolean | undefined;
  };
  uptime_seconds: number | null;
}

export interface ApiRootInfo {
  service: string;
  version: string;
  status: string;
  docs_url: string;
  health_url: string;
  query_url: string;
  documents_url: string;
}

export interface ApiErrorDetail {
  field?: string;
  message: string;
  type?: string;
}

export interface ApiErrorResponse {
  error: string;
  detail?: string;
  details?: ApiErrorDetail[];
  status_code: number;
}

// UI State Models
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  sources?: SourceMetadata[];
  visualInputs?: string[];
  cragDecision?: CRAGDecisionLabel | null;
  insufficientEvidence?: boolean;
  retrievalAttempts?: number;
  latency?: LatencyBreakdown;
  totalMs?: number | null;
  error?: string | null;
  rateLimitRetryAfter?: number | null;
}

export interface QuerySettingsConfig {
  topK: number;
  tokenBudget: number;
  enableCrag: boolean;
  selectedDocIds: string[];
  streamMode: boolean;
}
