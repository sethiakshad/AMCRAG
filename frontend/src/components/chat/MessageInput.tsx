/**
 * src/components/chat/MessageInput.tsx
 * Multi-line prompt input with modality switcher, stop generation button, and settings trigger.
 */

import React, { useRef, useEffect } from 'react';
import { Send, Square, Sliders, CornerDownLeft } from 'lucide-react';
import { Button } from '../ui/Button';
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
  disabled = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height as content expands
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
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
    <div
      className="glass-panel-elevated"
      style={{
        padding: '0.875rem 1.125rem',
        borderRadius: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
      }}
    >
      {/* Top Toolbar: Modality Selector & Settings */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <ModalitySelector value={modality} onChange={setModality} />

        <Button
          variant="icon"
          onClick={onOpenSettings}
          title="Adjust retrieval top-k, token budget, and document scope"
          style={{ padding: '4px' }}
        >
          <Sliders size={16} />
        </Button>
      </div>

      {/* Input Area */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.75rem' }}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your indexed PDF documents, reports, or research papers..."
          disabled={disabled || isStreaming}
          rows={1}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#ffffff',
            fontSize: '0.9375rem',
            fontFamily: 'var(--font-sans)',
            lineHeight: 1.5,
            resize: 'none',
            maxHeight: '180px',
            padding: '2px 0',
          }}
        />

        {/* Submit or Stop Button */}
        {isStreaming ? (
          <Button
            variant="danger"
            onClick={onStop}
            title="Stop generation"
            icon={<Square size={14} fill="currentColor" />}
            style={{ borderRadius: '10px', height: '38px', padding: '0 12px' }}
          >
            Stop
          </Button>
        ) : (
          <Button
            variant="primary"
            onClick={onSubmit}
            disabled={!input.trim() || disabled}
            title="Submit question (Enter)"
            icon={<Send size={15} />}
            style={{ borderRadius: '10px', height: '38px', padding: '0 14px' }}
          >
            Ask
          </Button>
        )}
      </div>

      {/* Subtext info */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.7rem',
          color: 'var(--text-muted)',
        }}
      >
        <span>Press <kbd style={{ fontFamily: 'var(--font-mono)' }}>Enter</kbd> to ask, <kbd style={{ fontFamily: 'var(--font-mono)' }}>Shift+Enter</kbd> for newline</span>
        <span>Grounded by Adaptive CRAG with 100% citation provenance</span>
      </div>
    </div>
  );
};
