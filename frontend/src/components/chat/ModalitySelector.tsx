/**
 * src/components/chat/ModalitySelector.tsx
 * Segmented toggle control: Auto (Smart intent) / Text Only / Multimodal Vision.
 */

import React from 'react';
import { Sparkles, FileText, Eye } from 'lucide-react';
import { ModelModality } from '../../types/amcrag';

export interface ModalitySelectorProps {
  value: ModelModality | null;
  onChange: (value: ModelModality | null) => void;
}

export const ModalitySelector: React.FC<ModalitySelectorProps> = ({ value, onChange }) => {
  const options = [
    {
      id: null,
      label: 'Auto',
      icon: <Sparkles size={13} />,
      tooltip: 'Auto-detect visual intent via keyword analysis (charts, tables, diagrams)',
    },
    {
      id: 'text' as ModelModality,
      label: 'Text Only',
      icon: <FileText size={13} />,
      tooltip: 'Force text-only generation; ignore page images',
    },
    {
      id: 'vision' as ModelModality,
      label: 'Multimodal Vision',
      icon: <Eye size={13} />,
      tooltip: 'Enforce ColPali visual retrieval and route page PNGs to vision model',
    },
  ];

  return (
    <div
      style={{
        display: 'inline-flex',
        padding: '3px',
        borderRadius: '8px',
        background: 'rgba(255, 255, 255, 0.04)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      {options.map((opt) => {
        const isSelected = value === opt.id;
        return (
          <button
            key={String(opt.id)}
            type="button"
            onClick={() => onChange(opt.id)}
            title={opt.tooltip}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: 'none',
              background: isSelected ? 'var(--brand-gradient)' : 'transparent',
              color: isSelected ? '#ffffff' : 'var(--text-muted)',
              fontSize: '0.75rem',
              fontWeight: isSelected ? 600 : 500,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              boxShadow: isSelected ? '0 2px 8px rgba(99, 102, 241, 0.3)' : 'none',
            }}
          >
            {opt.icon}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
};
