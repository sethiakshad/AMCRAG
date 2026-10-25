/**
 * src/components/chat/MessageItem.tsx
 * Renders individual user queries and assistant responses with grounded citations and telemetry.
 */

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  User,
  Bot,
  Copy,
  Check,
  AlertTriangle,
  Layers,
  Sparkles,
} from 'lucide-react';
import { ChatMessage, SourceMetadata } from '../../types/amcrag';
import { CRAGBadge } from './CRAGBadge';
import { LatencyWaterfall } from './LatencyWaterfall';
import { CitationBadge } from './CitationBadge';
import { parseCitations } from '../../utils/citationParser';

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
    setTimeout(() => setCopied(false), 2000);
  };

  // Render markdown with custom citation tag replacement
  const renderFormattedAnswer = (content: string, sources: SourceMetadata[] = []) => {
    const segments = parseCitations(content);

    return (
      <div className="markdown-body">
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

  return (
    <div
      style={{
        display: 'flex',
        gap: '1rem',
        padding: '1.25rem',
        borderRadius: '16px',
        background: isUser ? 'rgba(255, 255, 255, 0.02)' : 'rgba(15, 23, 42, 0.65)',
        border: `1px solid ${isUser ? 'transparent' : 'var(--border-subtle)'}`,
        backdropFilter: isUser ? 'none' : 'blur(12px)',
        position: 'relative',
      }}
      className="fade-in"
    >
      {/* Avatar Icon */}
      <div
        style={{
          width: '36px',
          height: '36px',
          borderRadius: '10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          background: isUser ? 'rgba(255, 255, 255, 0.08)' : 'var(--brand-gradient)',
          color: '#ffffff',
          boxShadow: isUser ? 'none' : '0 4px 12px rgba(99, 102, 241, 0.35)',
        }}
      >
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>

      {/* Message Content Container */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
        {/* Header: Author & Metadata */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.9375rem', color: '#ffffff' }}>
              {isUser ? 'You' : 'AMCRAG Assistant'}
            </span>

            {!isUser && message.cragDecision && (
              <CRAGBadge decision={message.cragDecision} attempts={message.retrievalAttempts} />
            )}
          </div>

          {!isUser && !message.isStreaming && message.content && (
            <button
              onClick={handleCopy}
              className="btn-icon"
              title="Copy answer"
              style={{ padding: '4px' }}
            >
              {copied ? <Check size={14} style={{ color: '#10b981' }} /> : <Copy size={14} />}
            </button>
          )}
        </div>

        {/* Rate Limit Error Card if received */}
        {message.rateLimitRetryAfter && (
          <div
            style={{
              padding: '0.875rem 1rem',
              borderRadius: '8px',
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.35)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              color: '#fbbf24',
              fontSize: '0.8125rem',
            }}
          >
            <AlertTriangle size={18} style={{ flexShrink: 0 }} />
            <div>
              <strong>LLM Rate Limit Reached:</strong> Upstream provider throttled request. Please retry after{' '}
              <strong>{message.rateLimitRetryAfter} seconds</strong>.
            </div>
          </div>
        )}

        {/* Zero-Hallucination Safe Fallback Card */}
        {message.insufficientEvidence && (
          <div
            style={{
              padding: '0.875rem 1rem',
              borderRadius: '8px',
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              color: '#fbbf24',
              fontSize: '0.8125rem',
            }}
          >
            <AlertTriangle size={18} style={{ flexShrink: 0 }} />
            <div>
              <strong>Zero-Hallucination Guard Active:</strong> The CRAG quality gate concluded that the indexed documents lack factual evidence to reliably answer this question. Generation was stopped to prevent ungrounded fabrication.
            </div>
          </div>
        )}

        {/* General Error Card */}
        {message.error && !message.rateLimitRetryAfter && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              background: 'rgba(244, 63, 94, 0.12)',
              border: '1px solid rgba(244, 63, 94, 0.35)',
              color: '#fb7185',
              fontSize: '0.8125rem',
            }}
          >
            {message.error}
          </div>
        )}

        {/* Text Body */}
        {isUser ? (
          <div style={{ color: '#ffffff', fontSize: '0.9375rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {message.content}
          </div>
        ) : (
          <div>
            {renderFormattedAnswer(message.content, message.sources)}
            {message.isStreaming && <span className="cursor-blink">▊</span>}
          </div>
        )}

        {/* Source Citations Quick Bar */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '0.5rem',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              flexWrap: 'wrap',
              gap: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Sources:</span>
              {message.sources.map((src) => (
                <CitationBadge
                  key={src.evidence_id}
                  evidenceTag={`[${src.evidence_id}] ${src.document}${src.page ? ` p.${src.page}` : ''}`}
                  evidenceId={src.evidence_id}
                  source={src}
                  onClick={(id) => onSelectCitation(id, message.sources || [])}
                />
              ))}
            </div>

            <button
              onClick={() => onOpenAllSources(message.sources || [], message.visualInputs)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--brand-primary)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <Layers size={13} /> View All {message.sources.length} Evidence Items
            </button>
          </div>
        )}

        {/* Latency Waterfall Telemetry */}
        {!isUser && (
          <LatencyWaterfall latency={message.latency} totalMs={message.totalMs} />
        )}
      </div>
    </div>
  );
};
