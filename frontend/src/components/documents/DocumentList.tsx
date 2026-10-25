/**
 * src/components/documents/DocumentList.tsx
 * Searchable catalog table/cards of all indexed documents in the knowledge base.
 * Aligned with Claude design system.
 */

import React from 'react';
import {
  FileText,
  Layers,
  Trash2,
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
            padding: '6px 12px',
            background: 'var(--bg-000)',
            border: 'var(--border-w) solid var(--border-200)',
            borderRadius: 'var(--radius-md)',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <Search size={15} style={{ color: 'var(--text-300)' }} />
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
              color: 'var(--text-100)',
              fontSize: '14px',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange('')}
              className="btn-ghost"
              style={{ fontSize: '12px', padding: '0 4px', color: 'var(--text-300)' }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Catalog Listing */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-300)', fontSize: '14px' }}>
          Loading document catalog…
        </div>
      ) : documents.length === 0 ? (
        <div
          style={{
            padding: '3rem 1.5rem',
            textAlign: 'center',
            background: 'var(--bg-000)',
            border: 'var(--border-w) dashed var(--border-200)',
            borderRadius: 'var(--radius-lg)',
          }}
        >
          <FileText size={32} style={{ color: 'var(--text-400)', margin: '0 auto 0.75rem auto' }} />
          <h4 style={{ fontSize: '16px', fontWeight: 500, fontFamily: 'var(--font-serif)', color: 'var(--text-100)' }}>
            {searchQuery ? 'No matching documents found' : 'No documents indexed yet'}
          </h4>
          <p style={{ fontSize: '13px', color: 'var(--text-300)', marginTop: '4px' }}>
            {searchQuery
              ? 'Try adjusting your search terms.'
              : 'Upload PDF research papers or financial reports to populate the knowledge base.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {documents.map((doc) => (
            <div
              key={doc.document_id}
              className="doc-card"
            >
              {/* Document Identity */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: '220px' }}>
                <div
                  style={{
                    padding: '8px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-300)',
                    color: 'var(--brand-clay)',
                    flexShrink: 0,
                  }}
                >
                  <FileText size={20} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <div
                      style={{
                        fontSize: '14.5px',
                        fontWeight: 500,
                        color: 'var(--text-100)',
                        cursor: 'pointer',
                      }}
                      onClick={() => onViewDetail(doc.document_id)}
                      title="Click to view manifest and page images"
                    >
                      {doc.filename}
                    </div>
                    {(doc.is_scanned || doc.ocr_needed) && (
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 500,
                          padding: '1px 6px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'rgba(217, 119, 6, 0.12)',
                          color: '#d97706',
                          border: '1px solid rgba(217, 119, 6, 0.3)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                        }}
                        title="This PDF contains scanned page images without extractable digital text. OCR is required."
                      >
                        ⚠️ Scanned PDF / OCR Required
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-400)', marginTop: '2px' }}>
                    <code style={{ fontFamily: 'var(--font-mono)' }}>{doc.document_id}</code>
                  </div>
                </div>
              </div>

              {/* Statistics Cluster */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '13px', color: 'var(--text-200)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Total Pages">
                  <Layers size={13} style={{ color: 'var(--text-400)' }} />
                  <span><strong>{doc.page_count}</strong> pages</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Indexed Text Chunks">
                  <FileText size={13} style={{ color: 'var(--brand-clay)' }} />
                  <span><strong>{doc.chunk_count}</strong> chunks</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="File Size">
                  <HardDrive size={13} style={{ color: 'var(--text-400)' }} />
                  <span>{formatBytes(doc.file_size_bytes)}</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }} title="Upload Timestamp">
                  <Calendar size={13} style={{ color: 'var(--text-400)' }} />
                  <span>{formatRelativeTime(doc.upload_timestamp)}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Button
                  size="sm"
                  variant="primary"
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
