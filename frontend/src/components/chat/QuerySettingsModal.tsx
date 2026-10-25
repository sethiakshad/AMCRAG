/**
 * src/components/chat/QuerySettingsModal.tsx
 * Query execution parameter configuration modal (top_k, token_budget, enable_crag, document filtering).
 * Aligned with Claude design system.
 */

import React from 'react';
import { RotateCcw } from 'lucide-react';
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
    <Modal isOpen={isOpen} onClose={onClose} title="Query Settings" maxWidth="500px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Top K Slider */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)' }}>
              Retrieval Top-K Candidates: <strong style={{ color: 'var(--brand)', fontFamily: 'var(--font-mono)' }}>{localSettings.topK}</strong>
            </label>
            <span style={{ fontSize: '12px', color: 'var(--text-400)' }}>1 to 50</span>
          </div>
          <input
            type="range"
            min={1}
            max={50}
            value={localSettings.topK}
            onChange={(e) => setLocalSettings({ ...localSettings, topK: parseInt(e.target.value, 10) })}
            style={{ width: '100%', accentColor: 'var(--brand)' }}
          />
          <p style={{ fontSize: '12px', color: 'var(--text-300)', marginTop: '4px' }}>
            Number of hybrid passages and ColPali visual page representations retrieved per query.
          </p>
        </div>

        {/* Token Budget Slider */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)' }}>
              Context Token Budget: <strong style={{ color: 'var(--brand-clay)', fontFamily: 'var(--font-mono)' }}>{localSettings.tokenBudget}</strong> tokens
            </label>
            <span style={{ fontSize: '12px', color: 'var(--text-400)' }}>500 to 16,000</span>
          </div>
          <input
            type="range"
            min={500}
            max={16000}
            step={256}
            value={localSettings.tokenBudget}
            onChange={(e) => setLocalSettings({ ...localSettings, tokenBudget: parseInt(e.target.value, 10) })}
            style={{ width: '100%', accentColor: 'var(--brand)' }}
          />
          <p style={{ fontSize: '12px', color: 'var(--text-300)', marginTop: '4px' }}>
            Maximum token budget allocated for context synthesis before truncation.
          </p>
        </div>

        {/* Enable CRAG Quality Gate Toggle */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            background: 'var(--bg-100)',
            borderRadius: 'var(--radius-md)',
            border: 'var(--border-w) solid var(--border-200)',
          }}
        >
          <div>
            <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)' }}>
              Adaptive CRAG Quality Gate
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-300)' }}>
              Evaluates evidence confidence, filters noise, and reformulates query if needed.
            </div>
          </div>
          <input
            type="checkbox"
            checked={localSettings.enableCrag}
            onChange={(e) => setLocalSettings({ ...localSettings, enableCrag: e.target.checked })}
            style={{ width: '17px', height: '17px', accentColor: 'var(--brand)', cursor: 'pointer' }}
          />
        </div>

        {/* Streaming Mode Toggle */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            background: 'var(--bg-100)',
            borderRadius: 'var(--radius-md)',
            border: 'var(--border-w) solid var(--border-200)',
          }}
        >
          <div>
            <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)' }}>
              Real-Time SSE Streaming
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-300)' }}>
              Streams answer tokens as they are generated by the LLM.
            </div>
          </div>
          <input
            type="checkbox"
            checked={localSettings.streamMode}
            onChange={(e) => setLocalSettings({ ...localSettings, streamMode: e.target.checked })}
            style={{ width: '17px', height: '17px', accentColor: 'var(--brand)', cursor: 'pointer' }}
          />
        </div>

        {/* Document Scope Filter */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)' }}>
              Document Filter Scope
            </label>
            <span style={{ fontSize: '12px', color: 'var(--text-300)' }}>
              {localSettings.selectedDocIds.length === 0
                ? 'Searching All Documents'
                : `${localSettings.selectedDocIds.length} restricted`}
            </span>
          </div>

          {availableDocuments.length === 0 ? (
            <p style={{ fontSize: '12px', color: 'var(--text-400)' }}>No documents currently indexed.</p>
          ) : (
            <div
              style={{
                maxHeight: '130px',
                overflowY: 'auto',
                border: 'var(--border-w) solid var(--border-200)',
                borderRadius: 'var(--radius-md)',
                padding: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '3px',
                background: 'var(--bg-100)',
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
                      padding: '5px 8px',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer',
                      fontSize: '13px',
                      color: isSelected ? 'var(--text-100)' : 'var(--text-200)',
                      background: isSelected ? 'var(--brand-tint)' : 'transparent',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleDocSelection(doc.document_id)}
                      style={{ accentColor: 'var(--brand)' }}
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px', paddingTop: '10px', borderTop: 'var(--border-w) solid var(--border-100)' }}>
          <Button variant="ghost" size="sm" onClick={handleReset} icon={<RotateCcw size={13} />}>
            Reset
          </Button>

          <div style={{ display: 'flex', gap: '8px' }}>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleApply}>
              Save
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
