/**
 * src/components/chat/CRAGBadge.tsx
 * Evaluator decision badge (CORRECT / AMBIGUOUS / INCORRECT) adhering to Claude design tokens.
 */

import React from 'react';
import { Check, AlertTriangle, AlertCircle, RotateCcw } from 'lucide-react';
import { CRAGDecisionLabel } from '../../types/amcrag';

export interface CRAGBadgeProps {
  decision: CRAGDecisionLabel | null | undefined;
  attempts?: number;
  className?: string;
}

export const CRAGBadge: React.FC<CRAGBadgeProps> = ({
  decision,
  attempts = 1,
  className = '',
}) => {
  if (!decision) return null;

  const decisionConfig = {
    CORRECT: {
      label: 'Verified Grounded',
      pillClass: 'crag-pill correct',
      icon: <Check size={12} strokeWidth={2.5} />,
      tooltip: 'Passed confidence threshold (β >= 0.70). High factual grounding.',
    },
    AMBIGUOUS: {
      label: 'Filtered Ambiguous',
      pillClass: 'crag-pill ambiguous',
      icon: <AlertTriangle size={12} />,
      tooltip: 'Evidence had medium confidence (0.30 <= β < 0.70). Irrelevant passages stripped.',
    },
    INCORRECT: {
      label: 'Corrective Reformulation',
      pillClass: 'crag-pill incorrect',
      icon: <AlertCircle size={12} />,
      tooltip: 'Initial confidence low (β < 0.30). Triggered corrective query reformulation.',
    },
  };

  const item = decisionConfig[decision] || decisionConfig.CORRECT;

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }} className={className}>
      <span className={item.pillClass} title={item.tooltip}>
        {item.icon}
        {item.label}
      </span>

      {attempts > 1 && (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '3px',
            padding: '2px 6px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            background: 'var(--bg-300)',
            color: 'var(--text-300)',
            border: 'var(--border-w) solid var(--border-100)',
          }}
          title={`Query reformulated and retrieved ${attempts} times by CRAG retry loop`}
        >
          <RotateCcw size={10} /> {attempts} retries
        </span>
      )}
    </div>
  );
};
