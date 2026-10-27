/**
 * src/hooks/useSSEQuery.ts
 * Streaming query execution hook using Server-Sent Events (SSE).
 */

import { useCallback, useRef, useState } from 'react';
import {
  CRAGDecisionLabel,
  QueryRequest,
  SSEDoneEvent,
  SSEMetadataEvent,
  SourceMetadata,
} from '../types/amcrag';

export interface SSEStreamState {
  isStreaming: boolean;
  activeQuery: string;
  accumulatedAnswer: string;
  sources: SourceMetadata[];
  visualInputs: string[];
  cragDecision: CRAGDecisionLabel | null;
  insufficientEvidence: boolean;
  retrievalAttempts: number;
  totalMs: number | null;
  error: string | null;
  rateLimitRetryAfter: number | null;
}

export function useSSEQuery() {
  const [streamState, setStreamState] = useState<SSEStreamState>({
    isStreaming: false,
    activeQuery: '',
    accumulatedAnswer: '',
    sources: [],
    visualInputs: [],
    cragDecision: null,
    insufficientEvidence: false,
    retrievalAttempts: 1,
    totalMs: null,
    error: null,
    rateLimitRetryAfter: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    async (
      payload: QueryRequest,
      onToken?: (token: string) => void,
      onComplete?: (finalState: SSEStreamState) => void
    ) => {
      // Abort previous stream if active
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const initialState: SSEStreamState = {
        isStreaming: true,
        activeQuery: payload.query,
        accumulatedAnswer: '',
        sources: [],
        visualInputs: [],
        cragDecision: null,
        insufficientEvidence: false,
        retrievalAttempts: 1,
        totalMs: null,
        error: null,
        rateLimitRetryAfter: null,
      };

      setStreamState(initialState);
      let localAnswer = '';
      let localSources: SourceMetadata[] = [];
      let localVisualInputs: string[] = [];
      let localDecision: CRAGDecisionLabel | null = null;
      let localInsufficient = false;
      let localAttempts = 1;
      let localTotalMs: number | null = null;

      try {
        const response = await fetch('/api/v1/query/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          let errMsg = errData.detail || errData.error || `Stream failed with status ${response.status}`;
          // Provide friendlier messages for common backend-down scenarios
          if (response.status === 502) {
            errMsg = 'Backend server is not running. Please start the backend first.';
          } else if (response.status === 503) {
            errMsg = errData.detail || 'Service temporarily unavailable. Please try again shortly.';
          }
          let retrySec: number | null = null;
          if (response.status === 503) {
            const retryHeader = response.headers.get('Retry-After');
            if (retryHeader) retrySec = parseInt(retryHeader, 10);
          }
          setStreamState((prev) => ({
            ...prev,
            isStreaming: false,
            error: errMsg,
            rateLimitRetryAfter: retrySec,
          }));
          return;
        }

        if (!response.body) {
          throw new Error('ReadableStream is not supported in this browser environment.');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';

          for (const rawEvent of events) {
            if (!rawEvent.trim()) continue;

            const lines = rawEvent.split('\n');
            let eventType = 'message';
            const dataLines: string[] = [];

            for (const line of lines) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                dataLines.push(line.slice(6));
              }
            }
            const dataStr = dataLines.join('\n');

            if (eventType === 'metadata') {
              try {
                const meta: SSEMetadataEvent = JSON.parse(dataStr);
                localSources = meta.sources || [];
                localVisualInputs = meta.visual_inputs || [];
                localDecision = meta.crag_decision;
                localInsufficient = meta.insufficient_evidence;
                localAttempts = meta.retrieval_attempts;

                setStreamState((prev) => ({
                  ...prev,
                  sources: localSources,
                  visualInputs: localVisualInputs,
                  cragDecision: localDecision,
                  insufficientEvidence: localInsufficient,
                  retrievalAttempts: localAttempts,
                }));
              } catch (e) {
                console.error('Failed to parse SSE metadata event', e);
              }
            } else if (eventType === 'sources') {
              try {
                const sourcesList: SourceMetadata[] = JSON.parse(dataStr);
                localSources = sourcesList;
                setStreamState((prev) => ({ ...prev, sources: localSources }));
              } catch (e) {
                console.error('Failed to parse SSE sources event', e);
              }
            } else if (eventType === 'token') {
              localAnswer += dataStr;
              if (onToken) onToken(dataStr);
              setStreamState((prev) => ({ ...prev, accumulatedAnswer: localAnswer }));
            } else if (eventType === 'done') {
              try {
                const doneData: SSEDoneEvent = JSON.parse(dataStr);
                localTotalMs = doneData.total_ms;
                localAttempts = doneData.retrieval_attempts;
                localInsufficient = doneData.insufficient_evidence;

                setStreamState((prev) => ({
                  ...prev,
                  totalMs: localTotalMs,
                  retrievalAttempts: localAttempts,
                  insufficientEvidence: localInsufficient,
                  isStreaming: false,
                }));
              } catch {
                setStreamState((prev) => ({ ...prev, isStreaming: false }));
              }
            } else if (eventType === 'error') {
              try {
                const errPayload = JSON.parse(dataStr);
                setStreamState((prev) => ({
                  ...prev,
                  error: errPayload.error || 'Stream error occurred',
                  rateLimitRetryAfter: errPayload.retry_after || null,
                  isStreaming: false,
                }));
              } catch {
                setStreamState((prev) => ({
                  ...prev,
                  error: dataStr || 'Stream error occurred',
                  isStreaming: false,
                }));
              }
            }
          }
        }

        // Safety net: ensure isStreaming is false after reader finishes,
        // even if no explicit 'done' event was received (e.g. backend crash mid-stream)
        setStreamState((prev) => {
          if (prev.isStreaming) {
            return { ...prev, isStreaming: false };
          }
          return prev;
        });

        if (onComplete) {
          onComplete({
            isStreaming: false,
            activeQuery: payload.query,
            accumulatedAnswer: localAnswer,
            sources: localSources,
            visualInputs: localVisualInputs,
            cragDecision: localDecision,
            insufficientEvidence: localInsufficient,
            retrievalAttempts: localAttempts,
            totalMs: localTotalMs,
            error: null,
            rateLimitRetryAfter: null,
          });
        }
      } catch (err: any) {
        if (err.name === 'AbortError') {
          console.info('AMCRAG: SSE Query stream generation aborted by user.');
          setStreamState((prev) => ({ ...prev, isStreaming: false }));
        } else {
          console.error('AMCRAG: SSE Query stream failed', err);
          const friendlyMsg = err.message?.includes('Failed to fetch')
            ? 'Cannot connect to the backend. Please ensure the server is running.'
            : (err.message || 'Network stream error');
          setStreamState((prev) => ({
            ...prev,
            isStreaming: false,
            error: friendlyMsg,
          }));
        }
      } finally {
        abortControllerRef.current = null;
      }
    },
    []
  );

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setStreamState((prev) => ({ ...prev, isStreaming: false }));
    }
  }, []);

  return {
    streamState,
    startStream,
    stopStream,
  };
}
