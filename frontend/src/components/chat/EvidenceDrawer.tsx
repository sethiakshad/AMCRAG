/**
 * src/components/chat/EvidenceDrawer.tsx
 * Slide-over evidence inspector displaying factual provenance records and 150 DPI page images.
 */

import React, { useState } from 'react';
import {
  FileText,
  Image as ImageIcon,
  Layers,
  Award,
  Maximize2,
  X,
  ExternalLink,
} from 'lucide-react';
import { Drawer } from '../ui/Drawer';
import { SourceMetadata } from '../../types/amcrag';
import { resolvePageImageUrl } from '../../utils/imageUrl';

export interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  sources: SourceMetadata[];
  visualInputs?: string[];
  activeEvidenceId?: string | null;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  isOpen,
  onClose,
  sources,
  visualInputs = [],
  activeEvidenceId,
}) => {
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

  return (
    <>
      <Drawer
        isOpen={isOpen}
        onClose={onClose}
        title="Evidence & Provenance Inspector"
        subtitle={`${sources.length} retrieved citation ${sources.length === 1 ? 'passage' : 'passages'} grounded in context`}
        width="540px"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {sources.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
              No evidence sources attached to this query response.
            </div>
          ) : (
            sources.map((src) => {
              const isSelected = activeEvidenceId === src.evidence_id;

              // Check if there is an associated visual page image
              const matchedVisualPath = visualInputs.find((p) =>
                src.page ? p.includes(`page_${src.page}.png`) : false
              );

              return (
                <div
                  key={src.evidence_id}
                  id={`evidence-${src.evidence_id}`}
                  style={{
                    padding: '1.125rem',
                    borderRadius: '12px',
                    background: isSelected ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                    border: `1px solid ${
                      isSelected ? 'rgba(99, 102, 241, 0.5)' : 'var(--border-subtle)'
                    }`,
                    transition: 'all 0.2s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.75rem',
                  }}
                >
                  {/* Evidence Header */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '0.8125rem',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: 'rgba(99, 102, 241, 0.2)',
                          color: '#a5b4fc',
                          border: '1px solid rgba(99, 102, 241, 0.4)',
                        }}
                      >
                        [{src.evidence_id}]
                      </span>
                      <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#ffffff' }}>
                        {src.document}
                      </span>
                    </div>

                    {src.rank !== null && src.rank !== undefined && (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          fontSize: '0.75rem',
                          color: 'var(--text-muted)',
                        }}
                        title="Fusion rank position"
                      >
                        <Award size={13} style={{ color: '#f59e0b' }} /> Rank #{src.rank}
                      </span>
                    )}
                  </div>

                  {/* Badges: Page and Modality */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {src.page && (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.75rem',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: 'rgba(255, 255, 255, 0.05)',
                          color: 'var(--text-secondary)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <Layers size={12} /> Page {src.page}
                      </span>
                    )}

                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.75rem',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background:
                          src.type === 'visual'
                            ? 'rgba(236, 72, 153, 0.1)'
                            : 'rgba(56, 189, 248, 0.1)',
                        color: src.type === 'visual' ? '#f472b6' : '#38bdf8',
                        border: `1px solid ${
                          src.type === 'visual'
                            ? 'rgba(236, 72, 153, 0.3)'
                            : 'rgba(56, 189, 248, 0.3)'
                        }`,
                      }}
                    >
                      {src.type === 'visual' ? <ImageIcon size={12} /> : <FileText size={12} />}
                      {src.type === 'visual' ? 'ColPali Visual Page' : 'Hybrid Text Chunk'}
                    </span>
                  </div>

                  {/* Chunk Reference */}
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Chunk ID: <code style={{ fontFamily: 'var(--font-mono)' }}>{src.chunk_id}</code>
                  </div>

                  {/* Visual Page Image Preview if available */}
                  {matchedVisualPath && (
                    <div style={{ marginTop: '0.25rem' }}>
                      <div
                        style={{
                          position: 'relative',
                          borderRadius: '8px',
                          overflow: 'hidden',
                          border: '1px solid var(--border-medium)',
                          background: '#090e17',
                          cursor: 'pointer',
                          maxHeight: '180px',
                        }}
                        onClick={() => setLightboxUrl(resolvePageImageUrl(matchedVisualPath))}
                      >
                        <img
                          src={resolvePageImageUrl(matchedVisualPath)}
                          alt={`Page ${src.page}`}
                          style={{
                            width: '100%',
                            height: '180px',
                            objectFit: 'cover',
                            objectPosition: 'top',
                          }}
                        />
                        <div
                          style={{
                            position: 'absolute',
                            inset: 0,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'rgba(0, 0, 0, 0.5)',
                            gap: '6px',
                            color: '#ffffff',
                            fontSize: '0.8125rem',
                            fontWeight: 600,
                          }}
                        >
                          <Maximize2 size={16} /> Click to Inspect Page Image
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </Drawer>

      {/* Lightbox for Image Preview */}
      {lightboxUrl && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.9)',
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
          }}
          onClick={() => setLightboxUrl(null)}
        >
          <button
            onClick={() => setLightboxUrl(null)}
            className="btn-icon"
            style={{ position: 'absolute', top: '1.5rem', right: '1.5rem', color: '#fff' }}
          >
            <X size={24} />
          </button>
          <img
            src={lightboxUrl}
            alt="Page Evidence Preview"
            style={{
              maxWidth: '90vw',
              maxHeight: '85vh',
              objectFit: 'contain',
              borderRadius: '8px',
              boxShadow: '0 10px 40px rgba(0,0,0,0.8)',
            }}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
};
