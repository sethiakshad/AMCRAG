/**
 * src/components/ui/Drawer.tsx
 * Slide-over drawer panel for Evidence Inspector and Query Configuration.
 */

import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  width?: string;
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  width = '520px',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div
        className="drawer-panel"
        style={{ width: `min(${width}, 100vw)` }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="drawer-header">
          <div>
            <h3>{title}</h3>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button onClick={onClose} className="btn-icon" aria-label="Close drawer">
            <X size={18} />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="drawer-body">
          {children}
        </div>
      </div>
    </div>
  );
};
