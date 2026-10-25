/**
 * src/components/health/HealthIndicator.tsx
 * Status indicator pill showing live backend connection state.
 * Follows Claude design tokens (no neon glow).
 */

import React, { useState } from 'react';
import { HealthResponse } from '../../types/amcrag';
import { HealthModal } from './HealthModal';

export interface HealthIndicatorProps {
  health: HealthResponse | null;
  isLoading: boolean;
  isOffline: boolean;
  onRefresh: () => void;
}

export const HealthIndicator: React.FC<HealthIndicatorProps> = ({
  health,
  isLoading,
  isOffline,
  onRefresh,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  let statusLabel = 'Connecting…';
  let dotColor = 'var(--text-400)';

  if (isOffline) {
    statusLabel = 'Offline';
    dotColor = 'var(--danger)';
  } else if (health) {
    if (health.status === 'healthy') {
      statusLabel = 'Online';
      dotColor = 'var(--success)';
    } else {
      statusLabel = 'Degraded';
      dotColor = 'var(--warning)';
    }
  }

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '7px',
          padding: '3px 10px',
          borderRadius: 'var(--radius-full)',
          background: 'var(--bg-300)',
          border: 'var(--border-w) solid var(--border-200)',
          color: 'var(--text-200)',
          fontSize: '12px',
          cursor: 'pointer',
          transition: 'all var(--dur-base)',
        }}
        title="View AMCRAG pipeline subsystem diagnostics"
      >
        <span
          style={{
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            backgroundColor: dotColor,
          }}
        />
        <span style={{ fontWeight: 500 }}>{statusLabel}</span>
      </button>

      <HealthModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        health={health}
        isOffline={isOffline}
        isLoading={isLoading}
        onRefresh={onRefresh}
      />
    </>
  );
};
