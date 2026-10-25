/**
 * src/utils/imageUrl.ts
 * Normalizes backend filesystem paths into browser-safe HTTP URLs.
 */

export function resolvePageImageUrl(rawPath: string, backendBaseUrl: string = ''): string {
  if (!rawPath) return '';
  if (rawPath.startsWith('http://') || rawPath.startsWith('https://')) {
    return rawPath;
  }

  // Handle patterns like .../data/page_images/{doc_id}/page_{n}.png or .../page_images/{doc_id}/{filename}
  const match = rawPath.match(/page_images[/\\]([^/\\]+)[/\\]([^/\\]+)$/);
  if (match) {
    const [, docId, filename] = match;
    const base = backendBaseUrl || '';
    return `${base}/static/page_images/${docId}/${filename}`;
  }

  return rawPath;
}
