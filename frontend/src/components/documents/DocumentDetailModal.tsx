/**
 * src/components/documents/DocumentDetailModal.tsx
 * Manifest inspector and 150 DPI rendered page gallery modal.
 */

import React, { useEffect, useState } from 'react';
import {
  FileText,
  Layers,
  Image as ImageIcon,
  Calendar,
  HardDrive,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  X,
} from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { getDocumentDetail } from '../../services/api';
import { DocumentDetailResponse } from '../../types/amcrag';
import { formatBytes, formatRelativeTime } from '../../utils/formatters';
import { resolvePageImageUrl } from '../../utils/imageUrl';

export interface DocumentDetailModalProps {
  docId: string | null;
  onClose: () => void;
  onChatWithDoc?: (docId: string) => void;
}

export const DocumentDetailModal: React.FC<DocumentDetailModalProps> = ({
  docId,
  onClose,
  onChatWithDoc,
}) => {
  const [detail, setDetail] = useState<DocumentDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!docId) {
      setDetail(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    getDocumentDetail(docId)
      .then((data) => setDetail(data))
      .catch((err) => setError(err.message || 'Failed to load document manifest'))
      .finally(() => setIsLoading(false));
  }, [docId]);

  if (!docId) return null;

  return (
    <>
      <Modal isOpen={Boolean(docId)} onClose={onClose} title={detail?.filename || 'Document Manifest'} maxWidth="840px">
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-secondary)' }}>
            Loading document manifest and page images...
          </div>
        ) : error ? (
          <div style={{ padding: '1rem', color: '#fb7185', background: 'rgba(244, 63, 94, 0.1)', borderRadius: '8px' }}>
            {error}
          </div>
        ) : detail ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Metadata Summary Banner */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: '12px',
                padding: '1rem',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Layers size={13} /> Pages
                </div>
                <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#ffffff', marginTop: '2px' }}>
                  {detail.page_count}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <FileText size={13} /> Text Chunks
                </div>
                <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#818cf8', marginTop: '2px' }}>
                  {detail.chunk_count}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <ImageIcon size={13} /> Page Images
                </div>
                <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#38bdf8', marginTop: '2px' }}>
                  {detail.image_count}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <HardDrive size={13} /> File Size
                </div>
                <div style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#ffffff', marginTop: '4px' }}>
                  {formatBytes(detail.metadata?.file_size_bytes)}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Calendar size={13} /> Ingested
                </div>
                <div style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#ffffff', marginTop: '4px' }}>
                  {formatRelativeTime(detail.metadata?.upload_timestamp)}
                </div>
              </div>
            </div>

            {/* Document ID & Actions */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                background: 'rgba(0, 0, 0, 0.25)',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.8125rem',
              }}
            >
              <div>
                <span style={{ color: 'var(--text-muted)' }}>Document ID: </span>
                <code style={{ color: '#a5b4fc', fontFamily: 'var(--font-mono)' }}>{detail.document_id}</code>
              </div>
              {onChatWithDoc && (
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    onChatWithDoc(detail.document_id);
                    onClose();
                  }}
                  icon={<ExternalLink size={13} />}
                >
                  Query Document
                </Button>
              )}
            </div>

            {/* Rendered 150 DPI Page Image Gallery */}
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '0.75rem',
                }}
              >
                <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
                  ColPali Visual Pages ({detail.page_images.length})
                </h4>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  150 DPI PNG rasterizations indexed for multimodal search
                </span>
              </div>

              {detail.page_images.length === 0 ? (
                <div
                  style={{
                    padding: '2rem',
                    textAlign: 'center',
                    background: 'rgba(255, 255, 255, 0.02)',
                    borderRadius: '8px',
                    color: 'var(--text-muted)',
                    fontSize: '0.8125rem',
                  }}
                >
                  No page images discovered in runtime storage for this document.
                </div>
              ) : (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
                    gap: '12px',
                    maxHeight: '340px',
                    overflowY: 'auto',
                    padding: '4px',
                  }}
                >
                  {detail.page_images.map((imgPath, idx) => {
                    const resolvedUrl = resolvePageImageUrl(imgPath);
                    return (
                      <div
                        key={imgPath}
                        onClick={() => setLightboxIndex(idx)}
                        style={{
                          borderRadius: '8px',
                          overflow: 'hidden',
                          border: '1px solid var(--border-subtle)',
                          background: '#090e17',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          display: 'flex',
                          flexDirection: 'column',
                          position: 'relative',
                        }}
                      >
                        <div
                          style={{
                            aspectRatio: '0.707',
                            overflow: 'hidden',
                            position: 'relative',
                            background: '#000',
                          }}
                        >
                          <img
                            src={resolvedUrl}
                            alt={`Page ${idx + 1}`}
                            loading="lazy"
                            style={{
                              width: '100%',
                              height: '100%',
                              objectFit: 'contain',
                              transition: 'transform 0.2s ease',
                            }}
                            onError={(e) => {
                              // Fallback display if static mount is not configured yet
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                          <div
                            style={{
                              position: 'absolute',
                              inset: 0,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              background: 'rgba(0, 0, 0, 0.4)',
                              opacity: 0,
                              transition: 'opacity 0.2s ease',
                            }}
                            className="hover:opacity-100"
                          >
                            <Maximize2 size={18} color="#fff" />
                          </div>
                        </div>
                        <div
                          style={{
                            padding: '4px 6px',
                            fontSize: '0.75rem',
                            textAlign: 'center',
                            background: 'rgba(255, 255, 255, 0.03)',
                            color: 'var(--text-secondary)',
                            fontWeight: 500,
                          }}
                        >
                          Page {idx + 1}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Modal>

      {/* Full-Screen Image Lightbox */}
      {lightboxIndex !== null && detail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.92)',
            zIndex: 1100,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={() => setLightboxIndex(null)}
        >
          {/* Lightbox Toolbar */}
          <div
            style={{
              position: 'absolute',
              top: '1rem',
              right: '1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              zIndex: 1110,
            }}
          >
            <span style={{ color: '#fff', fontSize: '0.875rem', fontWeight: 500 }}>
              Page {lightboxIndex + 1} of {detail.page_images.length}
            </span>
            <button
              onClick={() => setLightboxIndex(null)}
              className="btn-icon"
              style={{ color: '#fff', background: 'rgba(255,255,255,0.1)' }}
            >
              <X size={20} />
            </button>
          </div>

          {/* Navigation Controls */}
          {lightboxIndex > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setLightboxIndex((prev) => (prev !== null ? prev - 1 : 0));
              }}
              className="btn-icon"
              style={{
                position: 'absolute',
                left: '1rem',
                color: '#fff',
                background: 'rgba(255,255,255,0.15)',
                padding: '12px',
              }}
            >
              <ChevronLeft size={28} />
            </button>
          )}

          {lightboxIndex < detail.page_images.length - 1 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setLightboxIndex((prev) => (prev !== null ? prev + 1 : 0));
              }}
              className="btn-icon"
              style={{
                position: 'absolute',
                right: '1rem',
                color: '#fff',
                background: 'rgba(255,255,255,0.15)',
                padding: '12px',
              }}
            >
              <ChevronRight size={28} />
            </button>
          )}

          {/* Large Image View */}
          <img
            src={resolvePageImageUrl(detail.page_images[lightboxIndex])}
            alt={`Page ${lightboxIndex + 1}`}
            style={{
              maxWidth: '90vw',
              maxHeight: '85vh',
              objectFit: 'contain',
              boxShadow: '0 10px 40px rgba(0,0,0,0.8)',
              borderRadius: '6px',
            }}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
};
