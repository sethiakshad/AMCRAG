/**
 * src/components/chat/ModalitySelector.tsx
 * Segmented control: Auto / Text / Vision adhering to Claude design rules.
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
      label: 'Text',
      icon: <FileText size={13} />,
      tooltip: 'Force text-only generation; ignore page images',
    },
    {
      id: 'vision' as ModelModality,
      label: 'Vision',
      icon: <Eye size={13} />,
      tooltip: 'Enforce ColPali visual retrieval and route page PNGs to vision model',
    },
  ];

  return (
    <div className="segmented-control">
      {options.map((opt) => {
        const isSelected = value === opt.id;
        return (
          <button
            key={String(opt.id)}
            type="button"
            onClick={() => onChange(opt.id)}
            title={opt.tooltip}
            className={`segmented-btn ${isSelected ? 'selected' : ''}`}
          >
            {opt.icon}
            <span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
};
