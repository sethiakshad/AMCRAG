/**
 * src/components/chat/CRAGBadge.tsx
 * Evaluator decision badge (CORRECT / AMBIGUOUS / INCORRECT) and reformulation indicator.
 */

import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, RotateCcw } from 'lucide-react';
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

  const decisionMap = {
    CORRECT: {
      label: 'CRAG: Correct',
      color: '#34d399',
      bg: 'var(--crag-correct-bg)',
      border: 'var(--crag-correct-border)',
      icon: <CheckCircle2 size={13} />,
      tooltip: 'Evidence passed confidence threshold (β >= 0.70). High factual grounding.',
    },
    AMBIGUOUS: {
      label: 'CRAG: Ambiguous',
      color: '#fbbf24',
      bg: 'var(--crag-ambiguous-bg)',
      border: 'var(--crag-ambiguous-border)',
      icon: <AlertTriangle size={13} />,
      tooltip: 'Evidence had medium confidence (0.30 <= β < 0.70). Noisy passages filtered out.',
    },
    INCORRECT: {
      label: 'CRAG: Incorrect',
      color: '#fb7185',
      bg: 'var(--crag-incorrect-bg)',
      border: 'var(--crag-incorrect-border)',
      icon: <XCircle size={13} />,
      tooltip: 'Evidence confidence low (β < 0.30). Triggered corrective query reformulation.',
    },
  };

  const item = decisionMap[decision] || decisionMap.CORRECT;

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }} className={className}>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          padding: '2px 8px',
          borderRadius: '6px',
          fontSize: '0.75rem',
          fontWeight: 600,
          background: item.bg,
          color: item.color,
          border: `1px solid ${item.border}`,
          fontFamily: 'var(--font-mono)',
        }}
        title={item.tooltip}
      >
        {item.icon}
        {item.label}
      </span>

      {attempts > 1 && (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '3px',
            padding: '2px 7px',
            borderRadius: '6px',
            fontSize: '0.7rem',
            fontWeight: 500,
            background: 'rgba(255, 255, 255, 0.05)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border-subtle)',
          }}
          title={`Query reformulated and retrieved ${attempts} times by CRAG retry loop`}
        >
          <RotateCcw size={11} /> {attempts} attempts
        </span>
      )}
    </div>
  );
};
