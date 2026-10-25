/**
 * src/hooks/useDocuments.ts
 * Manages knowledge base document catalog state, uploads, and deletions.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  deleteDocument as apiDeleteDocument,
  listDocuments as apiListDocuments,
  uploadDocument as apiUploadDocument,
} from '../services/api';
import { DocumentSummary, DocumentUploadResponse } from '../types/amcrag';

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const refreshDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiListDocuments();
      setDocuments(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load document catalog');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  const upload = useCallback(
    async (file: File, force: boolean = false): Promise<DocumentUploadResponse> => {
      setIsUploading(true);
      setError(null);
      try {
        const response = await apiUploadDocument(file, force);
        await refreshDocuments();
        return response;
      } catch (err: any) {
        setError(err.message || 'Upload failed');
        throw err;
      } finally {
        setIsUploading(false);
      }
    },
    [refreshDocuments]
  );

  const remove = useCallback(
    async (docId: string): Promise<void> => {
      setError(null);
      try {
        await apiDeleteDocument(docId);
        setDocuments((prev) => prev.filter((d) => d.document_id !== docId));
      } catch (err: any) {
        setError(err.message || 'Failed to delete document');
        throw err;
      }
    },
    []
  );

  const filteredDocuments = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
    doc.document_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return {
    documents: filteredDocuments,
    allDocuments: documents,
    isLoading,
    isUploading,
    error,
    searchQuery,
    setSearchQuery,
    refreshDocuments,
    upload,
    remove,
  };
}
