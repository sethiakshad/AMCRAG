/**
 * src/components/documents/DeleteConfirmModal.tsx
 * Destructive action confirmation dialog for removing documents from knowledge base.
 * Styled with Claude paper aesthetic.
 */

import React, { useState } from 'react';
import { AlertTriangle, Trash2 } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';

export interface DeleteConfirmModalProps {
  isOpen: boolean;
  docId: string | null;
  filename?: string;
  onClose: () => void;
  onConfirm: (docId: string) => Promise<void>;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  isOpen,
  docId,
  filename,
  onClose,
  onConfirm,
}) => {
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !docId) return null;

  const handleDelete = async () => {
    setIsDeleting(true);
    setError(null);
    try {
      await onConfirm(docId);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Deletion failed');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Delete Document" maxWidth="440px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
          <div
            style={{
              padding: '8px',
              borderRadius: '50%',
              background: 'rgba(181, 51, 51, 0.1)',
              color: 'var(--danger)',
              flexShrink: 0,
            }}
          >
            <AlertTriangle size={20} />
          </div>
          <div>
            <h4 style={{ fontSize: '15px', fontWeight: 500, color: 'var(--text-100)' }}>
              Purge from Knowledge Base?
            </h4>
            <p style={{ fontSize: '13px', color: 'var(--text-300)', marginTop: '4px', lineHeight: 1.5 }}>
              Are you sure you want to delete <strong style={{ color: 'var(--text-100)' }}>{filename || docId}</strong>?
              This action permanently purges all extracted text chunks, Qdrant dense vector embeddings, BM25 indices, and rendered 150 DPI page images.
            </p>
          </div>
        </div>

        {error && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(181, 51, 51, 0.08)',
              border: 'var(--border-w) solid rgba(181, 51, 51, 0.3)',
              color: 'var(--danger)',
              fontSize: '13px',
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '4px', paddingTop: '10px', borderTop: 'var(--border-w) solid var(--border-100)' }}>
          <Button variant="secondary" onClick={onClose} disabled={isDeleting}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={handleDelete}
            isLoading={isDeleting}
            icon={<Trash2 size={14} />}
          >
            Confirm Delete
          </Button>
        </div>
      </div>
    </Modal>
  );
};
