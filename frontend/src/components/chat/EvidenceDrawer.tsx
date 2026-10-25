/**
 * src/components/chat/EvidenceDrawer.tsx
 * Slide-over evidence inspector displaying factual provenance records and 150 DPI page images.
 * Follows Claude design tokens with clean hairline cards and warm accents.
 */

import React, { useState } from 'react';
import {
  FileText,
  Image as ImageIcon,
  Layers,
  Award,
  Maximize2,
  X,
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
        title="Evidence & Citations"
        subtitle={`${sources.length} retrieved citation ${sources.length === 1 ? 'passage' : 'passages'} grounded in context`}
        width="540px"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {sources.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-400)' }}>
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
                    padding: '14px 16px',
                    borderRadius: 'var(--radius-lg)',
                    background: isSelected ? 'var(--brand-tint)' : 'var(--bg-100)',
                    border: `var(--border-w) solid ${
                      isSelected ? 'var(--brand)' : 'var(--border-200)'
                    }`,
                    transition: 'all var(--dur-base) ease',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                  }}
                >
                  {/* Evidence Header */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '12px',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 600,
                          padding: '1px 7px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--brand)',
                          color: 'var(--on-brand)',
                        }}
                      >
                        [{src.evidence_id}]
                      </span>
                      <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-100)' }}>
                        {src.document}
                      </span>
                    </div>

                    {src.rank !== null && src.rank !== undefined && (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          fontSize: '12px',
                          color: 'var(--text-300)',
                        }}
                        title="Fusion rank position"
                      >
                        <Award size={13} style={{ color: 'var(--brand-clay)' }} /> Rank #{src.rank}
                      </span>
                    )}
                  </div>

                  {/* Badges: Page and Modality */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {src.page && (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '12px',
                          padding: '1px 7px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--bg-300)',
                          color: 'var(--text-200)',
                          border: 'var(--border-w) solid var(--border-200)',
                        }}
                      >
                        <Layers size={11} /> Page {src.page}
                      </span>
                    )}

                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '12px',
                        padding: '1px 7px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--bg-300)',
                        color: 'var(--text-200)',
                        border: 'var(--border-w) solid var(--border-200)',
                      }}
                    >
                      {src.type === 'visual' ? <ImageIcon size={11} /> : <FileText size={11} />}
                      {src.type === 'visual' ? 'ColPali Visual Page' : 'Hybrid Text Passage'}
                    </span>
                  </div>

                  {/* Chunk Reference */}
                  <div style={{ fontSize: '12px', color: 'var(--text-300)' }}>
                    Chunk ID: <code style={{ fontFamily: 'var(--font-mono)' }}>{src.chunk_id}</code>
                  </div>

                  {/* Visual Page Image Preview if available */}
                  {matchedVisualPath && (
                    <div style={{ marginTop: '4px' }}>
                      <div
                        style={{
                          position: 'relative',
                          borderRadius: 'var(--radius-md)',
                          overflow: 'hidden',
                          border: 'var(--border-w) solid var(--border-200)',
                          background: 'var(--bg-300)',
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
                            display: 'block',
                          }}
                        />
                        <div
                          style={{
                            position: 'absolute',
                            inset: 0,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'rgba(20, 20, 19, 0.45)',
                            gap: '6px',
                            color: '#ffffff',
                            fontSize: '13px',
                            fontWeight: 500,
                          }}
                        >
                          <Maximize2 size={15} /> Inspect 150 DPI Page Image
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
            background: 'rgba(20, 20, 19, 0.85)',
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
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-modal)',
            }}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
};
