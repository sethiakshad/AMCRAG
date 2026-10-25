/**
 * src/components/chat/ChatWindow.tsx
 * Full conversational QA interface integrating streaming responses, provenance drawer, and settings.
 */

import React, { useRef, useEffect, useState } from 'react';
import { Sparkles, MessageSquare, BookOpen, Layers, ShieldCheck } from 'lucide-react';
import { MessageItem } from './MessageItem';
import { MessageInput } from './MessageInput';
import { EvidenceDrawer } from './EvidenceDrawer';
import { QuerySettingsModal } from './QuerySettingsModal';
import { useSSEQuery } from '../../hooks/useSSEQuery';
import { executeQuery } from '../../services/api';
import {
  ChatMessage,
  DocumentSummary,
  ModelModality,
  QuerySettingsConfig,
  SourceMetadata,
} from '../../types/amcrag';

export interface ChatWindowProps {
  availableDocuments: DocumentSummary[];
  preselectedDocId?: string | null;
  onClearPreselectedDoc?: () => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  availableDocuments,
  preselectedDocId,
  onClearPreselectedDoc,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState<string>('');
  const [modality, setModality] = useState<ModelModality | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Evidence Drawer state
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerSources, setDrawerSources] = useState<SourceMetadata[]>([]);
  const [drawerVisualInputs, setDrawerVisualInputs] = useState<string[]>([]);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);

  // Query Settings
  const [settings, setSettings] = useState<QuerySettingsConfig>({
    topK: 5,
    tokenBudget: 4096,
    enableCrag: true,
    selectedDocIds: preselectedDocId ? [preselectedDocId] : [],
    streamMode: true,
  });

  useEffect(() => {
    if (preselectedDocId) {
      setSettings((prev) => ({
        ...prev,
        selectedDocIds: [preselectedDocId],
      }));
    }
  }, [preselectedDocId]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { streamState, startStream, stopStream } = useSSEQuery();

  // Scroll to bottom when messages update or streaming tokens arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamState.accumulatedAnswer]);

  const handleOpenCitation = (evidenceId: string, sources: SourceMetadata[]) => {
    setDrawerSources(sources);
    setActiveEvidenceId(evidenceId);
    setIsDrawerOpen(true);
  };

  const handleOpenAllSources = (sources: SourceMetadata[], visualInputs?: string[]) => {
    setDrawerSources(sources);
    setDrawerVisualInputs(visualInputs || []);
    setActiveEvidenceId(null);
    setIsDrawerOpen(true);
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    const userMessageId = `msg-user-${Date.now()}`;
    const assistantMessageId = `msg-asst-${Date.now() + 1}`;

    const userMsg: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: trimmed,
      timestamp: new Date(),
    };

    const placeholderAssistantMsg: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, placeholderAssistantMsg]);
    setInput('');

    const queryPayload = {
      query: trimmed,
      model_modality: modality,
      top_k: settings.topK,
      token_budget: settings.tokenBudget,
      enable_crag: settings.enableCrag,
      document_ids: settings.selectedDocIds.length > 0 ? settings.selectedDocIds : null,
    };

    if (settings.streamMode) {
      // Execute Streaming via SSE
      startStream(
        queryPayload,
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content + token }
                : msg
            )
          );
        },
        (finalState) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: finalState.accumulatedAnswer,
                    isStreaming: false,
                    sources: finalState.sources,
                    visualInputs: finalState.visualInputs,
                    cragDecision: finalState.cragDecision,
                    insufficientEvidence: finalState.insufficientEvidence,
                    retrievalAttempts: finalState.retrievalAttempts,
                    totalMs: finalState.totalMs,
                    error: finalState.error,
                    rateLimitRetryAfter: finalState.rateLimitRetryAfter,
                  }
                : msg
            )
          );
        }
      );
    } else {
      // Execute standard synchronous query
      try {
        const response = await executeQuery(queryPayload);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: response.answer,
                  isStreaming: false,
                  sources: response.sources,
                  visualInputs: response.visual_inputs,
                  cragDecision: response.crag_decision,
                  insufficientEvidence: response.insufficient_evidence,
                  retrievalAttempts: response.retrieval_attempts,
                  latency: response.latency,
                  totalMs: response.latency.total_ms,
                }
              : msg
          )
        );
      } catch (err: any) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: '',
                  isStreaming: false,
                  error: err.message || 'Query execution failed',
                  rateLimitRetryAfter: err.retryAfter || null,
                }
              : msg
          )
        );
      }
    }
  };

  const starterQueries = [
    'What is the lock-in period and tax deduction rule for ELSS mutual funds?',
    'Summarize the primary revenue growth drivers disclosed in the report.',
    'Compare the risk factors outlined between quarterly periods.',
    'What key trends and data points are illustrated in the performance chart?',
  ];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 120px)',
        maxWidth: '960px',
        width: '100%',
        margin: '0 auto',
        position: 'relative',
      }}
    >
      {/* Active Document Filter Notification Pill if restricted */}
      {settings.selectedDocIds.length > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 14px',
            marginBottom: '0.75rem',
            borderRadius: '8px',
            background: 'rgba(99, 102, 241, 0.12)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            fontSize: '0.8125rem',
            color: '#c7d2fe',
          }}
        >
          <span>
            Filtering query scope to <strong>{settings.selectedDocIds.length}</strong> selected document(s)
          </span>
          <button
            onClick={() => {
              setSettings((prev) => ({ ...prev, selectedDocIds: [] }));
              if (onClearPreselectedDoc) onClearPreselectedDoc();
            }}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#ffffff',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              textDecoration: 'underline',
            }}
          >
            Clear Filter (Search All)
          </button>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
          paddingRight: '6px',
          paddingBottom: '1rem',
        }}
      >
        {messages.length === 0 ? (
          /* Empty State */
          <div
            style={{
              margin: 'auto',
              textAlign: 'center',
              maxWidth: '620px',
              padding: '2rem 1rem',
            }}
          >
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '16px',
                background: 'var(--brand-gradient)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 1.25rem auto',
                boxShadow: 'var(--brand-glow)',
                color: '#ffffff',
              }}
            >
              <Sparkles size={28} />
            </div>

            <h3 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ffffff', fontFamily: 'var(--font-heading)' }}>
              Ask AMCRAG Anything
            </h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.5rem', lineHeight: 1.6 }}>
              Combines dense semantic vectors, sparse lexical search, and ColPali visual document retrieval with an Adaptive Corrective RAG quality gate to eliminate hallucinations.
            </p>

            {/* Feature Highlights Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
                gap: '10px',
                marginTop: '1.75rem',
                textAlign: 'left',
              }}
            >
              <div className="glass-panel" style={{ padding: '0.875rem' }}>
                <Layers size={16} style={{ color: '#818cf8', marginBottom: '4px' }} />
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#ffffff' }}>Hybrid Retrieval</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Dense BGE + Sparse BM25 fused with RRF k=60</div>
              </div>

              <div className="glass-panel" style={{ padding: '0.875rem' }}>
                <ShieldCheck size={16} style={{ color: '#34d399', marginBottom: '4px' }} />
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#ffffff' }}>Adaptive CRAG</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Confidence thresholds with query reformulations</div>
              </div>

              <div className="glass-panel" style={{ padding: '0.875rem' }}>
                <BookOpen size={16} style={{ color: '#f472b6', marginBottom: '4px' }} />
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#ffffff' }}>ColPali Vision</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>150 DPI page visual representations</div>
              </div>
            </div>

            {/* Starter Queries */}
            <div style={{ marginTop: '2rem', textAlign: 'left' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                Sample Questions
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {starterQueries.map((q) => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    style={{
                      padding: '0.625rem 0.875rem',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--text-secondary)',
                      fontSize: '0.8125rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                    className="hover:border-indigo-500/50 hover:text-white"
                  >
                    <MessageSquare size={13} style={{ color: 'var(--brand-primary)', flexShrink: 0 }} />
                    <span>{q}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <MessageItem
              key={msg.id}
              message={msg}
              onSelectCitation={handleOpenCitation}
              onOpenAllSources={handleOpenAllSources}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Sticky Bottom Input Bar */}
      <div style={{ marginTop: 'auto', paddingTop: '0.5rem' }}>
        <MessageInput
          input={input}
          setInput={setInput}
          onSubmit={handleSend}
          onStop={stopStream}
          isStreaming={streamState.isStreaming}
          modality={modality}
          setModality={setModality}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />
      </div>

      {/* Slide-Over Evidence Inspector Drawer */}
      <EvidenceDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        sources={drawerSources}
        visualInputs={drawerVisualInputs}
        activeEvidenceId={activeEvidenceId}
      />

      {/* Query Configuration Modal */}
      <QuerySettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onSave={setSettings}
        availableDocuments={availableDocuments}
      />
    </div>
  );
};
