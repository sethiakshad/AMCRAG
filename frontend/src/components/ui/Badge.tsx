/**
 * src/components/ui/Badge.tsx
 * Status and label badge component adhering to Claude design tokens.
 */

import React from 'react';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'brand' | 'success' | 'warning' | 'error' | 'neutral';
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  icon,
  className = '',
  onClick,
}) => {
  const variantStyles: Record<string, React.CSSProperties> = {
    brand: {
      background: 'var(--brand-tint)',
      color: 'var(--brand)',
      border: 'var(--border-w) solid rgba(51, 143, 255, 0.25)',
    },
    success: {
      background: 'rgba(23, 163, 74, 0.08)',
      color: 'var(--success)',
      border: 'var(--border-w) solid rgba(23, 163, 74, 0.25)',
    },
    warning: {
      background: 'rgba(234, 179, 8, 0.08)',
      color: 'var(--warning)',
      border: 'var(--border-w) solid rgba(234, 179, 8, 0.25)',
    },
    error: {
      background: 'rgba(181, 51, 51, 0.08)',
      color: 'var(--danger)',
      border: 'var(--border-w) solid rgba(181, 51, 51, 0.25)',
    },
    neutral: {
      background: 'var(--bg-300)',
      color: 'var(--text-200)',
      border: 'var(--border-w) solid var(--border-200)',
    },
  };

  const sizeStyles: Record<string, React.CSSProperties> = {
    sm: { padding: '1px 6px', fontSize: '11px' },
    md: { padding: '2px 8px', fontSize: '12px' },
  };

  return (
    <span
      className={className}
      style={{
        ...variantStyles[variant],
        ...sizeStyles[size],
        borderRadius: 'var(--radius-sm)',
        fontFamily: 'var(--font-mono)',
        fontWeight: 500,
        cursor: onClick ? 'pointer' : 'default',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        transition: 'all var(--dur-base)',
      }}
      onClick={onClick}
    >
      {icon}
      {children}
    </span>
  );
};
