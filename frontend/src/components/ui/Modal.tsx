/**
 * src/components/ui/Modal.tsx
 * Accessible dialog modal with quiet backdrop, hairline border, and Serif header.
 */

import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = '520px',
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
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-panel"
        style={{ maxWidth }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <h2>{title}</h2>
          <button
            onClick={onClose}
            className="btn-icon"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content body */}
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  );
};
