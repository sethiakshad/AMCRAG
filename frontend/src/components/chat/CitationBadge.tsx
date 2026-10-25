/**
 * src/components/chat/CitationBadge.tsx
 * Interactive [E#] citation badge with hover preview and click-through to Evidence Drawer.
 */

import React from 'react';
import { SourceMetadata } from '../../types/amcrag';

export interface CitationBadgeProps {
  evidenceTag: string; // e.g. "[E1]"
  evidenceId: string;  // e.g. "E1"
  source?: SourceMetadata;
  onClick: (evidenceId: string) => void;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({
  evidenceTag,
  evidenceId,
  source,
  onClick,
}) => {
  const tooltipText = source
    ? `${source.document}${source.page ? ` (Page ${source.page})` : ''} • ${source.type === 'visual' ? 'Visual Page' : 'Text Passage'}`
    : `Evidence ${evidenceId}`;

  return (
    <button
      type="button"
      className="citation-badge"
      onClick={() => onClick(evidenceId)}
      title={tooltipText}
    >
      {evidenceTag}
    </button>
  );
};
