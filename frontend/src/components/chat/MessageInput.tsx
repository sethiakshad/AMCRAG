/**
 * src/components/chat/MessageInput.tsx
 * Signature Claude.ai composer component:
 * - Floating pill shape (20px border radius) on --bg-000
 * - Terracotta 32px send button with up arrow
 * - Modality segmented control and query settings trigger
 */

import React, { useRef, useEffect } from 'react';
import { ArrowUp, Square, Sliders, Filter } from 'lucide-react';
import { ModalitySelector } from './ModalitySelector';
import { ModelModality } from '../../types/amcrag';

export interface MessageInputProps {
  input: string;
  setInput: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isStreaming: boolean;
  modality: ModelModality | null;
  setModality: (val: ModelModality | null) => void;
  onOpenSettings: () => void;
  selectedDocCount?: number;
  disabled?: boolean;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  input,
  setInput,
  onSubmit,
  onStop,
  isStreaming,
  modality,
  setModality,
  onOpenSettings,
  selectedDocCount = 0,
  disabled = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height as content expands
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 260)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && input.trim() && !disabled) {
        onSubmit();
      }
    }
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        {/* Text Area */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Reply to AMCRAG or ask a question about your indexed PDFs..."
          disabled={disabled || isStreaming}
          rows={1}
        />

        {/* Bottom Toolbar */}
        <div className="composer-toolbar">
          {/* Left tools: Modality Selector & Filter Indicator */}
          <div className="composer-tools-left">
            <ModalitySelector value={modality} onChange={setModality} />

            {selectedDocCount > 0 && (
              <button
                type="button"
                onClick={onOpenSettings}
                className="btn btn-ghost"
                style={{
                  height: '28px',
                  padding: '0 8px',
                  fontSize: '12px',
                  gap: '4px',
                  color: 'var(--brand)',
                  background: 'var(--brand-tint)',
                  borderRadius: 'var(--radius-sm)',
                }}
                title="Filter active on specific documents"
              >
                <Filter size={11} />
                <span>{selectedDocCount} doc{selectedDocCount > 1 ? 's' : ''}</span>
              </button>
            )}
          </div>

          {/* Right tools: Settings Cog & Send/Stop Button */}
          <div className="composer-tools-right">
            <button
              type="button"
              onClick={onOpenSettings}
              className="btn-icon"
              title="Query and Retrieval Parameters"
              style={{ width: '30px', height: '30px' }}
            >
              <Sliders size={16} />
            </button>

            {isStreaming ? (
              <button
                type="button"
                onClick={onStop}
                className="stop-btn"
                title="Stop generation"
              >
                <Square size={12} fill="currentColor" />
              </button>
            ) : (
              <button
                type="button"
                onClick={onSubmit}
                disabled={!input.trim() || disabled}
                className="send-btn"
                title="Send message (Enter)"
              >
                <ArrowUp size={16} strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="composer-disclaimer">
        AMCRAG answers with Adaptive Multimodal Corrective RAG and 100% citation grounding.
      </div>
    </div>
  );
};
