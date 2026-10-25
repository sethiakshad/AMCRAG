/**
 * src/components/chat/ChatWindow.tsx
 * Full conversational QA interface adhering to Claude.ai:
 * - Empty state: Centered greeting in Newsreader Serif + Starburst mark + centered composer + suggestion chips.
 * - Conversation state: Centered 768px reading column + pinned floating composer.
 */

import React, { useRef, useEffect, useState } from 'react';
import { Filter, X } from 'lucide-react';
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

// Geometric starburst mark in terracotta
const StarburstIcon: React.FC<{ size?: number; className?: string }> = ({ size = 28, className = '' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    style={{ display: 'inline-block', verticalAlign: 'middle', color: 'var(--brand-clay)' }}
  >
    <path d="M12 2L13.8 8.2L20 6.5L16.2 11.5L22 14.5L15.8 16.5L17.5 22.5L12 18.5L6.5 22.5L8.2 16.5L2 14.5L7.8 11.5L4 6.5L10.2 8.2L12 2Z" />
  </svg>
);

export interface ChatWindowProps {
  availableDocuments: DocumentSummary[];
  preselectedDocId?: string | null;
  onClearPreselectedDoc?: () => void;
  onStartNewChat?: () => void;
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

  // Scroll to bottom when messages update
  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
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

  const handleSendQuery = async (queryText?: string) => {
    const textToSend = (queryText || input).trim();
    if (!textToSend) return;

    const userMessageId = `msg-user-${Date.now()}`;
    const assistantMessageId = `msg-asst-${Date.now() + 1}`;

    const userMsg: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: textToSend,
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
      query: textToSend,
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

  // Time-based friendly greeting
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      {/* Active Document Filter Notification Pill if restricted */}
      {settings.selectedDocIds.length > 0 && (
        <div
          style={{
            maxWidth: '48rem',
            width: '100%',
            margin: '8px auto 0',
            padding: '6px 14px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--brand-tint)',
            border: 'var(--border-w) solid rgba(51, 143, 255, 0.25)',
            fontSize: '13px',
            color: 'var(--text-100)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={13} style={{ color: 'var(--brand)' }} />
            <span>
              Searching restricted to <strong>{settings.selectedDocIds.length}</strong> document(s)
            </span>
          </div>
          <button
            onClick={() => {
              setSettings((prev) => ({ ...prev, selectedDocIds: [] }));
              if (onClearPreselectedDoc) onClearPreselectedDoc();
            }}
            className="btn-ghost"
            style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '3px' }}
          >
            <X size={12} />
            <span>Clear filter</span>
          </button>
        </div>
      )}

      {/* 1. Empty / Welcome State */}
      {messages.length === 0 ? (
        <div className="welcome-section">
          {/* Greeting Row */}
          <div className="welcome-greeting-row">
            <StarburstIcon size={30} />
            <h1 className="welcome-greeting">{getGreeting()}</h1>
          </div>

          {/* Centered Composer in Welcome view */}
          <div style={{ width: '100%', maxWidth: '46rem' }}>
            <MessageInput
              input={input}
              setInput={setInput}
              onSubmit={() => handleSendQuery()}
              onStop={stopStream}
              isStreaming={streamState.isStreaming}
              modality={modality}
              setModality={setModality}
              onOpenSettings={() => setIsSettingsOpen(true)}
              selectedDocCount={settings.selectedDocIds.length}
            />
          </div>
        </div>
      ) : (
        /* 2. Active Conversation State */
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {/* Scrollable Reading Column */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <div className="reading-column">
              {messages.map((msg) => (
                <MessageItem
                  key={msg.id}
                  message={msg}
                  onSelectCitation={handleOpenCitation}
                  onOpenAllSources={handleOpenAllSources}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Pinned Bottom Composer */}
          <div style={{ flex: 'none', background: 'transparent' }}>
            <MessageInput
              input={input}
              setInput={setInput}
              onSubmit={() => handleSendQuery()}
              onStop={stopStream}
              isStreaming={streamState.isStreaming}
              modality={modality}
              setModality={setModality}
              onOpenSettings={() => setIsSettingsOpen(true)}
              selectedDocCount={settings.selectedDocIds.length}
            />
          </div>
        </div>
      )}

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
