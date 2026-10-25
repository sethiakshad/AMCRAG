/**
 * src/components/ui/Button.tsx
 * Reusable button with variants, loading spinners, and icons.
 * Follows Claude.ai quiet button specifications.
 */

import React from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'icon';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  icon,
  className = '',
  disabled,
  style,
  ...props
}) => {
  let variantClass = 'btn-primary';
  if (variant === 'secondary' || variant === 'outline') variantClass = 'btn-secondary';
  if (variant === 'danger') variantClass = 'btn-danger';
  if (variant === 'ghost') variantClass = 'btn-ghost';
  if (variant === 'icon') variantClass = 'btn-icon';

  const sizeStyles: Record<string, React.CSSProperties> = {
    sm: { height: '30px', padding: '0 10px', fontSize: '13px' },
    md: { height: '34px', padding: '0 14px', fontSize: '13.5px' },
    lg: { height: '38px', padding: '0 18px', fontSize: '14.5px' },
  };

  const finalStyle = variant !== 'icon' ? { ...sizeStyles[size], ...style } : style;

  return (
    <button
      className={`${variant === 'icon' ? 'btn-icon' : 'btn'} ${variantClass} ${className}`}
      style={finalStyle}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 style={{ animation: 'spin 1s linear infinite' }} size={size === 'sm' ? 13 : 15} />
      ) : (
        icon
      )}
      {children}
    </button>
  );
};
