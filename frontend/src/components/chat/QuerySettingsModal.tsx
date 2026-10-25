/**
 * src/components/chat/QuerySettingsModal.tsx
 * Query execution parameter configuration modal (top_k, token_budget, enable_crag, document filtering).
 */

import React from 'react';
import { Sliders, RotateCcw } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { DocumentSummary, QuerySettingsConfig } from '../../types/amcrag';

export interface QuerySettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: QuerySettingsConfig;
  onSave: (newSettings: QuerySettingsConfig) => void;
  availableDocuments: DocumentSummary[];
}

export const QuerySettingsModal: React.FC<QuerySettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onSave,
  availableDocuments,
}) => {
  const [localSettings, setLocalSettings] = React.useState<QuerySettingsConfig>(settings);

  React.useEffect(() => {
    setLocalSettings(settings);
  }, [settings, isOpen]);

  const handleReset = () => {
    setLocalSettings({
      topK: 5,
      tokenBudget: 4096,
      enableCrag: true,
      selectedDocIds: [],
      streamMode: true,
    });
  };

  const toggleDocSelection = (docId: string) => {
    setLocalSettings((prev) => {
      const exists = prev.selectedDocIds.includes(docId);
      return {
        ...prev,
        selectedDocIds: exists
          ? prev.selectedDocIds.filter((id) => id !== docId)
          : [...prev.selectedDocIds, docId],
      };
    });
  };

  const handleApply = () => {
    onSave(localSettings);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Query & Retrieval Settings" maxWidth="520px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Top K Slider */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
              Retrieval Top-K Candidates: <strong style={{ color: 'var(--brand-primary)' }}>{localSettings.topK}</strong>
            </label>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>1 to 50</span>
          </div>
          <input
            type="range"
            min={1}
            max={50}
            value={localSettings.topK}
            onChange={(e) => setLocalSettings({ ...localSettings, topK: parseInt(e.target.value, 10) })}
            style={{ width: '100%', accentColor: 'var(--brand-primary)' }}
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Number of hybrid text chunks and ColPali visual pages retrieved per query.
          </p>
        </div>

        {/* Token Budget Slider */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
              Context Token Budget: <strong style={{ color: '#38bdf8' }}>{localSettings.tokenBudget}</strong> tokens
            </label>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>500 to 32,000</span>
          </div>
          <input
            type="range"
            min={500}
            max={16000}
            step={256}
            value={localSettings.tokenBudget}
            onChange={(e) => setLocalSettings({ ...localSettings, tokenBudget: parseInt(e.target.value, 10) })}
            style={{ width: '100%', accentColor: '#38bdf8' }}
          />
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Maximum token budget allocated for context synthesis before truncation.
          </p>
        </div>

        {/* Enable CRAG Quality Gate Toggle */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.875rem 1rem',
            background: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
              Adaptive CRAG Quality Gatekeeper
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Evaluates evidence confidence, filters noise, and reformulates query if needed.
            </div>
          </div>
          <input
            type="checkbox"
            checked={localSettings.enableCrag}
            onChange={(e) => setLocalSettings({ ...localSettings, enableCrag: e.target.checked })}
            style={{ width: '18px', height: '18px', accentColor: 'var(--brand-primary)', cursor: 'pointer' }}
          />
        </div>

        {/* Streaming Mode Toggle */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.875rem 1rem',
            background: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
              Real-Time SSE Token Streaming
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Streams answer tokens as they are generated by the LLM.
            </div>
          </div>
          <input
            type="checkbox"
            checked={localSettings.streamMode}
            onChange={(e) => setLocalSettings({ ...localSettings, streamMode: e.target.checked })}
            style={{ width: '18px', height: '18px', accentColor: 'var(--brand-primary)', cursor: 'pointer' }}
          />
        </div>

        {/* Document Scope Filter */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
              Document Filter Scope
            </label>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {localSettings.selectedDocIds.length === 0
                ? 'Searching All Documents'
                : `${localSettings.selectedDocIds.length} restricted`}
            </span>
          </div>

          {availableDocuments.length === 0 ? (
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No documents currently indexed.</p>
          ) : (
            <div
              style={{
                maxHeight: '130px',
                overflowY: 'auto',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                background: 'rgba(0, 0, 0, 0.2)',
              }}
            >
              {availableDocuments.map((doc) => {
                const isSelected = localSettings.selectedDocIds.includes(doc.document_id);
                return (
                  <label
                    key={doc.document_id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '4px 8px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.8125rem',
                      color: isSelected ? '#ffffff' : 'var(--text-secondary)',
                      background: isSelected ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleDocSelection(doc.document_id)}
                      style={{ accentColor: 'var(--brand-primary)' }}
                    />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {doc.filename}
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
          <Button variant="ghost" size="sm" onClick={handleReset} icon={<RotateCcw size={13} />}>
            Reset Defaults
          </Button>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleApply}>
              Save Settings
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
