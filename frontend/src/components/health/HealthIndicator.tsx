/**
 * src/components/health/HealthIndicator.tsx
 * Status indicator pill in the navbar showing live backend connection state.
 */

import React, { useState } from 'react';
import { Activity } from 'lucide-react';
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

  let statusLabel = 'Connecting...';
  let dotColor = '#94a3b8';
  let badgeBorder = 'rgba(255, 255, 255, 0.1)';
  let badgeBg = 'rgba(255, 255, 255, 0.04)';

  if (isOffline) {
    statusLabel = 'Offline';
    dotColor = '#f43f5e';
    badgeBorder = 'rgba(244, 63, 94, 0.3)';
    badgeBg = 'rgba(244, 63, 94, 0.1)';
  } else if (health) {
    if (health.status === 'healthy') {
      statusLabel = 'System Online';
      dotColor = '#10b981';
      badgeBorder = 'rgba(16, 185, 129, 0.3)';
      badgeBg = 'rgba(16, 185, 129, 0.08)';
    } else {
      statusLabel = 'Degraded';
      dotColor = '#f59e0b';
      badgeBorder = 'rgba(245, 158, 11, 0.3)';
      badgeBg = 'rgba(245, 158, 11, 0.08)';
    }
  }

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '5px 12px',
          borderRadius: '9999px',
          background: badgeBg,
          border: `1px solid ${badgeBorder}`,
          color: 'var(--text-primary)',
          fontSize: '0.8125rem',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
        title="Click to view subsystem health diagnostics"
      >
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: dotColor,
            boxShadow: `0 0 8px ${dotColor}`,
          }}
        />
        <Activity size={13} style={{ color: dotColor }} />
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
