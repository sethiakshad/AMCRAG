/**
 * src/components/chat/MessageItem.tsx
 * Renders individual user queries and assistant responses adhering strictly to Claude.ai:
 * - User message in a rounded warm tinted container (sans font).
 * - Assistant message sits directly on canvas with NO bubble and NO avatar (serif font).
 * - Minimal, quiet action bar with copy, evidence drawer, CRAG badge, and latency toggle.
 */

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Copy,
  Check,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { ChatMessage, SourceMetadata } from '../../types/amcrag';
import { CRAGBadge } from './CRAGBadge';
import { LatencyWaterfall } from './LatencyWaterfall';
import { CitationBadge } from './CitationBadge';
import { parseCitations } from '../../utils/citationParser';

// Geometric starburst mark in terracotta
const StarburstIcon: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    style={{ display: 'inline-block', verticalAlign: 'middle' }}
  >
    <path d="M12 2L13.8 8.2L20 6.5L16.2 11.5L22 14.5L15.8 16.5L17.5 22.5L12 18.5L6.5 22.5L8.2 16.5L2 14.5L7.8 11.5L4 6.5L10.2 8.2L12 2Z" />
  </svg>
);

export interface MessageItemProps {
  message: ChatMessage;
  onSelectCitation: (evidenceId: string, sources: SourceMetadata[]) => void;
  onOpenAllSources: (sources: SourceMetadata[], visualInputs?: string[]) => void;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  onSelectCitation,
  onOpenAllSources,
}) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  // Render markdown with custom citation tag replacement
  const renderFormattedAnswer = (content: string, sources: SourceMetadata[] = []) => {
    const segments = parseCitations(content);

    return (
      <div className="prose">
        {segments.map((seg, idx) => {
          if (seg.type === 'citation' && seg.evidenceId) {
            const matchedSource = sources.find((s) => s.evidence_id === seg.evidenceId);
            return (
              <CitationBadge
                key={`cite-${idx}`}
                evidenceTag={seg.content}
                evidenceId={seg.evidenceId}
                source={matchedSource}
                onClick={(id) => onSelectCitation(id, sources)}
              />
            );
          }
          return (
            <ReactMarkdown
              key={`md-${idx}`}
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <span>{children}</span>,
              }}
            >
              {seg.content}
            </ReactMarkdown>
          );
        })}
      </div>
    );
  };

  // 1. User Message (Rounded container on --bg-300, sans font, no avatar)
  if (isUser) {
    return (
      <div className="turn" style={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
        <div className="msg-user">
          {message.content}
        </div>
      </div>
    );
  }

  // 2. Assistant Message (Directly on canvas, no bubble, no avatar, Newsreader serif)
  return (
    <div className="turn">
      {/* Rate Limit Notice if throttled */}
      {message.rateLimitRetryAfter && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-300)',
            border: 'var(--border-w) solid var(--warning)',
            color: 'var(--text-100)',
            fontSize: '13.5px',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <AlertTriangle size={16} style={{ color: 'var(--warning)', flexShrink: 0 }} />
          <div>
            <strong>Provider Rate Limit:</strong> Upstream model temporarily throttled. Please retry in{' '}
            <strong>{message.rateLimitRetryAfter}s</strong>.
          </div>
        </div>
      )}

      {/* Zero-Hallucination Guarded Notice */}
      {message.insufficientEvidence && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-300)',
            border: 'var(--border-w) solid var(--border-200)',
            color: 'var(--text-200)',
            fontSize: '13.5px',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <AlertTriangle size={16} style={{ color: 'var(--brand-clay)', flexShrink: 0 }} />
          <div>
            <strong>Zero-Hallucination Safe Fallback:</strong> The CRAG quality gate determined that retrieved documents lack sufficient factual evidence to reliably answer this prompt. Generation was stopped to avoid fabrication.
          </div>
        </div>
      )}

      {/* Error Card */}
      {message.error && !message.rateLimitRetryAfter && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-300)',
            border: 'var(--border-w) solid rgba(181, 51, 51, 0.3)',
            color: 'var(--danger)',
            fontSize: '13.5px',
            marginBottom: '12px',
          }}
        >
          {message.error}
        </div>
      )}

      {/* Main Serif Text Body */}
      <div className="msg-ai">
        {message.content ? (
          renderFormattedAnswer(message.content, message.sources)
        ) : null}

        {/* Streaming Thinking State */}
        {message.isStreaming && (
          <div className="thinking-state">
            <StarburstIcon size={16} className="spin-mark" />
            <span>Thinking…</span>
          </div>
        )}
      </div>

      {/* Quiet Action Toolbar Below Assistant Answer */}
      {!message.isStreaming && message.content && (
        <div className="msg-actions">
          {/* CRAG Decision State Badge */}
          {message.cragDecision && (
            <CRAGBadge decision={message.cragDecision} attempts={message.retrievalAttempts} />
          )}

          {/* Evidence Sources Button */}
          {message.sources && message.sources.length > 0 && (
            <button
              onClick={() => onOpenAllSources(message.sources || [], message.visualInputs)}
              className="btn btn-ghost"
              style={{ height: '28px', padding: '0 8px', fontSize: '12px', gap: '4px' }}
              title="Inspect citations and page evidence"
            >
              <Layers size={13} style={{ color: 'var(--brand-clay)' }} />
              <span>{message.sources.length} {message.sources.length === 1 ? 'citation' : 'citations'}</span>
            </button>
          )}

          {/* Copy Button */}
          <button
            onClick={handleCopy}
            className="btn-icon"
            style={{ width: '28px', height: '28px', marginLeft: 'auto' }}
            title={copied ? 'Copied to clipboard' : 'Copy answer'}
          >
            {copied ? <Check size={14} style={{ color: 'var(--success)' }} /> : <Copy size={14} />}
          </button>
        </div>
      )}

      {/* Telemetry Breakdown (Collapsible) */}
      {!message.isStreaming && (
        <LatencyWaterfall latency={message.latency} totalMs={message.totalMs} />
      )}
    </div>
  );
};
