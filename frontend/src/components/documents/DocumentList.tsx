/**
 * src/components/documents/DocumentList.tsx
 * Searchable catalog table/cards of all indexed documents in the knowledge base.
 */

import React from 'react';
import {
  FileText,
  Layers,
  Trash2,
  ExternalLink,
  MessageSquare,
  Search,
  HardDrive,
  Calendar,
  Eye,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { DocumentSummary } from '../../types/amcrag';
import { formatBytes, formatRelativeTime } from '../../utils/formatters';

export interface DocumentListProps {
  documents: DocumentSummary[];
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onViewDetail: (docId: string) => void;
  onDeleteDoc: (docId: string, filename: string) => void;
  onChatWithDoc: (docId: string) => void;
  isLoading: boolean;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  searchQuery,
  onSearchChange,
  onViewDetail,
  onDeleteDoc,
  onChatWithDoc,
  isLoading,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Search Input Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '0.5rem 0.875rem',
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <Search size={16} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search documents by filename or ID..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              fontSize: '0.875rem',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.75rem',
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Catalog Listing */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
          Loading document catalog...
        </div>
      ) : documents.length === 0 ? (
        <div
          style={{
            padding: '3rem 1.5rem',
            textAlign: 'center',
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px dashed var(--border-subtle)',
            borderRadius: '12px',
          }}
        >
          <FileText size={36} style={{ color: 'var(--text-muted)', margin: '0 auto 0.75rem auto' }} />
          <h4 style={{ fontSize: '1rem', fontWeight: 600, color: '#ffffff' }}>
            {searchQuery ? 'No matching documents found' : 'No documents indexed yet'}
          </h4>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {searchQuery
              ? 'Try adjusting your search terms.'
              : 'Upload PDF research papers or reports to populate the knowledge base.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {documents.map((doc) => (
            <div
              key={doc.document_id}
              className="glass-panel"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1rem 1.25rem',
                gap: '1rem',
                flexWrap: 'wrap',
                transition: 'border-color 0.2s ease',
              }}
            >
              {/* Document Identity */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: '240px' }}>
                <div
                  style={{
                    padding: '10px',
                    borderRadius: '8px',
                    background: 'rgba(99, 102, 241, 0.12)',
                    color: '#818cf8',
                    flexShrink: 0,
                  }}
                >
                  <FileText size={22} />
                </div>
                <div>
                  <div
                    style={{
                      fontSize: '0.9375rem',
                      fontWeight: 600,
                      color: '#ffffff',
                      cursor: 'pointer',
                    }}
                    onClick={() => onViewDetail(doc.document_id)}
                    title="Click to view manifest and page images"
                  >
                    {doc.filename}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    <code style={{ fontFamily: 'var(--font-mono)' }}>{doc.document_id}</code>
                  </div>
                </div>
              </div>

              {/* Statistics Pill Cluster */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Total Pages">
                  <Layers size={14} style={{ color: 'var(--text-muted)' }} />
                  <span><strong>{doc.page_count}</strong> pages</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Indexed Text Chunks">
                  <FileText size={14} style={{ color: '#818cf8' }} />
                  <span><strong>{doc.chunk_count}</strong> chunks</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="File Size">
                  <HardDrive size={14} style={{ color: 'var(--text-muted)' }} />
                  <span>{formatBytes(doc.file_size_bytes)}</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Upload Timestamp">
                  <Calendar size={14} style={{ color: 'var(--text-muted)' }} />
                  <span>{formatRelativeTime(doc.upload_timestamp)}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => onChatWithDoc(doc.document_id)}
                  title="Query this document specifically"
                  icon={<MessageSquare size={13} />}
                >
                  Query
                </Button>

                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => onViewDetail(doc.document_id)}
                  title="Inspect manifest and rendered 150 DPI page gallery"
                  icon={<Eye size={13} />}
                >
                  Inspect
                </Button>

                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => onDeleteDoc(doc.document_id, doc.filename)}
                  title="Purge document from vector store"
                  icon={<Trash2 size={13} />}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
