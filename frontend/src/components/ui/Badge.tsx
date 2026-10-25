/**
 * src/components/ui/Badge.tsx
 * Status and label badge component.
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
  const variantStyles = {
    brand: {
      background: 'rgba(99, 102, 241, 0.15)',
      color: '#a5b4fc',
      border: '1px solid rgba(99, 102, 241, 0.35)',
    },
    success: {
      background: 'var(--crag-correct-bg)',
      color: 'var(--crag-correct-text)',
      border: '1px solid var(--crag-correct-border)',
    },
    warning: {
      background: 'var(--crag-ambiguous-bg)',
      color: 'var(--crag-ambiguous-text)',
      border: '1px solid var(--crag-ambiguous-border)',
    },
    error: {
      background: 'var(--crag-incorrect-bg)',
      color: 'var(--crag-incorrect-text)',
      border: '1px solid var(--crag-incorrect-border)',
    },
    neutral: {
      background: 'rgba(255, 255, 255, 0.06)',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border-subtle)',
    },
  };

  const sizeStyles = {
    sm: { padding: '2px 6px', fontSize: '0.7rem' },
    md: { padding: '3px 9px', fontSize: '0.75rem' },
  };

  return (
    <span
      className={`inline-flex items-center gap-1 font-medium rounded ${className}`}
      style={{
        ...variantStyles[variant],
        ...sizeStyles[size],
        borderRadius: '6px',
        cursor: onClick ? 'pointer' : 'default',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
      }}
      onClick={onClick}
    >
      {icon}
      {children}
    </span>
  );
};
