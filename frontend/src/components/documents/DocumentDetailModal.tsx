/**
 * src/components/documents/DocumentDetailModal.tsx
 * Manifest inspector and 150 DPI rendered page gallery modal.
 * Styled with Claude paper aesthetic.
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
      <Modal isOpen={Boolean(docId)} onClose={onClose} title={detail?.filename || 'Document Manifest'} maxWidth="780px">
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-300)', fontSize: '14px' }}>
            Loading document manifest and page images…
          </div>
        ) : error ? (
          <div style={{ padding: '12px 14px', color: 'var(--danger)', background: 'rgba(181, 51, 51, 0.08)', borderRadius: 'var(--radius-md)' }}>
            {error}
          </div>
        ) : detail ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Metadata Summary Banner */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '10px',
                padding: '14px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-100)',
                border: 'var(--border-w) solid var(--border-200)',
              }}
            >
              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-300)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Layers size={13} /> Pages
                </div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-100)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                  {detail.page_count}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-300)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <FileText size={13} /> Text Chunks
                </div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--brand-clay)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                  {detail.chunk_count}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-300)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <ImageIcon size={13} /> Page Images
                </div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--brand)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                  {detail.image_count}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-300)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <HardDrive size={13} /> File Size
                </div>
                <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)', marginTop: '4px' }}>
                  {formatBytes(detail.metadata?.file_size_bytes)}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-300)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Calendar size={13} /> Ingested
                </div>
                <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)', marginTop: '4px' }}>
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
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-100)',
                border: 'var(--border-w) solid var(--border-200)',
                fontSize: '13px',
              }}
            >
              <div>
                <span style={{ color: 'var(--text-300)' }}>Document ID: </span>
                <code style={{ color: 'var(--text-100)', fontFamily: 'var(--font-mono)' }}>{detail.document_id}</code>
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
                  marginBottom: '10px',
                }}
              >
                <h4 style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)' }}>
                  ColPali Visual Pages ({detail.page_images.length})
                </h4>
                <span style={{ fontSize: '12px', color: 'var(--text-300)' }}>
                  150 DPI PNG rasterizations indexed for multimodal search
                </span>
              </div>

              {detail.page_images.length === 0 ? (
                <div
                  style={{
                    padding: '2rem',
                    textAlign: 'center',
                    background: 'var(--bg-100)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-300)',
                    fontSize: '13px',
                  }}
                >
                  No page images discovered in runtime storage for this document.
                </div>
              ) : (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
                    gap: '10px',
                    maxHeight: '340px',
                    overflowY: 'auto',
                    padding: '2px',
                  }}
                >
                  {detail.page_images.map((imgPath, idx) => {
                    const resolvedUrl = resolvePageImageUrl(imgPath);
                    return (
                      <div
                        key={imgPath}
                        onClick={() => setLightboxIndex(idx)}
                        style={{
                          borderRadius: 'var(--radius-md)',
                          overflow: 'hidden',
                          border: 'var(--border-w) solid var(--border-200)',
                          background: 'var(--bg-100)',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          position: 'relative',
                          transition: 'border-color var(--dur-base)',
                        }}
                      >
                        <div
                          style={{
                            aspectRatio: '0.707',
                            overflow: 'hidden',
                            position: 'relative',
                            background: 'var(--bg-300)',
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
                            }}
                            onError={(e) => {
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
                              background: 'rgba(20, 20, 19, 0.4)',
                              opacity: 0,
                              transition: 'opacity var(--dur-base) ease',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                            onMouseLeave={(e) => (e.currentTarget.style.opacity = '0')}
                          >
                            <Maximize2 size={16} color="#fff" />
                          </div>
                        </div>
                        <div
                          style={{
                            padding: '4px 6px',
                            fontSize: '12px',
                            textAlign: 'center',
                            background: 'var(--bg-200)',
                            color: 'var(--text-200)',
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
            background: 'rgba(20, 20, 19, 0.88)',
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
            <span style={{ color: '#fff', fontSize: '13px', fontWeight: 500 }}>
              Page {lightboxIndex + 1} of {detail.page_images.length}
            </span>
            <button
              onClick={() => setLightboxIndex(null)}
              className="btn-icon"
              style={{ color: '#fff', background: 'rgba(255,255,255,0.1)' }}
            >
              <X size={18} />
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
                width: '40px',
                height: '40px',
              }}
            >
              <ChevronLeft size={24} />
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
                width: '40px',
                height: '40px',
              }}
            >
              <ChevronRight size={24} />
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
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              borderRadius: 'var(--radius-md)',
            }}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
};
