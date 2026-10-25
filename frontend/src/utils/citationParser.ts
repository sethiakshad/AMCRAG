/**
 * src/utils/citationParser.ts
 * Parses markdown text containing [E#] citation tags into structured tokens.
 */

export interface CitationSegment {
  type: 'text' | 'citation';
  content: string;
  evidenceId?: string; // e.g. "E1"
  evidenceNum?: number; // e.g. 1
}

export function parseCitations(text: string): CitationSegment[] {
  if (!text) return [];

  const regex = /\[E(\d+)\]/g;
  const segments: CitationSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const matchIndex = match.index;
    if (matchIndex > lastIndex) {
      segments.push({
        type: 'text',
        content: text.substring(lastIndex, matchIndex),
      });
    }

    segments.push({
      type: 'citation',
      content: match[0],
      evidenceId: `E${match[1]}`,
      evidenceNum: parseInt(match[1], 10),
    });

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push({
      type: 'text',
      content: text.substring(lastIndex),
    });
  }

  return segments;
}
