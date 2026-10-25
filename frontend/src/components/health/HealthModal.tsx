/**
 * src/components/health/HealthModal.tsx
 * Subsystem diagnostic matrix modal displaying operational state and readiness.
 */

import React from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCw,
  Server,
  Database,
  Cpu,
  Eye,
  Clock,
  Sparkles,
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
      icon: <Database size={18} className="text-indigo-400" />,
      status: health?.components?.vector_db ?? false,
    },
    {
      id: 'bm25',
      name: 'BM25 Lexical Keyword Engine',
      description: 'Sparse exact-term retrieval & rank reciprocal fusion',
      icon: <Server size={18} className="text-cyan-400" />,
      status: health?.components?.bm25 ?? false,
    },
    {
      id: 'crag',
      name: 'Adaptive CRAG Quality Gate',
      description: 'T5-Large confidence assessment & query reformulation loop',
      icon: <Cpu size={18} className="text-purple-400" />,
      status: health?.components?.crag ?? false,
    },
    {
      id: 'llm',
      name: 'Answer Generator LLM',
      description: 'Ollama Cloud (gemma4:31b) / Google Gemini API client',
      icon: <Sparkles size={18} className="text-amber-400" />,
      status: health?.components?.llm ?? false,
    },
    {
      id: 'colpali',
      name: 'ColPali Multimodal Visual Bridge',
      description: '150 DPI page image late-interaction VLM search',
      icon: <Eye size={18} className="text-pink-400" />,
      status: health?.components?.colpali ?? false,
    },
  ];

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="AMCRAG Subsystem Diagnostics" maxWidth="580px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Overall Status Banner */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1rem 1.25rem',
            borderRadius: '10px',
            background: isOffline
              ? 'rgba(244, 63, 94, 0.1)'
              : health?.status === 'healthy'
              ? 'rgba(16, 185, 129, 0.1)'
              : 'rgba(245, 158, 11, 0.1)',
            border: `1px solid ${
              isOffline
                ? 'rgba(244, 63, 94, 0.3)'
                : health?.status === 'healthy'
                ? 'rgba(16, 185, 129, 0.3)'
                : 'rgba(245, 158, 11, 0.3)'
            }`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {isOffline ? (
              <XCircle size={28} style={{ color: '#f43f5e' }} />
            ) : health?.status === 'healthy' ? (
              <CheckCircle2 size={28} style={{ color: '#10b981' }} />
            ) : (
              <AlertTriangle size={28} style={{ color: '#f59e0b' }} />
            )}
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.9375rem', color: '#ffffff' }}>
                {isOffline
                  ? 'Backend Server Unreachable'
                  : health?.status === 'healthy'
                  ? 'All Subsystems Operational'
                  : 'System Running in Degraded Mode'}
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                {isOffline
                  ? 'FastAPI server at http://localhost:8000 is not responding.'
                  : `Version ${health?.version || '1.0.0'} — Production Orchestrator`}
              </div>
            </div>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={onRefresh}
            isLoading={isLoading}
            icon={<RotateCw size={14} />}
          >
            Re-check
          </Button>
        </div>

        {/* Uptime and Service Info */}
        {!isOffline && health && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1.5rem',
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.8125rem',
              color: 'var(--text-secondary)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Clock size={15} style={{ color: 'var(--text-muted)' }} />
              <span>
                Uptime: <strong style={{ color: '#ffffff' }}>{formatUptime(health.uptime_seconds)}</strong>
              </span>
            </div>
            <div>
              Gateway: <strong style={{ color: '#ffffff' }}>FastAPI (Uvicorn)</strong>
            </div>
          </div>
        )}

        {/* Component Checklist */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
          <h4 style={{ fontSize: '0.8125rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
            Subsystem Status Matrix
          </h4>

          {componentsList.map((comp) => (
            <div
              key={comp.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.875rem 1rem',
                borderRadius: '8px',
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div
                  style={{
                    padding: '8px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.05)',
                  }}
                >
                  {comp.icon}
                </div>
                <div>
                  <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
                    {comp.name}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {comp.description}
                  </div>
                </div>
              </div>

              <div>
                {isOffline ? (
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Unknown</span>
                ) : comp.status ? (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: '#10b981',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      background: 'rgba(16, 185, 129, 0.1)',
                    }}
                  >
                    <CheckCircle2 size={13} /> Ready
                  </span>
                ) : (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: '#f59e0b',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      background: 'rgba(245, 158, 11, 0.1)',
                    }}
                  >
                    <AlertTriangle size={13} /> Fallback
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
