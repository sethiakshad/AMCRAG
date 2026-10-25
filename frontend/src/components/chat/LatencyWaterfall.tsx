/**
 * src/components/chat/LatencyWaterfall.tsx
 * Visual waterfall display showing per-stage latency breakdown across the RAG pipeline.
 */

import React, { useState } from 'react';
import { Zap, ChevronDown, ChevronUp } from 'lucide-react';
import { LatencyBreakdown } from '../../types/amcrag';
import { formatDuration } from '../../utils/formatters';

export interface LatencyWaterfallProps {
  latency?: LatencyBreakdown | null;
  totalMs?: number | null;
}

export const LatencyWaterfall: React.FC<LatencyWaterfallProps> = ({ latency, totalMs }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const finalTotal = latency?.total_ms || totalMs || 0;
  if (finalTotal <= 0 && !latency) return null;

  const stages = [
    {
      label: 'Query Analysis',
      ms: latency?.query_analysis_ms || 0,
      color: '#818cf8',
    },
    {
      label: 'Parallel Retrieval & Fusion',
      ms: latency?.retrieval_ms || 0,
      color: '#38bdf8',
    },
    {
      label: 'CRAG Gate & Reformulation',
      ms: latency?.crag_evaluation_ms || 0,
      color: '#c084fc',
    },
    {
      label: 'Context Building & Citations',
      ms: latency?.context_building_ms || 0,
      color: '#fbbf24',
    },
    {
      label: 'LLM Answer Generation',
      ms: latency?.generation_ms || 0,
      color: '#34d399',
    },
  ];

  return (
    <div
      style={{
        marginTop: '0.75rem',
        padding: '0.5rem 0.75rem',
        borderRadius: '8px',
        background: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid var(--border-subtle)',
        fontSize: '0.75rem',
      }}
    >
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
          <Zap size={13} style={{ color: '#f59e0b' }} />
          <span>Pipeline Telemetry:</span>
          <strong style={{ color: '#ffffff' }}>{formatDuration(finalTotal)}</strong>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-muted)' }}>
          <span>{isExpanded ? 'Hide Breakdown' : 'Show Breakdown'}</span>
          {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </div>
      </div>

      {isExpanded && latency && (
        <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {stages.map((stage) => {
            const pct = finalTotal > 0 ? Math.min(100, Math.max(3, (stage.ms / finalTotal) * 100)) : 0;
            return (
              <div key={stage.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px', color: 'var(--text-secondary)' }}>
                  <span>{stage.label}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: '#ffffff' }}>
                    {formatDuration(stage.ms)}
                  </span>
                </div>
                <div
                  style={{
                    height: '4px',
                    width: '100%',
                    background: 'rgba(255, 255, 255, 0.06)',
                    borderRadius: '2px',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${pct}%`,
                      backgroundColor: stage.color,
                      borderRadius: '2px',
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
