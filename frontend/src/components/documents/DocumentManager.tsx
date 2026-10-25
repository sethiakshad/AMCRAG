/**
 * src/components/documents/DocumentManager.tsx
 * Orchestrates document upload, catalog browsing, manifest inspection, and deletion.
 */

import React, { useState } from 'react';
import { Upload, RefreshCw, Database } from 'lucide-react';
import { Button } from '../ui/Button';
import { DocumentList } from './DocumentList';
import { UploadModal } from './UploadModal';
import { DocumentDetailModal } from './DocumentDetailModal';
import { DeleteConfirmModal } from './DeleteConfirmModal';
import { useDocuments } from '../../hooks/useDocuments';

export interface DocumentManagerProps {
  onChatWithDoc: (docId: string) => void;
}

export const DocumentManager: React.FC<DocumentManagerProps> = ({ onChatWithDoc }) => {
  const {
    documents,
    allDocuments,
    isLoading,
    isUploading,
    searchQuery,
    setSearchQuery,
    refreshDocuments,
    upload,
    remove,
  } = useDocuments();

  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedDetailDocId, setSelectedDetailDocId] = useState<string | null>(null);
  const [docToDelete, setDocToDelete] = useState<{ id: string; name: string } | null>(null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', width: '100%', maxWidth: '1080px', margin: '0 auto' }}>
      {/* View Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={24} style={{ color: 'var(--brand-primary)' }} />
            Knowledge Base Catalog
          </h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {allDocuments.length} PDF {allDocuments.length === 1 ? 'document' : 'documents'} indexed with dense BGE vectors, BM25 tokens, and ColPali 150 DPI page visual representations.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Button
            variant="secondary"
            size="md"
            onClick={refreshDocuments}
            isLoading={isLoading}
            icon={<RefreshCw size={15} />}
          >
            Refresh
          </Button>

          <Button
            variant="primary"
            size="md"
            onClick={() => setIsUploadModalOpen(true)}
            icon={<Upload size={15} />}
          >
            Upload PDF
          </Button>
        </div>
      </div>

      {/* Catalog Listing */}
      <DocumentList
        documents={documents}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onViewDetail={(id) => setSelectedDetailDocId(id)}
        onDeleteDoc={(id, name) => setDocToDelete({ id, name })}
        onChatWithDoc={onChatWithDoc}
        isLoading={isLoading}
      />

      {/* Modals */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={upload}
        isUploading={isUploading}
      />

      <DocumentDetailModal
        docId={selectedDetailDocId}
        onClose={() => setSelectedDetailDocId(null)}
        onChatWithDoc={onChatWithDoc}
      />

      <DeleteConfirmModal
        isOpen={Boolean(docToDelete)}
        docId={docToDelete?.id || null}
        filename={docToDelete?.name}
        onClose={() => setDocToDelete(null)}
        onConfirm={remove}
      />
    </div>
  );
};
