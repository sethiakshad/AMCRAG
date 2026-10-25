/**
 * src/components/chat/LatencyWaterfall.tsx
 * Quiet, editorial telemetry breakdown showing per-stage latency across the pipeline.
 * Follows Claude muted warm palette.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Clock } from 'lucide-react';
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
      color: 'var(--text-400)',
    },
    {
      label: 'Parallel Retrieval & Fusion',
      ms: latency?.retrieval_ms || 0,
      color: 'var(--brand-clay)',
    },
    {
      label: 'CRAG Gate & Reformulation',
      ms: latency?.crag_evaluation_ms || 0,
      color: 'var(--brand)',
    },
    {
      label: 'Context Building & Citations',
      ms: latency?.context_building_ms || 0,
      color: 'var(--text-300)',
    },
    {
      label: 'LLM Answer Generation',
      ms: latency?.generation_ms || 0,
      color: 'var(--brand-active)',
    },
  ];

  return (
    <div
      style={{
        marginTop: '10px',
        padding: '8px 12px',
        borderRadius: 'var(--radius-md)',
        background: 'var(--bg-200)',
        border: 'var(--border-w) solid var(--border-100)',
        fontSize: '12px',
        color: 'var(--text-200)',
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Clock size={13} style={{ color: 'var(--brand-clay)' }} />
          <span>Pipeline execution:</span>
          <strong style={{ color: 'var(--text-100)', fontFamily: 'var(--font-mono)' }}>
            {formatDuration(finalTotal)}
          </strong>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-300)' }}>
          <span>{isExpanded ? 'Hide' : 'Details'}</span>
          {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </div>
      </div>

      {isExpanded && latency && (
        <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px', paddingTop: '8px', borderTop: 'var(--border-w) solid var(--border-100)' }}>
          {stages.map((stage) => {
            const pct = finalTotal > 0 ? Math.min(100, Math.max(3, (stage.ms / finalTotal) * 100)) : 0;
            return (
              <div key={stage.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px', fontSize: '11.5px', color: 'var(--text-200)' }}>
                  <span>{stage.label}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-100)' }}>
                    {formatDuration(stage.ms)}
                  </span>
                </div>
                <div
                  style={{
                    height: '3px',
                    width: '100%',
                    background: 'var(--bg-300)',
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
