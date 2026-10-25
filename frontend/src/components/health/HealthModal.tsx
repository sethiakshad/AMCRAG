/**
 * src/components/health/HealthModal.tsx
 * Subsystem diagnostic matrix modal displaying operational readiness.
 * Styled with Claude paper aesthetic.
 */

import React from 'react';
import {
  Check,
  AlertTriangle,
  RotateCw,
  Server,
  Database,
  Cpu,
  Eye,
  Clock,
  Sparkles,
  X,
} from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { HealthResponse } from '../../types/amcrag';
import { formatUptime } from '../../utils/formatters';

export interface HealthModalProps {
  isOpen: boolean;
  onClose: () => void;
  health: HealthResponse | null;
  isOffline: boolean;
  isLoading: boolean;
  onRefresh: () => void;
}

export const HealthModal: React.FC<HealthModalProps> = ({
  isOpen,
  onClose,
  health,
  isOffline,
  isLoading,
  onRefresh,
}) => {
  const componentsList = [
    {
      id: 'vector_db',
      name: 'Qdrant Dense Vector Store',
      description: 'BAAI/bge-base-en-v1.5 dense semantic index & embeddings',
      icon: <Database size={16} />,
      status: health?.components?.vector_db ?? false,
    },
    {
      id: 'bm25',
      name: 'BM25 Lexical Keyword Engine',
      description: 'Sparse exact-term retrieval & rank reciprocal fusion (RRF k=60)',
      icon: <Server size={16} />,
      status: health?.components?.bm25 ?? false,
    },
    {
      id: 'crag',
      name: 'Adaptive CRAG Quality Gate',
      description: 'T5-Large confidence assessment & query reformulation loop',
      icon: <Cpu size={16} />,
      status: health?.components?.crag ?? false,
    },
    {
      id: 'llm',
      name: 'Answer Generator LLM',
      description: 'Ollama Cloud (gemma4:31b) / Google Gemini API client',
      icon: <Sparkles size={16} />,
      status: health?.components?.llm ?? false,
    },
    {
      id: 'colpali',
      name: 'ColPali Multimodal Visual Bridge',
      description: '150 DPI page image late-interaction VLM search',
      icon: <Eye size={16} />,
      status: health?.components?.colpali ?? false,
    },
  ];

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Subsystem Diagnostics" maxWidth="540px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Overall Status Banner */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '14px 16px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-100)',
            border: 'var(--border-w) solid var(--border-200)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: isOffline
                  ? 'var(--danger)'
                  : health?.status === 'healthy'
                  ? 'var(--success)'
                  : 'var(--warning)',
              }}
            />
            <div>
              <div style={{ fontWeight: 500, fontSize: '14.5px', color: 'var(--text-100)' }}>
                {isOffline
                  ? 'Backend Server Unreachable'
                  : health?.status === 'healthy'
                  ? 'All Subsystems Operational'
                  : 'System Running in Degraded Mode'}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-300)', marginTop: '2px' }}>
                {isOffline
                  ? 'FastAPI server at http://127.0.0.1:8001 is not responding.'
                  : `Version ${health?.version || '1.0.0'} — Production Orchestrator`}
              </div>
            </div>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={onRefresh}
            isLoading={isLoading}
            icon={<RotateCw size={13} />}
          >
            Refresh
          </Button>
        </div>

        {/* Uptime and Service Info */}
        {!isOffline && health && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1.5rem',
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-100)',
              border: 'var(--border-w) solid var(--border-100)',
              fontSize: '12.5px',
              color: 'var(--text-200)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Clock size={14} style={{ color: 'var(--text-300)' }} />
              <span>
                Uptime: <strong style={{ color: 'var(--text-100)', fontFamily: 'var(--font-mono)' }}>{formatUptime(health.uptime_seconds)}</strong>
              </span>
            </div>
            <div>
              Gateway: <strong style={{ color: 'var(--text-100)' }}>FastAPI (Uvicorn)</strong>
            </div>
          </div>
        )}

        {/* Component Checklist */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-400)' }}>
            Pipeline Subsystems
          </div>

          {componentsList.map((comp) => (
            <div
              key={comp.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-100)',
                border: 'var(--border-w) solid var(--border-200)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ color: 'var(--text-300)' }}>
                  {comp.icon}
                </div>
                <div>
                  <div style={{ fontSize: '13.5px', fontWeight: 500, color: 'var(--text-100)' }}>
                    {comp.name}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-300)' }}>
                    {comp.description}
                  </div>
                </div>
              </div>

              <div>
                {isOffline ? (
                  <span style={{ fontSize: '12px', color: 'var(--text-400)' }}>Unknown</span>
                ) : comp.status ? (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: 'var(--success)',
                      padding: '2px 7px',
                      borderRadius: 'var(--radius-sm)',
                      background: 'rgba(23, 163, 74, 0.08)',
                    }}
                  >
                    <Check size={12} strokeWidth={2.5} /> Ready
                  </span>
                ) : (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: 'var(--warning)',
                      padding: '2px 7px',
                      borderRadius: 'var(--radius-sm)',
                      background: 'rgba(234, 179, 8, 0.08)',
                    }}
                  >
                    <AlertTriangle size={12} /> Standby
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Modal>
  );
};
